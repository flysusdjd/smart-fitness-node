#include <Arduino.h>
#include <Wire.h>
#include <math.h>
#include <MPU6050.h>
#include <BLEDevice.h>
#include <BLEUtils.h>
#include <BLEServer.h>
#include <BLE2902.h>

MPU6050 mpu;

static const char *DEVICE_NAME = "ESP32S3_Fitness_BLE";
static const char *SERVICE_UUID = "4fafc201-1fb5-459e-8fcc-c5c9c331914b";
static const char *CHARACTERISTIC_UUID = "beb5483e-36e1-4688-b7f5-ea07361b26a8";
static const uint16_t BLE_SEND_INTERVAL_MS = 100;

static const int SDA_PIN = 1;
static const int SCL_PIN = 2;
static const int FLEX_SENSOR_PIN = 4;

// ESP32-S3 ADC 采用 12 位采样，电压按 3.3V 参考值换算。
static const int ADC_RESOLUTION = 4095;
static const int ADC_REF_MV = 3300;

// 资料里写这个模块可接 5V，OUT 最高可能到 0-5V。
// ESP32-S3 的 ADC 引脚不能直接承受 5V。
// 如果模块按 5V 供电，必须先做分压/限幅，确保 GPIO4 实际输入不超过 3300mV。
//
// 这个模块还是“应变片 + 放大板 + 电位器”的结构，
// AO 起始点和增益都会随电位器调整而变化。
// 所以这里不再把“满量程”写死成固定毫伏值，而是按自然状态基线的比例自动计算。

// 这片应变片当前的安装方向是“越弯曲，输出电压越低”。
// 如果你后面把应变片翻面安装，导致越弯曲电压越高，把它改成 false 即可。
static const bool FLEX_BEND_LOWERS_VOLTAGE = true;

// 开机基线标定：上电后请保持应变片自然不弯曲。
static const int FLEX_BASELINE_SAMPLE_COUNT = 80;
static const int FLEX_BASELINE_SAMPLE_DELAY_MS = 10;

// 读取原始 ADC 时做一次“去极值后的中值均值”，降低模拟量抖动。
static const int FLEX_ADC_SAMPLE_COUNT = 9;

// 死区按“当前基线的百分比”计算，更适合带电位器的应变片模块。
static const float FLEX_DEAD_ZONE_RATIO = 0.02f;
static const int FLEX_DEAD_ZONE_MIN_MV = 80;
static const int FLEX_DEAD_ZONE_MAX_MV = 220;

// 满量程也按“当前基线的百分比”计算。
// 这样当你转动模块上的 AO 电位器后，软件不用再重写固定毫伏阈值。
static const float FLEX_FULL_BEND_RATIO = 1.00f;
static const int FLEX_FULL_BEND_MIN_MV = 1000;
static const int FLEX_FULL_BEND_MAX_MV = 3300;

// 原始电压只用于展示和建模，指数内部单独做平滑，避免 UI 一跳一跳。
static const float FLEX_SIGNAL_SMOOTH_ALPHA = 0.20f;

// 当传感器回到自然状态附近时，允许基线很慢地自动跟随，补偿温漂和零点漂移。
static const float FLEX_BASELINE_TRACK_ALPHA = 0.003f;

// 指数曲线大于 1 时会降低中前段灵敏度，让“微微一弯就满格”的问题缓和一些。
static const float FLEX_INDEX_GAMMA = 1.40f;

// 如果原始电压长期贴近 0mV，通常说明模块增益过高或已经撞到输出下限。
static const int FLEX_NEAR_RAIL_MV = 80;
static const uint32_t FLEX_WARN_INTERVAL_MS = 3000;

BLECharacteristic *pCharacteristic = nullptr;
bool deviceConnected = false;
uint32_t packetSequence = 0;
bool mpuReady = false;

int flexBaselineAdc = 0;
float flexBaselineMv = 0.0f;
float smoothedFlexMv = 0.0f;
uint32_t lastFlexWarnMs = 0;

class MyServerCallbacks : public BLEServerCallbacks {
public:
    void onConnect(BLEServer *pServer) override {
        deviceConnected = true;
        Serial.println("[BLE] Phone connected");
    }

    void onDisconnect(BLEServer *pServer) override {
        deviceConnected = false;
        pServer->getAdvertising()->start();
        Serial.println("[BLE] Phone disconnected");
        Serial.println("[BLE] Advertising restarted");
    }
};

int getCurrentBaselineMv() {
    return (int)(flexBaselineMv + 0.5f);
}

int getFlexDeadZoneMv() {
    int deadZoneMv = (int)(getCurrentBaselineMv() * FLEX_DEAD_ZONE_RATIO + 0.5f);
    return constrain(deadZoneMv, FLEX_DEAD_ZONE_MIN_MV, FLEX_DEAD_ZONE_MAX_MV);
}

int getFlexFullBendDeltaMv() {
    int fullBendDeltaMv = (int)(getCurrentBaselineMv() * FLEX_FULL_BEND_RATIO + 0.5f);
    return constrain(fullBendDeltaMv, FLEX_FULL_BEND_MIN_MV, FLEX_FULL_BEND_MAX_MV);
}

// 读取应变片模块的 AO 输出，并对 9 个采样值排序后取中间 5 个均值。
void scanI2cDevices() {
    Serial.println("[I2C] Scanning devices...");
    int found = 0;
    for (uint8_t address = 1; address < 127; ++address) {
        Wire.beginTransmission(address);
        if (Wire.endTransmission() == 0) {
            Serial.printf("[I2C] Found device at 0x%02X\n", address);
            found++;
        }
    }
    if (found == 0) {
        Serial.println("[I2C] No device found on the bus");
    }
}

int readFlexVoltageMv(int pin, int &rawAdc) {
    int samples[FLEX_ADC_SAMPLE_COUNT];

    for (int i = 0; i < FLEX_ADC_SAMPLE_COUNT; ++i) {
        samples[i] = analogRead(pin);
        delayMicroseconds(800);
    }

    for (int i = 0; i < FLEX_ADC_SAMPLE_COUNT - 1; ++i) {
        for (int j = i + 1; j < FLEX_ADC_SAMPLE_COUNT; ++j) {
            if (samples[j] < samples[i]) {
                int temp = samples[i];
                samples[i] = samples[j];
                samples[j] = temp;
            }
        }
    }

    long middleSum = 0;
    for (int i = 2; i <= 6; ++i) {
        middleSum += samples[i];
    }

    rawAdc = (int)(middleSum / 5);
    long rawMv = ((long)rawAdc * ADC_REF_MV + ADC_RESOLUTION / 2) / ADC_RESOLUTION;
    return (int)rawMv;
}

void printFlexCalibrationInfo() {
    Serial.printf("[FLEX] Baseline ADC = %d\n", flexBaselineAdc);
    Serial.printf("[FLEX] Baseline Voltage = %d mV\n", getCurrentBaselineMv());
    Serial.printf("[FLEX] Dead zone = %d mV\n", getFlexDeadZoneMv());
    Serial.printf("[FLEX] Full bend delta = %d mV\n", getFlexFullBendDeltaMv());
    Serial.printf("[FLEX] Signal smooth alpha = %.2f\n", FLEX_SIGNAL_SMOOTH_ALPHA);
    Serial.printf("[FLEX] Baseline track alpha = %.4f\n", FLEX_BASELINE_TRACK_ALPHA);
    Serial.printf("[FLEX] Index gamma = %.2f\n", FLEX_INDEX_GAMMA);
}

// 上电时记录自然状态基线，后面的所有弯曲程度都基于这条基线计算。
void calibrateFlexBaseline() {
    long adcSum = 0;
    long mvSum = 0;

    Serial.println("[FLEX] Start baseline calibration...");
    Serial.println("[FLEX] Keep the strain gauge in its natural, unbent state.");

    for (int i = 0; i < FLEX_BASELINE_SAMPLE_COUNT; ++i) {
        int rawAdc = 0;
        int rawMv = readFlexVoltageMv(FLEX_SENSOR_PIN, rawAdc);
        adcSum += rawAdc;
        mvSum += rawMv;
        delay(FLEX_BASELINE_SAMPLE_DELAY_MS);
    }

    flexBaselineAdc = (int)(adcSum / FLEX_BASELINE_SAMPLE_COUNT);
    flexBaselineMv = (float)mvSum / (float)FLEX_BASELINE_SAMPLE_COUNT;
    smoothedFlexMv = flexBaselineMv;
    printFlexCalibrationInfo();
}

// 根据安装方向，把“当前值相对自然状态变化了多少”转换成弯曲量。
int calculateBendDeltaMv(int filteredMv) {
    int baselineMv = getCurrentBaselineMv();
    int deltaMv = FLEX_BEND_LOWERS_VOLTAGE ? (baselineMv - filteredMv) : (filteredMv - baselineMv);
    return max(deltaMv, 0);
}

// 当应变片回到自然状态附近时，允许基线很慢地跟随，减轻温漂和放大板零点漂移。
void updateFlexBaseline(int filteredMv, int bendDeltaMv) {
    int baselineTrackWindowMv = getFlexDeadZoneMv() / 2;
    if (bendDeltaMv > baselineTrackWindowMv) {
        return;
    }

    flexBaselineMv = flexBaselineMv +
                     ((float)filteredMv - flexBaselineMv) * FLEX_BASELINE_TRACK_ALPHA;
}

// 弯曲指数只用于实时展示和交互提示，原始 ADC / mV 仍然完整保留给后续建模使用。
int calculateFlexIndex(int bendDeltaMv) {
    int deadZoneMv = getFlexDeadZoneMv();
    int fullBendDeltaMv = getFlexFullBendDeltaMv();

    if (bendDeltaMv <= deadZoneMv || fullBendDeltaMv <= deadZoneMv) {
        return 0;
    }

    if (bendDeltaMv >= fullBendDeltaMv) {
        return 100;
    }

    float normalized = (float)(bendDeltaMv - deadZoneMv) /
                       (float)(fullBendDeltaMv - deadZoneMv);

    if (normalized < 0.0f) {
        normalized = 0.0f;
    } else if (normalized > 1.0f) {
        normalized = 1.0f;
    }

    // 接近满量程时直接顶到 100%，让最大弯曲更容易看懂。
    if (normalized >= 0.98f) {
        return 100;
    }

    float curved = powf(normalized, FLEX_INDEX_GAMMA);
    return (int)(curved * 100.0f + 0.5f);
}

void warnIfFlexOutputNearRail(int rawMv) {
    if (rawMv > FLEX_NEAR_RAIL_MV) {
        return;
    }

    if (millis() - lastFlexWarnMs < FLEX_WARN_INTERVAL_MS) {
        return;
    }

    lastFlexWarnMs = millis();
    Serial.println("[FLEX][WARN] Raw voltage is near 0mV.");
    Serial.println("[FLEX][WARN] This usually means the module gain is too high or the AO output has hit its lower rail.");
    Serial.println("[FLEX][WARN] Turn the board potentiometer slightly to reduce gain / move the zero point.");
}

void setupBle() {
    BLEDevice::init(DEVICE_NAME);

    BLEServer *pServer = BLEDevice::createServer();
    pServer->setCallbacks(new MyServerCallbacks());

    BLEService *pService = pServer->createService(SERVICE_UUID);
    pCharacteristic = pService->createCharacteristic(
        CHARACTERISTIC_UUID,
        BLECharacteristic::PROPERTY_NOTIFY | BLECharacteristic::PROPERTY_READ
    );
    pCharacteristic->addDescriptor(new BLE2902());
    pCharacteristic->setValue("booting");

    pService->start();

    BLEAdvertising *pAdvertising = BLEDevice::getAdvertising();
    pAdvertising->addServiceUUID(SERVICE_UUID);
    pAdvertising->setScanResponse(true);
    pAdvertising->setMinPreferred(0x06);
    pAdvertising->setMinPreferred(0x12);
    BLEDevice::startAdvertising();

    Serial.println("[BLE] Service started");
}

void setupMpu() {
    Wire.begin(SDA_PIN, SCL_PIN);
    scanI2cDevices();
    mpu.initialize();

    if (!mpu.testConnection()) {
        Serial.println("[MPU6050] Connection failed");
        Serial.printf("[MPU6050] Check wiring: SDA->GPIO%d, SCL->GPIO%d, VCC, GND\n", SDA_PIN, SCL_PIN);
        Serial.println("[MPU6050] BLE will still start, but IMU data will stay 0 until the sensor is fixed");
        mpuReady = false;
        return;
    }

    Serial.println("[MPU6050] Ready");
    mpuReady = true;
}

void setupFlexSensor() {
    analogReadResolution(12);
    pinMode(FLEX_SENSOR_PIN, INPUT);

    Serial.printf("[FLEX] GPIO %d ready\n", FLEX_SENSOR_PIN);
    Serial.println("[FLEX] Module type: strain gauge amplifier AO output");
    Serial.println("[FLEX] If the module is powered from 5V, do not connect OUT directly to ESP32-S3 ADC without voltage limiting.");
}

void setup() {
    Serial.begin(115200);
    delay(1000);

    Serial.println();
    Serial.println("=================================");
    Serial.println("ESP32-S3 Smart Fitness Node");
    Serial.println("IMU + Strain Gauge + BLE");
    Serial.println("=================================");

    setupMpu();
    setupFlexSensor();
    calibrateFlexBaseline();
    setupBle();
}

void loop() {
    static uint32_t lastSendMs = 0;

    if (millis() - lastSendMs < BLE_SEND_INTERVAL_MS) {
        delay(5);
        return;
    }
    lastSendMs = millis();

    int16_t ax, ay, az;
    int16_t gx, gy, gz;
    int rawAdc = 0;
    uint32_t timestampMs = millis();

    if (mpuReady) {
        mpu.getAcceleration(&ax, &ay, &az);
        mpu.getRotation(&gx, &gy, &gz);
    } else {
        ax = ay = az = 0;
        gx = gy = gz = 0;
    }

    int rawVoltageMv = readFlexVoltageMv(FLEX_SENSOR_PIN, rawAdc);

    // 指数内部使用平滑后的电压，原始值仍然按真实采样值发送给手机和 CSV。
    smoothedFlexMv = smoothedFlexMv +
                     ((float)rawVoltageMv - smoothedFlexMv) * FLEX_SIGNAL_SMOOTH_ALPHA;
    int filteredVoltageMv = (int)(smoothedFlexMv + 0.5f);

    int bendDeltaMv = calculateBendDeltaMv(filteredVoltageMv);
    updateFlexBaseline(filteredVoltageMv, bendDeltaMv);
    bendDeltaMv = calculateBendDeltaMv(filteredVoltageMv);

    int flexIndex = calculateFlexIndex(bendDeltaMv);
    warnIfFlexOutputNearRail(rawVoltageMv);

    // CSV 格式：
    // seq,timestampMs,ax,ay,az,gx,gy,gz,flexRawAdc,flexRawMv,flexIndex
    String data = String(packetSequence++) + "," + String(timestampMs) + "," +
                  String(ax) + "," + String(ay) + "," + String(az) + "," +
                  String(gx) + "," + String(gy) + "," + String(gz) + "," +
                  String(rawAdc) + "," + String(rawVoltageMv) + "," + String(flexIndex);

    Serial.print("[DATA] ");
    Serial.println(data);

    if (deviceConnected && pCharacteristic != nullptr) {
        pCharacteristic->setValue(data.c_str());
        pCharacteristic->notify();
    }
}
