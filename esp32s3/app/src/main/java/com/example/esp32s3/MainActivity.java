package com.example.esp32s3;

import android.Manifest;
import android.bluetooth.BluetoothAdapter;
import android.bluetooth.BluetoothDevice;
import android.bluetooth.BluetoothGatt;
import android.bluetooth.BluetoothGattCallback;
import android.bluetooth.BluetoothGattCharacteristic;
import android.bluetooth.BluetoothGattDescriptor;
import android.bluetooth.BluetoothGattService;
import android.bluetooth.BluetoothManager;
import android.bluetooth.BluetoothProfile;
import android.bluetooth.le.BluetoothLeScanner;
import android.bluetooth.le.ScanCallback;
import android.bluetooth.le.ScanResult;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.os.Build;
import android.os.Bundle;
import android.os.Environment;
import android.os.Handler;
import android.os.Looper;
import android.speech.tts.TextToSpeech;
import android.view.View;
import android.widget.Button;
import android.widget.TextView;
import android.widget.Toast;

import androidx.annotation.NonNull;
import androidx.appcompat.app.AppCompatActivity;
import androidx.core.app.ActivityCompat;
import androidx.core.content.ContextCompat;

import com.google.android.material.textfield.TextInputEditText;

import java.io.BufferedWriter;
import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.OutputStreamWriter;
import java.nio.charset.StandardCharsets;
import java.text.SimpleDateFormat;
import java.util.ArrayList;
import java.util.Date;
import java.util.List;
import java.util.Locale;
import java.util.UUID;

public class MainActivity extends AppCompatActivity implements TextToSpeech.OnInitListener {

    private static final String DEVICE_NAME = "ESP32S3_Fitness_BLE";
    private static final UUID SERVICE_UUID = UUID.fromString("4fafc201-1fb5-459e-8fcc-c5c9c331914b");
    private static final UUID CHAR_UUID = UUID.fromString("beb5483e-36e1-4688-b7f5-ea07361b26a8");
    private static final UUID CCCD_UUID = UUID.fromString("00002902-0000-1000-8000-00805f9b34fb");
    private static final int REQUEST_MTU = 247;
    private static final long SCAN_TIMEOUT_MS = 12000L;
    private static final long VOICE_COOLDOWN_MS = 2800L;
    private static final long TTS_INIT_SETTLE_MS = 300L;
    private static final String GOOGLE_TTS_PACKAGE = "com.google.android.tts";
    private static final String DEFAULT_RECORD_LABEL = "training_session";
    private static final String CSV_HEADER =
            "phoneReceiveTimeMs,label,seq,timestampMs,ax,ay,az,gx,gy,gz,flexRawAdc,flexRawMv,flexIndex,rawPacket";

    private TextView tvStatus;
    private TextView tvAccountMode;
    private TextView tvAccountUser;
    private TextView tvAccountBackend;
    private TextView tvSequence;
    private TextView tvTimestamp;
    private TextView tvAcceleration;
    private TextView tvGyroscope;
    private TextView tvFlexAdc;
    private TextView tvFlexMv;
    private TextView tvFlexIndex;
    private TextView tvRawPacket;
    private TextView tvRecordStatus;
    private TextView tvRecordCount;
    private TextView tvRecordFile;
    private TextView tvEvalAction;
    private TextView tvEvalPhase;
    private TextView tvEvalScore;
    private TextView tvEvalRisk;
    private TextView tvEvalSuggestion;
    private TextView tvVoiceStatus;
    private TextInputEditText etActionLabel;
    private Button btnScan;
    private Button btnDisconnect;
    private Button btnStartRecord;
    private Button btnStopRecord;
    private Button btnVoiceToggle;
    private Button btnToggleDebug;
    private Button btnSwitchAccount;
    private Button btnNavHome;
    private Button btnNavTraining;
    private Button btnNavGuide;
    private Button btnNavReport;
    private Button btnNavSettings;
    private View pageHome;
    private View pageTraining;
    private View pageGuide;
    private View pageReport;
    private View pageSettings;
    private View layoutDebugSection;

    private BluetoothAdapter bluetoothAdapter;
    private BluetoothGatt currentGatt;
    private BluetoothLeScanner currentScanner;
    private ScanCallback currentScanCallback;

    private final Handler mainHandler = new Handler(Looper.getMainLooper());

    private BufferedWriter recordWriter;
    private File currentRecordFile;
    private boolean isRecording = false;
    private boolean isScanning = false;
    private boolean isGattConnected = false;
    private boolean isSubscribed = false;
    private boolean disconnectRequested = false;
    private int recordCount = 0;
    private String currentLabel = "";

    private TextToSpeech textToSpeech;
    private boolean ttsReady = false;
    private boolean ttsInitializing = false;
    private boolean pendingVoiceTest = false;
    private boolean triedSystemDefaultTts = false;
    private String currentTtsEnginePackage = null;
    private boolean voiceEnabled = true;
    private long lastSpokenAtMs = 0L;
    private String lastSpokenText = "";

    private long previousPacketTimestampMs = -1L;
    private int previousFlexIndex = -1;
    private float smoothedFlexVelocity = 0f;
    private boolean debugMode = false;
    private SessionManager sessionManager;

    private final Runnable scanTimeoutRunnable = new Runnable() {
        @Override
        public void run() {
            if (!isScanning) {
                return;
            }
            stopScanInternal();
            tvStatus.setText(R.string.status_scan_timeout);
            updateUiState();
        }
    };

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        sessionManager = new SessionManager(this);
        if (!sessionManager.hasAccessMode()) {
            openAuthPage();
            return;
        }
        setContentView(R.layout.activity_main);

        btnSwitchAccount = findViewById(R.id.btnSwitchAccount);
        btnScan = findViewById(R.id.btnScan);
        btnDisconnect = findViewById(R.id.btnDisconnect);
        btnStartRecord = findViewById(R.id.btnStartRecord);
        btnStopRecord = findViewById(R.id.btnStopRecord);
        btnVoiceToggle = findViewById(R.id.btnVoiceToggle);
        btnToggleDebug = findViewById(R.id.btnToggleDebug);
        btnNavHome = findViewById(R.id.btnNavHome);
        btnNavTraining = findViewById(R.id.btnNavTraining);
        btnNavGuide = findViewById(R.id.btnNavGuide);
        btnNavReport = findViewById(R.id.btnNavReport);
        btnNavSettings = findViewById(R.id.btnNavSettings);

        tvStatus = findViewById(R.id.tvStatus);
        tvAccountMode = findViewById(R.id.tvAccountMode);
        tvAccountUser = findViewById(R.id.tvAccountUser);
        tvAccountBackend = findViewById(R.id.tvAccountBackend);
        tvSequence = findViewById(R.id.tvSequence);
        tvTimestamp = findViewById(R.id.tvTimestamp);
        tvAcceleration = findViewById(R.id.tvAcceleration);
        tvGyroscope = findViewById(R.id.tvGyroscope);
        tvFlexAdc = findViewById(R.id.tvFlexAdc);
        tvFlexMv = findViewById(R.id.tvFlexMv);
        tvFlexIndex = findViewById(R.id.tvFlexIndex);
        tvRawPacket = findViewById(R.id.tvRawPacket);
        tvRecordStatus = findViewById(R.id.tvRecordStatus);
        tvRecordCount = findViewById(R.id.tvRecordCount);
        tvRecordFile = findViewById(R.id.tvRecordFile);
        tvEvalAction = findViewById(R.id.tvEvalAction);
        tvEvalPhase = findViewById(R.id.tvEvalPhase);
        tvEvalScore = findViewById(R.id.tvEvalScore);
        tvEvalRisk = findViewById(R.id.tvEvalRisk);
        tvEvalSuggestion = findViewById(R.id.tvEvalSuggestion);
        tvVoiceStatus = findViewById(R.id.tvVoiceStatus);
        etActionLabel = findViewById(R.id.etActionLabel);
        pageHome = findViewById(R.id.pageHome);
        pageTraining = findViewById(R.id.pageTraining);
        pageGuide = findViewById(R.id.pageGuide);
        pageReport = findViewById(R.id.pageReport);
        pageSettings = findViewById(R.id.pageSettings);
        layoutDebugSection = findViewById(R.id.layoutDebugSection);

        BluetoothManager manager = (BluetoothManager) getSystemService(BLUETOOTH_SERVICE);
        if (manager != null) {
            bluetoothAdapter = manager.getAdapter();
        }

        voiceEnabled = sessionManager.isVoiceEnabled();

        requestPermissions();
        initializeTextToSpeech();

        resetSensorViews();
        resetAssessmentState();
        updateRecordCount(0);
        updateAccountViews();
        updateVoiceUi();
        updateDebugUi();
        updateUiState();
        showAppPage("home");

        btnSwitchAccount.setOnClickListener(v -> switchAccount());
        btnScan.setOnClickListener(v -> startScan());
        btnDisconnect.setOnClickListener(v -> disconnectDevice());
        btnStartRecord.setOnClickListener(v -> startRecording());
        btnStopRecord.setOnClickListener(v -> stopRecording(true));
        btnVoiceToggle.setOnClickListener(v -> toggleVoiceFeedback());
        btnToggleDebug.setOnClickListener(v -> toggleDebugMode());
        btnNavHome.setOnClickListener(v -> showAppPage("home"));
        btnNavTraining.setOnClickListener(v -> showAppPage("training"));
        btnNavGuide.setOnClickListener(v -> showAppPage("guide"));
        btnNavReport.setOnClickListener(v -> showAppPage("report"));
        btnNavSettings.setOnClickListener(v -> showAppPage("settings"));
    }

    @Override
    protected void onDestroy() {
        stopRecording(false);
        stopScanInternal();
        closeCurrentGatt();
        mainHandler.removeCallbacksAndMessages(null);
        if (textToSpeech != null) {
            textToSpeech.stop();
            textToSpeech.shutdown();
        }
        super.onDestroy();
    }

    private void showAppPage(String page) {
        setPageVisibility(pageHome, "home".equals(page));
        setPageVisibility(pageTraining, "training".equals(page));
        setPageVisibility(pageGuide, "guide".equals(page));
        setPageVisibility(pageReport, "report".equals(page));
        setPageVisibility(pageSettings, "settings".equals(page));

        updateNavButton(btnNavHome, "home".equals(page));
        updateNavButton(btnNavTraining, "training".equals(page));
        updateNavButton(btnNavGuide, "guide".equals(page));
        updateNavButton(btnNavReport, "report".equals(page));
        updateNavButton(btnNavSettings, "settings".equals(page));
    }

    private void setPageVisibility(View pageView, boolean visible) {
        if (pageView != null) {
            pageView.setVisibility(visible ? View.VISIBLE : View.GONE);
        }
    }

    private void updateNavButton(Button button, boolean selected) {
        if (button == null) {
            return;
        }
        button.setSelected(selected);
        button.setTextColor(ContextCompat.getColor(this, selected ? R.color.white : R.color.sf_muted));
        button.setTypeface(null, selected ? android.graphics.Typeface.BOLD : android.graphics.Typeface.NORMAL);
    }

    @Override
    protected void onResume() {
        super.onResume();
        if (!sessionManager.hasAccessMode()) {
            openAuthPage();
            return;
        }
        updateAccountViews();
    }

    @Override
    public void onInit(int status) {
        mainHandler.postDelayed(() -> finishTextToSpeechInit(status), TTS_INIT_SETTLE_MS);
    }

    private void initializeTextToSpeech() {
        triedSystemDefaultTts = false;
        String preferredEngine = isPackageInstalled(GOOGLE_TTS_PACKAGE) ? GOOGLE_TTS_PACKAGE : null;
        createTextToSpeech(preferredEngine);
    }

    private void createTextToSpeech(String enginePackage) {
        ttsReady = false;
        ttsInitializing = true;
        currentTtsEnginePackage = enginePackage;
        updateVoiceUi();
        if (textToSpeech != null) {
            try {
                textToSpeech.stop();
                textToSpeech.shutdown();
            } catch (Exception ignored) {
                // Some OEM engines throw while being recreated. We can safely retry.
            }
            textToSpeech = null;
        }
        if (enginePackage == null || enginePackage.trim().isEmpty()) {
            triedSystemDefaultTts = true;
            textToSpeech = new TextToSpeech(this, this);
        } else {
            textToSpeech = new TextToSpeech(this, this, enginePackage);
        }
    }

    private void finishTextToSpeechInit(int status) {
        if (status == TextToSpeech.SUCCESS && textToSpeech != null) {
            ttsReady = configureTextToSpeechLanguage();
            if (ttsReady) {
                textToSpeech.setSpeechRate(1.0f);
                textToSpeech.setPitch(1.0f);
            }
        } else {
            ttsReady = false;
        }
        if (!ttsReady && !triedSystemDefaultTts) {
            createTextToSpeech(null);
            return;
        }
        ttsInitializing = false;
        updateVoiceUi();
        if (pendingVoiceTest) {
            pendingVoiceTest = false;
            speakVoiceTestOrShowError();
        }
    }

    private boolean isPackageInstalled(String packageName) {
        if (packageName == null || packageName.trim().isEmpty()) {
            return false;
        }
        try {
            getPackageManager().getPackageInfo(packageName, 0);
            return true;
        } catch (PackageManager.NameNotFoundException ignored) {
            return false;
        }
    }

    private boolean configureTextToSpeechLanguage() {
        if (textToSpeech == null) {
            return false;
        }

        List<Locale> candidates = new ArrayList<>();
        candidates.add(Locale.SIMPLIFIED_CHINESE);
        candidates.add(Locale.CHINA);
        candidates.add(Locale.CHINESE);
        Locale defaultLocale = Locale.getDefault();
        if (defaultLocale != null) {
            candidates.add(defaultLocale);
        }
        Locale defaultTtsLocale = textToSpeech.getDefaultLanguage();
        if (defaultTtsLocale != null) {
            candidates.add(defaultTtsLocale);
        }

        for (Locale locale : candidates) {
            if (locale == null) {
                continue;
            }
            int available = textToSpeech.isLanguageAvailable(locale);
            if (available == TextToSpeech.LANG_MISSING_DATA || available == TextToSpeech.LANG_NOT_SUPPORTED) {
                continue;
            }
            int result = textToSpeech.setLanguage(locale);
            if (result != TextToSpeech.LANG_MISSING_DATA && result != TextToSpeech.LANG_NOT_SUPPORTED) {
                return true;
            }
        }

        // Some OEM engines, especially customized Android ROMs, can speak with
        // the system default voice but report language availability incorrectly.
        return true;
    }

    private void requestPermissions() {
        List<String> permissions = new ArrayList<>();
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            permissions.add(Manifest.permission.BLUETOOTH_SCAN);
            permissions.add(Manifest.permission.BLUETOOTH_CONNECT);
        } else {
            permissions.add(Manifest.permission.BLUETOOTH);
            permissions.add(Manifest.permission.BLUETOOTH_ADMIN);
        }
        permissions.add(Manifest.permission.ACCESS_FINE_LOCATION);
        permissions.add(Manifest.permission.ACCESS_COARSE_LOCATION);
        ActivityCompat.requestPermissions(this, permissions.toArray(new String[0]), 1);
    }

    private boolean hasPermission(String permission) {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.S) {
            if (Manifest.permission.BLUETOOTH_SCAN.equals(permission)
                    || Manifest.permission.BLUETOOTH_CONNECT.equals(permission)) {
                return true;
            }
        }
        return ContextCompat.checkSelfPermission(this, permission) == PackageManager.PERMISSION_GRANTED;
    }

    private void startScan() {
        if (!hasPermission(Manifest.permission.BLUETOOTH_SCAN)) {
            tvStatus.setText(R.string.status_no_scan_permission);
            return;
        }
        if (bluetoothAdapter == null || !bluetoothAdapter.isEnabled()) {
            tvStatus.setText(R.string.status_bluetooth_off);
            return;
        }

        stopScanInternal();
        closeCurrentGatt();
        resetSensorViews();
        resetAssessmentState();

        currentScanner = bluetoothAdapter.getBluetoothLeScanner();
        if (currentScanner == null) {
            tvStatus.setText(R.string.status_scanner_error);
            return;
        }

        tvStatus.setText(R.string.status_scanning);
        currentScanCallback = new ScanCallback() {
            @Override
            public void onScanResult(int callbackType, ScanResult result) {
                BluetoothDevice device = result.getDevice();
                try {
                    if (device.getName() != null && DEVICE_NAME.equals(device.getName())) {
                        tvStatus.setText(R.string.status_device_found);
                        stopScanInternal();
                        connectDevice(device);
                    }
                } catch (SecurityException e) {
                    tvStatus.setText(R.string.status_permission_error);
                }
            }

            @Override
            public void onScanFailed(int errorCode) {
                stopScanInternal();
                tvStatus.setText(R.string.status_scan_exception);
                updateUiState();
            }
        };

        try {
            currentScanner.startScan(currentScanCallback);
            isScanning = true;
            mainHandler.postDelayed(scanTimeoutRunnable, SCAN_TIMEOUT_MS);
            updateUiState();
        } catch (SecurityException e) {
            tvStatus.setText(R.string.status_scan_exception);
            stopScanInternal();
        }
    }

    private void stopScanInternal() {
        mainHandler.removeCallbacks(scanTimeoutRunnable);
        if (currentScanner != null && currentScanCallback != null) {
            try {
                if (hasPermission(Manifest.permission.BLUETOOTH_SCAN)) {
                    currentScanner.stopScan(currentScanCallback);
                }
            } catch (SecurityException ignored) {
                // ignore
            }
        }
        currentScanCallback = null;
        currentScanner = null;
        isScanning = false;
        updateUiState();
    }

    private void connectDevice(BluetoothDevice device) {
        if (!hasPermission(Manifest.permission.BLUETOOTH_CONNECT)) {
            tvStatus.setText(R.string.status_no_connect_permission);
            return;
        }
        disconnectRequested = false;
        tvStatus.setText(R.string.status_connecting);
        try {
            currentGatt = device.connectGatt(this, false, gattCallback);
            updateUiState();
        } catch (SecurityException e) {
            tvStatus.setText(R.string.status_connect_failed);
        }
    }

    private void disconnectDevice() {
        stopScanInternal();
        if (isRecording) {
            stopRecording(false);
            tvRecordStatus.setText(R.string.record_status_auto_stopped_disconnect);
        }

        if (currentGatt == null && !isGattConnected && !isSubscribed) {
            tvStatus.setText(R.string.status_idle);
            resetSensorViews();
            resetAssessmentState();
            updateUiState();
            return;
        }

        disconnectRequested = true;
        isSubscribed = false;
        tvStatus.setText(R.string.status_disconnecting);
        updateUiState();

        try {
            if (currentGatt != null && hasPermission(Manifest.permission.BLUETOOTH_CONNECT)) {
                currentGatt.disconnect();
            } else {
                closeCurrentGatt();
                tvStatus.setText(R.string.status_idle);
            }
        } catch (SecurityException e) {
            closeCurrentGatt();
            tvStatus.setText(R.string.status_permission_error);
        }
    }

    private void closeCurrentGatt() {
        if (currentGatt != null) {
            try {
                if (hasPermission(Manifest.permission.BLUETOOTH_CONNECT)) {
                    currentGatt.close();
                }
            } catch (SecurityException ignored) {
                // ignore
            }
        }
        currentGatt = null;
        isGattConnected = false;
        isSubscribed = false;
        disconnectRequested = false;
        updateUiState();
    }

    private void startRecording() {
        if (!isSubscribed) {
            tvRecordStatus.setText(R.string.record_status_need_connection);
            showToast(R.string.record_status_need_connection);
            return;
        }

        String labelInput = "";
        if (etActionLabel.getText() != null) {
            labelInput = etActionLabel.getText().toString().trim();
        }
        if (labelInput.isEmpty()) {
            labelInput = DEFAULT_RECORD_LABEL;
            etActionLabel.setText(labelInput);
            tvRecordStatus.setText(getString(R.string.record_status_default_label, labelInput));
            showToast(getString(R.string.record_status_default_label, labelInput));
        }

        stopRecording(false);
        File recordsDir = new File(getExternalFilesDir(Environment.DIRECTORY_DOCUMENTS), "captures");
        if (!recordsDir.exists() && !recordsDir.mkdirs()) {
            tvRecordStatus.setText(getString(R.string.record_status_failed, getString(R.string.record_error_create_dir)));
            return;
        }

        String safeLabel = labelInput.replaceAll("[^\\p{L}\\p{N}_-]", "_");
        String timestamp = new SimpleDateFormat("yyyyMMdd_HHmmss", Locale.getDefault()).format(new Date());
        currentRecordFile = new File(recordsDir, safeLabel + "_" + timestamp + ".csv");

        try {
            recordWriter = new BufferedWriter(
                    new OutputStreamWriter(new FileOutputStream(currentRecordFile), StandardCharsets.UTF_8)
            );
            recordWriter.write(CSV_HEADER);
            recordWriter.newLine();
            recordWriter.flush();
            currentLabel = labelInput;
            isRecording = true;
            recordCount = 0;
            updateRecordCount(recordCount);
            tvRecordFile.setText(getString(R.string.record_file_value, currentRecordFile.getAbsolutePath()));
            tvRecordStatus.setText(R.string.record_status_started);
            showToast(R.string.record_status_started);
            updateUiState();
        } catch (IOException e) {
            recordWriter = null;
            currentRecordFile = null;
            currentLabel = "";
            isRecording = false;
            tvRecordStatus.setText(getString(R.string.record_status_failed, e.getMessage()));
            showToast(getString(R.string.record_status_failed, e.getMessage()));
            updateUiState();
        }
    }

    private void stopRecording(boolean showStoppedMessage) {
        if (!isRecording && recordWriter == null) {
            if (showStoppedMessage) {
                tvRecordStatus.setText(R.string.record_status_no_session);
                showToast(R.string.record_status_no_session);
            }
            updateUiState();
            return;
        }

        IOException closeError = null;
        try {
            if (recordWriter != null) {
                recordWriter.flush();
                recordWriter.close();
            }
        } catch (IOException e) {
            closeError = e;
        }

        boolean hadSession = isRecording;
        String savedPath = currentRecordFile != null ? currentRecordFile.getAbsolutePath() : "";
        recordWriter = null;
        currentRecordFile = null;
        isRecording = false;
        currentLabel = "";

        if (closeError != null) {
            tvRecordStatus.setText(getString(R.string.record_status_failed, closeError.getMessage()));
            showToast(getString(R.string.record_status_failed, closeError.getMessage()));
        } else if (showStoppedMessage && hadSession) {
            tvRecordStatus.setText(getString(R.string.record_status_saved, savedPath));
            showToast(R.string.record_status_stopped);
        } else if (showStoppedMessage) {
            tvRecordStatus.setText(R.string.record_status_stopped);
            showToast(R.string.record_status_stopped);
        }
        updateUiState();
    }

    private void appendRecordLine(String rawPacket) {
        if (!isRecording || recordWriter == null) {
            return;
        }
        long receiveTimeMs = System.currentTimeMillis();
        String csvLine = receiveTimeMs + "," + escapeCsv(currentLabel) + "," + rawPacket + "," + escapeCsv(rawPacket);

        try {
            recordWriter.write(csvLine);
            recordWriter.newLine();
            recordWriter.flush();
            recordCount++;
            updateRecordCount(recordCount);
        } catch (IOException e) {
            stopRecording(false);
            tvRecordStatus.setText(getString(R.string.record_status_failed, e.getMessage()));
        }
    }

    private String escapeCsv(String value) {
        String escaped = value.replace("\"", "\"\"");
        return "\"" + escaped + "\"";
    }

    private void updateRecordCount(int count) {
        tvRecordCount.setText(getString(R.string.record_count_value, count));
    }

    private void resetSensorViews() {
        tvSequence.setText(R.string.waiting_for_data);
        tvTimestamp.setText(R.string.waiting_for_data);
        tvAcceleration.setText(R.string.waiting_for_data);
        tvGyroscope.setText(R.string.waiting_for_data);
        tvFlexAdc.setText(R.string.waiting_for_data);
        tvFlexMv.setText(R.string.waiting_for_data);
        tvFlexIndex.setText(R.string.waiting_for_data);
        tvRawPacket.setText(R.string.waiting_for_data);
    }

    private void resetAssessmentState() {
        previousPacketTimestampMs = -1L;
        previousFlexIndex = -1;
        smoothedFlexVelocity = 0f;
        lastSpokenAtMs = 0L;
        lastSpokenText = "";
        tvEvalAction.setText(R.string.eval_action_idle);
        tvEvalPhase.setText(R.string.eval_phase_idle);
        tvEvalScore.setText(getString(R.string.metric_eval_score_value, 0));
        tvEvalRisk.setText(R.string.eval_risk_unknown);
        tvEvalSuggestion.setText(R.string.eval_suggestion_idle);
        updateVoiceUi();
    }

    private void updateVoiceUi() {
        if (btnVoiceToggle != null) {
            if (!voiceEnabled) {
                btnVoiceToggle.setText(R.string.btn_voice_enable);
            } else if (!ttsReady) {
                btnVoiceToggle.setText(R.string.btn_voice_retry);
            } else {
                btnVoiceToggle.setText(R.string.btn_voice_disable);
            }
        }
        if (tvVoiceStatus == null) {
            return;
        }
        if (!voiceEnabled) {
            tvVoiceStatus.setText(R.string.eval_voice_disabled);
            tvVoiceStatus.setTextColor(0xFF6B7280);
        } else if (ttsInitializing) {
            tvVoiceStatus.setText(R.string.eval_voice_initializing);
            tvVoiceStatus.setTextColor(0xFFB85C38);
        } else if (!ttsReady) {
            tvVoiceStatus.setText(R.string.eval_voice_unavailable);
            tvVoiceStatus.setTextColor(0xFFB85C38);
        } else {
            tvVoiceStatus.setText(R.string.eval_voice_ready);
            tvVoiceStatus.setTextColor(0xFF2F7D57);
        }
    }

    private void toggleVoiceFeedback() {
        if (voiceEnabled && ttsReady) {
            voiceEnabled = false;
            sessionManager.setVoiceEnabled(false);
            pendingVoiceTest = false;
            if (textToSpeech != null) {
                textToSpeech.stop();
            }
            showToast(R.string.eval_voice_disabled);
            updateVoiceUi();
            return;
        }

        voiceEnabled = true;
        sessionManager.setVoiceEnabled(true);
        pendingVoiceTest = true;
        if (ttsReady && textToSpeech != null) {
            pendingVoiceTest = false;
            speakVoiceTestOrShowError();
        } else {
            initializeTextToSpeech();
        }
        updateVoiceUi();
    }

    private void speakVoiceTestOrShowError() {
        if (ttsReady && textToSpeech != null) {
            textToSpeech.stop();
            textToSpeech.speak(getString(R.string.eval_voice_test), TextToSpeech.QUEUE_FLUSH, null, "voice_toggle");
            showToast(R.string.eval_voice_test);
        } else {
            showToast(R.string.eval_voice_unavailable);
        }
    }

    private void toggleDebugMode() {
        debugMode = !debugMode;
        updateDebugUi();
    }

    private void updateDebugUi() {
        if (layoutDebugSection != null) {
            layoutDebugSection.setVisibility(debugMode ? View.VISIBLE : View.GONE);
        }
        if (btnToggleDebug != null) {
            btnToggleDebug.setText(debugMode
                    ? R.string.btn_toggle_debug_on
                    : R.string.btn_toggle_debug_off);
        }
    }

    private void updateAccountViews() {
        if (tvAccountMode == null || tvAccountUser == null || tvAccountBackend == null) {
            return;
        }
        if (sessionManager.isLoggedIn()) {
            tvAccountMode.setText(R.string.account_mode_logged_in);
            tvAccountUser.setText(sessionManager.getUsername());
            if (btnSwitchAccount != null) {
                btnSwitchAccount.setText(R.string.btn_logout);
            }
        } else if (sessionManager.isGuestMode()) {
            tvAccountMode.setText(R.string.account_mode_guest);
            tvAccountUser.setText(R.string.account_no_user);
            if (btnSwitchAccount != null) {
                btnSwitchAccount.setText(R.string.btn_return_login);
            }
        } else {
            tvAccountMode.setText(R.string.account_no_user);
            tvAccountUser.setText(R.string.account_no_user);
            if (btnSwitchAccount != null) {
                btnSwitchAccount.setText(R.string.btn_login_account);
            }
        }

        String backendUrl = sessionManager.getBackendUrl();
        if (backendUrl.trim().isEmpty()) {
            tvAccountBackend.setText(R.string.account_no_backend);
        } else {
            tvAccountBackend.setText(backendUrl);
        }
    }

    private void switchAccount() {
        stopRecording(false);
        stopScanInternal();
        closeCurrentGatt();
        sessionManager.clearSession();
        openAuthPage();
    }

    private void openAuthPage() {
        startActivity(new Intent(this, AuthActivity.class));
        finish();
    }

    private void showToast(int resId) {
        Toast.makeText(this, getString(resId), Toast.LENGTH_SHORT).show();
    }

    private void showToast(String message) {
        if (message == null || message.trim().isEmpty()) {
            return;
        }
        Toast.makeText(this, message, Toast.LENGTH_SHORT).show();
    }

    private void updateUiState() {
        boolean hasConnectionOrScan = isScanning || currentGatt != null || isGattConnected || isSubscribed;
        btnScan.setEnabled(!hasConnectionOrScan);
        btnDisconnect.setEnabled(hasConnectionOrScan);
        btnStartRecord.setEnabled(!isRecording);
        btnStopRecord.setEnabled(true);
        etActionLabel.setEnabled(!isRecording);
        if (btnToggleDebug != null) {
            btnToggleDebug.setEnabled(true);
        }
    }

    private final BluetoothGattCallback gattCallback = new BluetoothGattCallback() {
        @Override
        public void onConnectionStateChange(BluetoothGatt gatt, int status, int newState) {
            if (newState == BluetoothProfile.STATE_CONNECTED && status == BluetoothGatt.GATT_SUCCESS) {
                currentGatt = gatt;
                isGattConnected = true;
                disconnectRequested = false;
                runOnUiThread(() -> {
                    tvStatus.setText(R.string.status_connected);
                    updateUiState();
                });

                try {
                    if (hasPermission(Manifest.permission.BLUETOOTH_CONNECT)) {
                        runOnUiThread(() -> tvStatus.setText(R.string.status_requesting_mtu));
                        boolean requested = gatt.requestMtu(REQUEST_MTU);
                        if (!requested) {
                            gatt.discoverServices();
                        }
                    }
                } catch (SecurityException e) {
                    runOnUiThread(() -> tvStatus.setText(R.string.status_permission_error));
                }
                return;
            }

            boolean wasUserRequested = disconnectRequested;
            isGattConnected = false;
            isSubscribed = false;
            disconnectRequested = false;

            if (gatt != null) {
                try {
                    if (hasPermission(Manifest.permission.BLUETOOTH_CONNECT)) {
                        gatt.close();
                    }
                } catch (SecurityException ignored) {
                    // ignore
                }
            }
            if (gatt == currentGatt) {
                currentGatt = null;
            }

            runOnUiThread(() -> {
                if (isRecording) {
                    stopRecording(false);
                    tvRecordStatus.setText(R.string.record_status_auto_stopped_disconnect);
                }
                resetSensorViews();
                resetAssessmentState();
                if (wasUserRequested) {
                    tvStatus.setText(R.string.status_idle);
                } else {
                    tvStatus.setText(R.string.status_disconnected);
                }
                updateUiState();
            });
        }

        @Override
        public void onMtuChanged(BluetoothGatt gatt, int mtu, int status) {
            if (!hasPermission(Manifest.permission.BLUETOOTH_CONNECT)) {
                return;
            }
            try {
                gatt.discoverServices();
            } catch (SecurityException e) {
                runOnUiThread(() -> tvStatus.setText(R.string.status_permission_error));
            }
        }

        @Override
        public void onServicesDiscovered(BluetoothGatt gatt, int status) {
            if (!hasPermission(Manifest.permission.BLUETOOTH_CONNECT)) {
                return;
            }

            BluetoothGattService service = gatt.getService(SERVICE_UUID);
            if (service == null) {
                runOnUiThread(() -> tvStatus.setText(R.string.status_service_not_found));
                return;
            }

            BluetoothGattCharacteristic characteristic = service.getCharacteristic(CHAR_UUID);
            if (characteristic == null) {
                runOnUiThread(() -> tvStatus.setText(R.string.status_char_not_found));
                return;
            }

            try {
                gatt.setCharacteristicNotification(characteristic, true);
                BluetoothGattDescriptor descriptor = characteristic.getDescriptor(CCCD_UUID);
                if (descriptor == null) {
                    runOnUiThread(() -> tvStatus.setText(R.string.status_char_not_found));
                    return;
                }

                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
                    gatt.writeDescriptor(descriptor, BluetoothGattDescriptor.ENABLE_NOTIFICATION_VALUE);
                } else {
                    descriptor.setValue(BluetoothGattDescriptor.ENABLE_NOTIFICATION_VALUE);
                    gatt.writeDescriptor(descriptor);
                }
            } catch (SecurityException e) {
                runOnUiThread(() -> tvStatus.setText(R.string.status_permission_error));
            }
        }

        @Override
        public void onDescriptorWrite(BluetoothGatt gatt, BluetoothGattDescriptor descriptor, int status) {
            if (!CCCD_UUID.equals(descriptor.getUuid())) {
                return;
            }

            runOnUiThread(() -> {
                if (status == BluetoothGatt.GATT_SUCCESS) {
                    isSubscribed = true;
                    tvStatus.setText(R.string.status_subscribed);
                } else {
                    isSubscribed = false;
                    tvStatus.setText(R.string.status_subscribe_failed);
                }
                updateUiState();
            });
        }

        @Override
        public void onCharacteristicChanged(@NonNull BluetoothGatt gatt,
                                            @NonNull BluetoothGattCharacteristic characteristic,
                                            @NonNull byte[] value) {
            updateData(value);
        }

        @Override
        public void onCharacteristicChanged(BluetoothGatt gatt, BluetoothGattCharacteristic characteristic) {
            updateData(characteristic.getValue());
        }
    };

    private void updateData(byte[] value) {
        if (value == null) {
            return;
        }

        String data = new String(value, StandardCharsets.UTF_8).trim();
        runOnUiThread(() -> tvRawPacket.setText(getString(R.string.raw_packet_value, data)));
        appendRecordLine(data);

        String[] parts = data.split(",");
        if (parts.length < 11) {
            runOnUiThread(() -> tvStatus.setText(R.string.status_invalid_packet));
            return;
        }

        try {
            int seq = Integer.parseInt(parts[0].trim());
            long timestamp = Long.parseLong(parts[1].trim());
            int ax = Integer.parseInt(parts[2].trim());
            int ay = Integer.parseInt(parts[3].trim());
            int az = Integer.parseInt(parts[4].trim());
            int gx = Integer.parseInt(parts[5].trim());
            int gy = Integer.parseInt(parts[6].trim());
            int gz = Integer.parseInt(parts[7].trim());
            int flexAdc = Integer.parseInt(parts[8].trim());
            int flexMv = Integer.parseInt(parts[9].trim());
            int flexIndex = Integer.parseInt(parts[10].trim());

            MotionAssessment assessment = buildMotionAssessment(timestamp, ax, ay, az, gx, gy, gz, flexIndex);

            runOnUiThread(() -> {
                tvSequence.setText(getString(R.string.metric_seq_value, seq));
                tvTimestamp.setText(getString(R.string.metric_time_value, timestamp));
                tvAcceleration.setText(getString(R.string.metric_acc_value, ax, ay, az));
                tvGyroscope.setText(getString(R.string.metric_gyro_value, gx, gy, gz));
                tvFlexAdc.setText(getString(R.string.metric_flex_adc_value, flexAdc));
                tvFlexMv.setText(getString(R.string.metric_flex_mv_value, flexMv));
                tvFlexIndex.setText(getString(R.string.metric_flex_index_value, flexIndex));
                updateAssessmentViews(assessment);
                if (isSubscribed) {
                    tvStatus.setText(R.string.status_subscribed);
                }
            });
        } catch (NumberFormatException e) {
            runOnUiThread(() -> tvStatus.setText(R.string.status_invalid_packet));
        }
    }

    // 閹靛婧€缁旑垰鍘涢悽銊ㄤ氦闁插繗顫夐崚娆忎粵閸斻劋缍旂拠鍕強閿涘苯鎮楃紒顓炲讲閺囨寧宕叉稉鐑樻纯濮濓絽绱￠惃鍕伂娓氀勀侀崹瀣波閺嬫嚎鈧?
    private MotionAssessment buildMotionAssessment(
            long timestampMs,
            int ignoredAx,
            int ignoredAy,
            int ignoredAz,
            int gx,
            int gy,
            int gz,
            int flexIndex
    ) {
        double gyroMag = Math.sqrt(gx * (double) gx + gy * (double) gy + gz * (double) gz);
        long deltaTimeMs = previousPacketTimestampMs > 0 ? Math.max(1L, timestampMs - previousPacketTimestampMs) : 100L;
        float deltaFlex = previousFlexIndex >= 0 ? (flexIndex - previousFlexIndex) : 0f;
        float velocityPerSecond = deltaFlex * 1000f / deltaTimeMs;
        smoothedFlexVelocity = previousFlexIndex < 0
                ? velocityPerSecond
                : (smoothedFlexVelocity * 0.65f + velocityPerSecond * 0.35f);

        previousPacketTimestampMs = timestampMs;
        previousFlexIndex = flexIndex;

        boolean idle = flexIndex < 6 && gyroMag < 260;
        String actionLabel = idle ? getString(R.string.eval_action_idle) : getString(R.string.eval_action_squat);

        String phase;
        if (idle) {
            phase = getString(R.string.eval_phase_idle);
        } else if (smoothedFlexVelocity > 18f) {
            phase = getString(R.string.eval_phase_down);
        } else if (smoothedFlexVelocity < -18f) {
            phase = getString(R.string.eval_phase_up);
        } else if (flexIndex >= 26) {
            phase = getString(R.string.eval_phase_bottom);
        } else {
            phase = getString(R.string.eval_phase_transition);
        }

        int depthScore = idle ? 88 : mapToScore(flexIndex, 6f, 32f);
        int stabilityPenalty = clampToInt((gyroMag - 220.0) / 18.0, 0, 55)
                + clampToInt(Math.abs(smoothedFlexVelocity) / 3.5f, 0, 20);
        int stabilityScore = clampToInt(100 - stabilityPenalty, 0, 100);

        int rhythmScore;
        if (idle) {
            rhythmScore = 92;
        } else {
            float absVelocity = Math.abs(smoothedFlexVelocity);
            if (absVelocity >= 12f && absVelocity <= 34f) {
                rhythmScore = 88;
            } else if (absVelocity > 34f) {
                rhythmScore = Math.max(50, 88 - clampToInt((absVelocity - 34f) * 1.3f, 0, 38));
            } else if (flexIndex > 12) {
                rhythmScore = Math.max(55, 80 - clampToInt((12f - absVelocity) * 2.5f, 0, 26));
            } else {
                rhythmScore = 78;
            }
        }

        int standardScore = idle
                ? 88
                : clampToInt(depthScore * 0.45 + stabilityScore * 0.35 + rhythmScore * 0.20, 0, 100);

        String riskText;
        if (standardScore >= 85) {
            riskText = getString(R.string.eval_risk_low);
        } else if (standardScore >= 65) {
            riskText = getString(R.string.eval_risk_medium);
        } else {
            riskText = getString(R.string.eval_risk_high);
        }

        boolean useLocalizedAdvice = System.currentTimeMillis() >= 0;
        if (useLocalizedAdvice) {
            String suggestion;
            if (idle) {
                suggestion = getString(R.string.eval_suggestion_idle);
            } else if (depthScore < 55) {
                suggestion = getString(R.string.eval_suggestion_depth);
            } else if (stabilityScore < 68) {
                suggestion = getString(R.string.eval_suggestion_stability);
            } else if (rhythmScore < 68) {
                suggestion = getString(R.string.eval_suggestion_rhythm);
            } else {
                suggestion = getString(R.string.eval_suggestion_good);
            }

            String voiceText;
            boolean shouldSpeak;
            if (idle) {
                voiceText = "";
                shouldSpeak = false;
            } else if (depthScore < 55) {
                voiceText = getString(R.string.eval_voice_depth);
                shouldSpeak = true;
            } else if (stabilityScore < 68) {
                voiceText = getString(R.string.eval_voice_stability);
                shouldSpeak = true;
            } else if (rhythmScore < 68) {
                voiceText = getString(R.string.eval_voice_rhythm);
                shouldSpeak = true;
            } else {
                voiceText = getString(R.string.eval_voice_good);
                shouldSpeak = standardScore < 80;
            }

            return new MotionAssessment(
                    actionLabel,
                    phase,
                    standardScore,
                    riskText,
                    suggestion,
                    voiceText,
                    shouldSpeak
            );
        }

        String suggestion;
        if (idle) {
            suggestion = getString(R.string.eval_suggestion_idle);
        } else if (depthScore < 55) {
            suggestion = "下蹲深度偏浅，建议继续屈膝并保持脚跟稳定。";
        } else if (stabilityScore < 68) {
            suggestion = "动作晃动较明显，建议收紧核心并保持膝关节轨迹稳定。";
        } else if (rhythmScore < 68) {
            suggestion = "下蹲与起身节奏偏急，建议放慢动作速度。";
        } else {
            suggestion = "当前深蹲动作整体稳定，可以继续保持。";
        }

        String voiceText;
        boolean shouldSpeak;
        if (idle) {
            voiceText = "";
            shouldSpeak = false;
        } else if (depthScore < 55) {
            voiceText = "请继续下蹲，达到更稳定的动作深度。";
            shouldSpeak = true;
        } else if (stabilityScore < 68) {
            voiceText = "请收紧核心，减少身体晃动。";
            shouldSpeak = true;
        } else if (rhythmScore < 68) {
            voiceText = "请放慢下蹲和起身速度。";
            shouldSpeak = true;
        } else {
            voiceText = "动作整体稳定，可以继续保持。";
            shouldSpeak = standardScore < 80;
        }

        return new MotionAssessment(
                actionLabel,
                phase,
                standardScore,
                riskText,
                suggestion,
                voiceText,
                shouldSpeak
        );
    }

    private void updateAssessmentViews(MotionAssessment assessment) {
        tvEvalAction.setText(assessment.actionLabel);
        tvEvalPhase.setText(assessment.phase);
        tvEvalScore.setText(getString(R.string.metric_eval_score_value, assessment.standardScore));
        tvEvalRisk.setText(assessment.riskText);
        tvEvalSuggestion.setText(assessment.suggestion);
        if (assessment.standardScore >= 85) {
            tvEvalScore.setTextColor(0xFF2F9D6A);
        } else if (assessment.standardScore >= 65) {
            tvEvalScore.setTextColor(0xFFD2A129);
        } else {
            tvEvalScore.setTextColor(0xFFD65A48);
        }

        if (getString(R.string.eval_risk_low).equals(assessment.riskText)) {
            tvEvalRisk.setTextColor(0xFF2F9D6A);
        } else if (getString(R.string.eval_risk_medium).equals(assessment.riskText)) {
            tvEvalRisk.setTextColor(0xFFD2A129);
        } else if (getString(R.string.eval_risk_high).equals(assessment.riskText)) {
            tvEvalRisk.setTextColor(0xFFD65A48);
        } else {
            tvEvalRisk.setTextColor(0xFF7B6855);
        }
        maybeSpeak(assessment);
    }

    private void maybeSpeak(MotionAssessment assessment) {
        if (!voiceEnabled || !ttsReady || textToSpeech == null || !assessment.shouldSpeak) {
            return;
        }
        if (assessment.voiceText == null || assessment.voiceText.trim().isEmpty()) {
            return;
        }

        long now = System.currentTimeMillis();
        if (assessment.voiceText.equals(lastSpokenText) && now - lastSpokenAtMs < VOICE_COOLDOWN_MS) {
            return;
        }

        textToSpeech.stop();
        textToSpeech.speak(assessment.voiceText, TextToSpeech.QUEUE_FLUSH, null, "fitness_feedback");
        lastSpokenText = assessment.voiceText;
        lastSpokenAtMs = now;
    }

    private int mapToScore(float value, float min, float max) {
        if (value <= min) {
            return 0;
        }
        if (value >= max) {
            return 100;
        }
        return clampToInt(((value - min) / (max - min)) * 100f, 0, 100);
    }

    private int clampToInt(double value, int min, int max) {
        return Math.max(min, Math.min(max, (int) Math.round(value)));
    }

    private static final class MotionAssessment {
        final String actionLabel;
        final String phase;
        final int standardScore;
        final String riskText;
        final String suggestion;
        final String voiceText;
        final boolean shouldSpeak;

        MotionAssessment(
                String actionLabel,
                String phase,
                int standardScore,
                String riskText,
                String suggestion,
                String voiceText,
                boolean shouldSpeak
        ) {
            this.actionLabel = actionLabel;
            this.phase = phase;
            this.standardScore = standardScore;
            this.riskText = riskText;
            this.suggestion = suggestion;
            this.voiceText = voiceText;
            this.shouldSpeak = shouldSpeak;
        }
    }
}
