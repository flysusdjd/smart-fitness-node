# 项目代码技术难点深挖与严格答辩问答

这份文档是给最终检查和严格答辩准备的“代码深挖版”。

它不是普通项目说明，而是专门回答下面这类问题：

- 老师追问某个模块为什么这样设计。
- 老师要求你把某段代码从输入讲到输出。
- 老师问某个 Python / Java / BLE / WebSocket 语法在项目里到底怎么起作用。
- 老师故意问得很细，比如 `self`、`await`、`Notify`、`setOnClickListener`、`sessionmaker`、`predict_proba` 是什么意思。

---

## 1. 这份文档怎么用

建议这样用：

1. 先看第 2 节和第 3 节，把整条数据链路建立起来。
2. 再看第 4 到第 15 节，把每个难点模块单独吃透。
3. 最后看第 16 到第 21 节，直接按问答方式背。

如果老师现场追问代码，不要一上来就讲概念，建议按这个顺序回答：

1. 先说“这个模块在整个系统里的位置”。
2. 再说“输入是什么，输出是什么”。
3. 再说“代码里哪个类 / 哪个函数负责它”。
4. 最后说“为什么这么设计，而不是别的方式”。

---

## 2. 项目整体代码架构

你的项目不是单一程序，而是一个多端协同系统，主要由 5 层组成：

1. 设备端固件层  
ESP32-S3 读取 MPU6050 和柔性传感器数据，把数据打包成一行 CSV 字符串，通过 BLE Notify 发出去。

2. 网关采集与推理层  
PC 网关使用 Python + Bleak 连接 BLE，接收实时数据包，写 CSV，驱动推理模型和动作评估逻辑。

3. 服务接口层  
FastAPI 对外提供 HTTP API 和 WebSocket，让网页和安卓可以拿到状态、报告、训练结果。

4. 用户交互层  
网页前端使用单页应用路由；安卓端使用 Activity + 多页面视图切换。

5. 数据与模型层  
原始数据主要保存在 CSV，结构化信息保存在 MySQL，训练模型由 `ml_pipeline` 生成并用 `joblib` 保存。

一句话概括：

`ESP32-S3 采集 -> BLE Notify -> Python 网关 -> 推理/评估 -> API/WebSocket -> 网页/安卓显示 -> 数据库存档`

---

## 3. 从一条传感器数据进入系统开始，完整代码链路是什么

### 3.1 设备端发数据

文件位置：

- [ESPS3.ino](</C:/Users/flysusdjd/Documents/New project 3/ESPS3/ESPS3.ino>)

关键逻辑：

- `loop()` 中周期性读取 IMU 和柔性传感器。
- 把数据拼成：

```text
seq,timestampMs,ax,ay,az,gx,gy,gz,flexRawAdc,flexRawMv,flexIndex
```

- 调用：

```cpp
pCharacteristic->setValue(data.c_str());
pCharacteristic->notify();
```

这里的本质是：

- `setValue`：把这次采样的数据放进 BLE 特征值。
- `notify`：主动推送给已经订阅该特征值的客户端。

### 3.2 PC 网关接收 BLE Notify

文件位置：

- [service.py](</C:/Users/flysusdjd/Documents/New project 3/pc_gateway/service.py>)

关键流程：

- `connect()` 里执行：

```python
await client.start_notify(config.CHARACTERISTIC_UUID, self._notification_handler)
```

意思是：

- 连接指定 BLE 特征值。
- 以后特征值一有新数据，就自动调用 `self._notification_handler`。

### 3.3 回调函数把原始字节变成字符串

关键函数：

- `GatewayService._notification_handler()`

它会做这件事：

```python
payload = bytes(data).decode("utf-8", errors="ignore").strip()
asyncio.create_task(self._process_packet(payload))
```

解释：

- `data` 原本是 BLE 传来的字节数组。
- `decode("utf-8")` 把字节变成字符串。
- `strip()` 去掉首尾空白。
- `asyncio.create_task(...)` 不阻塞当前 BLE 回调，而是把真正的处理工作放进异步任务。

### 3.4 把字符串解析成结构化对象

文件位置：

- [models.py](</C:/Users/flysusdjd/Documents/New project 3/pc_gateway/models.py>)

关键函数：

- `SensorPacket.from_payload(payload, received_time_ms)`

它会：

1. 按逗号切分字符串。
2. 检查字段数是不是预期的 11 个。
3. 转成整数。
4. 组装成 `SensorPacket` 对象。

这样做的好处是，后面所有模块都不用再手动下标取值，而是直接写：

- `packet.ax`
- `packet.flex_index`
- `packet.timestamp_ms`

### 3.5 如果正在采集，就写入 CSV

文件位置：

- [recorder.py](</C:/Users/flysusdjd/Documents/New project 3/pc_gateway/recorder.py>)

在 `GatewayService._process_packet()` 里：

```python
self._recorder.write_packet(packet)
```

`SessionRecorder.write_packet()` 会把当前包写进正在采集的会话文件里。

### 3.6 把数据送进推理引擎

文件位置：

- [inference.py](</C:/Users/flysusdjd/Documents/New project 3/pc_gateway/inference.py>)

在 `service.py` 里：

```python
prediction = self._inference.consume_packet(packet)
```

意思是：

- 每来一个包，就塞进推理缓冲区。
- 缓冲区够一个窗口大小后，就提取特征并调用模型预测。

### 3.7 把推理结果送进评估引擎

文件位置：

- [evaluation.py](</C:/Users/flysusdjd/Documents/New project 3/pc_gateway/evaluation.py>)

在 `service.py` 里：

```python
self._status.evaluation = self._evaluation.consume(
    packet,
    inference_status=self._status.inference,
)
```

评估引擎不是分类模型，它主要做：

- 动作阶段判断
- 深度评分
- 稳定性评分
- 节奏评分
- 风险提示
- 纠正建议

### 3.8 推送给网页

还是在 `service.py` 里，处理完成后会广播：

```python
await self._broadcast("packet", packet.to_event_dict())
await self._broadcast("inference_status", self._status.inference)
await self._broadcast("evaluation_status", self._status.evaluation)
```

然后前端 WebSocket 收到后更新页面。

---

## 4. 难点一：为什么 `GatewayService` 是整个后端核心

文件位置：

- [service.py](</C:/Users/flysusdjd/Documents/New project 3/pc_gateway/service.py>)

### 4.1 它的职责

`GatewayService` 是系统的“中控层”。

它统一协调：

- BLE 扫描与连接
- 数据采集
- 推理
- 评估
- 数据库存档
- WebSocket 推送
- 模型训练任务

### 4.2 为什么不把这些逻辑全写在 `api.py`

因为 `api.py` 适合做“接口入口”，不适合做“大量业务逻辑”。

如果都写进 `api.py`，会出现：

- 接口函数过长
- BLE、数据库、模型训练逻辑混在一起
- 很难复用
- 很难测试

所以这个项目采用的是：

- `api.py`：负责“接收请求、返回响应”
- `service.py`：负责“真正做事”

### 4.3 `self` 是什么

`self` 不是 Python 关键字，但它是类实例方法里的约定写法，表示“当前这个对象自己”。

例如：

```python
self._recorder = SessionRecorder(self._data_root)
self._inference = InferenceEngine()
```

意思是：

- 当前这个 `GatewayService` 对象，拥有一个 `_recorder`
- 当前这个 `GatewayService` 对象，拥有一个 `_inference`

### 4.4 老师可能问

问：为什么 `GatewayService` 里要同时保存 `_recorder`、`_inference`、`_evaluation`？  
答：因为一条实时数据到达后，网关需要在同一条处理链上同时完成存储、识别和评估。把这些组件集中在服务层统一协调，能保证状态一致。

问：为什么这里用了以下划线开头的成员？  
答：以下划线是 Python 的约定，表示这是内部实现细节，不建议外部直接访问。

---

## 5. 难点二：Python 异步 `async/await` 在项目里是怎么工作的

文件位置：

- [service.py](</C:/Users/flysusdjd/Documents/New project 3/pc_gateway/service.py>)
- [api.py](</C:/Users/flysusdjd/Documents/New project 3/pc_gateway/api.py>)

### 5.1 `async def` 是什么

`async def` 定义的是异步函数，也叫协程函数。

比如：

```python
async def connect(...)
async def _process_packet(...)
async def live_stream(...)
```

它们适合处理：

- I/O 操作
- 网络请求
- BLE 读写
- WebSocket 发送
- 子进程执行

### 5.2 `await` 是什么

`await` 的意思是：

- “这里要等一个异步操作完成”
- “等待期间，事件循环可以先去处理别的任务”

例如：

```python
await client.start_notify(...)
await websocket.send_json(message)
await self._broadcast(...)
```

### 5.3 为什么这个项目适合异步

因为你的项目天然就是多 I/O 并发场景：

- BLE 实时收包
- 网页 WebSocket 推送
- 用户点击 API
- 模型训练子进程
- 数据库存取

### 5.4 `asyncio.create_task` 为什么重要

在 `_notification_handler()` 里：

```python
asyncio.create_task(self._process_packet(payload))
```

这表示：

- BLE 回调先尽快返回
- 真正耗时的解析、写文件、推理、广播放到异步任务里做

### 5.5 老师可能问

问：为什么不用多线程？  
答：这个项目的核心压力主要是 I/O，不是高 CPU 计算，所以优先使用异步编程。异步可以让 BLE、WebSocket、HTTP 请求在同一个事件循环里高效协调。

问：`await` 会不会让程序停住？  
答：当前协程会等待，但事件循环不会停住，其他协程还能继续跑。

---

## 6. 难点三：WebSocket 推送为什么比轮询更适合你的项目

文件位置：

- [api.py](</C:/Users/flysusdjd/Documents/New project 3/pc_gateway/api.py>)
- [service.py](</C:/Users/flysusdjd/Documents/New project 3/pc_gateway/service.py>)
- [app.js](</C:/Users/flysusdjd/Documents/New project 3/pc_gateway/static/app.js>)

### 6.1 后端 WebSocket 入口

`api.py` 里：

```python
@app.websocket("/ws/live")
async def live_stream(websocket: WebSocket) -> None:
    await websocket.accept()
    queue = await gateway_service.subscribe()
```

解释：

- `@app.websocket("/ws/live")` 表示这是一个 WebSocket 路由。
- `websocket.accept()` 表示接受连接。
- `gateway_service.subscribe()` 为这个前端连接分配一个消息队列。

### 6.2 前端怎么连上

`app.js` 里：

```javascript
const socket = new WebSocket(`${protocol}//${window.location.host}/ws/live`);
```

然后：

```javascript
socket.addEventListener("message", (event) => {
  const message = JSON.parse(event.data);
});
```

### 6.3 为什么不用前端每秒请求一次

如果用轮询，会出现：

- 数据延迟更大
- 请求次数更多
- 页面更容易抖动
- 实时动作反馈不自然

### 6.4 `_broadcast()` 是怎么工作的

`service.py` 里：

```python
async def _broadcast(self, event: str, data: Any) -> None:
    dead_queues: list[asyncio.Queue[dict[str, Any]]] = []
    for queue in self._subscribers:
        try:
            queue.put_nowait({"event": event, "data": data})
        except asyncio.QueueFull:
            dead_queues.append(queue)

    for queue in dead_queues:
        self._subscribers.discard(queue)
```

这一段要能讲清：

- `self`：当前 `GatewayService` 对象自己。
- `_broadcast`：内部广播函数。
- `event`：事件名，比如 `"packet"`、`"prediction"`、`"status"`。
- `data`：事件对应的数据内容。
- `self._subscribers`：所有已订阅前端连接对应的队列集合。
- `queue.put_nowait(...)`：把消息放进队列，但不阻塞等待。
- `QueueFull`：如果某个前端长时间不消费消息，它的队列可能满了。

### 6.5 为什么这里要先入队，而不是直接发 WebSocket

因为 service 层不应该直接依赖某个具体前端连接。

更好的结构是：

- service 层只负责“广播事件到队列”
- api 层负责“把队列消息发给 WebSocket”

### 6.6 老师可能问

问：为什么每个客户端都要一个队列？  
答：因为每个客户端消费速度不同，独立队列可以避免一个慢客户端拖累所有客户端。

问：为什么 `put_nowait` 不阻塞？  
答：因为实时系统不希望因为某个前端卡住而阻塞整个网关广播链路。

---

## 7. 难点四：BLE Notify 为什么是项目里的关键技术

文件位置：

- [ESPS3.ino](</C:/Users/flysusdjd/Documents/New project 3/ESPS3/ESPS3.ino>)
- [service.py](</C:/Users/flysusdjd/Documents/New project 3/pc_gateway/service.py>)
- [MainActivity.java](</C:/Users/flysusdjd/Documents/New project 3/esp32s3/app/src/main/java/com/example/esp32s3/MainActivity.java>)

### 7.1 Notify 是什么

BLE Notify 是一种“外设主动推送数据”的机制。

你的 ESP32-S3 是 BLE 外设，PC 网关和安卓是 BLE 客户端。

流程是：

1. 客户端先订阅某个 Characteristic。
2. 设备端数据一更新，就 `notify()`。
3. 客户端自动收到回调。

### 7.2 为什么不用 Read

因为 Read 是“客户端来问一次，设备回一次”。

你的场景是实时连续数据流，更适合 Notify：

- 延迟低
- 开销小
- 代码逻辑更自然

### 7.3 PC 端怎么订阅 Notify

在 `service.py`：

```python
await client.start_notify(config.CHARACTERISTIC_UUID, self._notification_handler)
```

### 7.4 安卓端怎么订阅 Notify

在 `MainActivity.java` 的 GATT 回调中：

```java
gatt.setCharacteristicNotification(characteristic, true);
gatt.writeDescriptor(descriptor, BluetoothGattDescriptor.ENABLE_NOTIFICATION_VALUE);
```

本质是两步：

1. 本地告诉安卓系统“我要监听这个特征值”
2. 向远端设备写 CCCD 描述符，通知 ESP32“请开始发通知”

### 7.5 老师可能问

问：为什么 BLE 传的是字符串，不是二进制结构体？  
答：字符串更便于串口打印、调试、跨平台联调，也更方便网页和 CSV 直接复用。代价是效率略低，但对当前采样频率足够。

问：UUID 有什么作用？  
答：UUID 是 BLE 服务和特征值的唯一标识，客户端靠它找到正确的数据通道。

---

## 8. 难点五：`SensorPacket` 为什么必须存在

文件位置：

- [models.py](</C:/Users/flysusdjd/Documents/New project 3/pc_gateway/models.py>)

### 8.1 它是什么

`SensorPacket` 是后端的统一数据对象。

它把一条字符串数据转换成带语义的结构：

- `seq`
- `timestamp_ms`
- `ax/ay/az`
- `gx/gy/gz`
- `flex_raw_adc`
- `flex_raw_mv`
- `flex_index`

### 8.2 为什么不能直接用 `payload.split(",")`

当然可以，但那样后续所有地方都会写：

```python
parts[2]
parts[3]
parts[10]
```

问题是：

- 可读性差
- 容易取错下标
- 复用困难
- 不利于统一校验

### 8.3 它还负责两个方向的转换

1. `to_event_dict()`：发给前端时转成 JSON 风格字典。
2. `to_csv_row()`：写采集文件时转成 CSV 行结构。

### 8.4 老师可能问

问：为什么 `from_payload()` 要检查字段数？  
答：因为 BLE 数据可能出现异常包，提前校验可以避免坏数据污染后续推理和文件存储。

---

## 9. 难点六：采集模块 `SessionRecorder` 的核心价值是什么

文件位置：

- [recorder.py](</C:/Users/flysusdjd/Documents/New project 3/pc_gateway/recorder.py>)

### 9.1 它做了什么

`SessionRecorder` 管理一次采集会话的完整生命周期：

- 创建会话目录和文件
- 记录当前会话信息
- 写 CSV 表头
- 每来一个包就写一行
- 停止时写元数据

### 9.2 为什么要有 `active_session`

因为系统需要知道当前是否正在采集，以及当前采集属于哪一组。

### 9.3 为什么原始数据存 CSV，不直接全进数据库

这是很重要的设计点：

- 原始传感器数据量大、频率高
- 直接全部入 MySQL 写入压力更大
- 训练前还要重新导出
- CSV 对时序分析更直观

所以采用：

- 原始时序数据：CSV
- 结构化业务信息：MySQL

### 9.4 老师可能问

问：为什么停止采集后还要写 metadata？  
答：因为除了原始时序数据，还要保留采集标签、开始结束时间、备注、路径、停止原因等上下文信息，便于后续训练和追踪。

---

## 10. 难点七：机器学习训练管线到底做了什么

文件位置：

- [prepare_dataset.py](</C:/Users/flysusdjd/Documents/New project 3/ml_pipeline/prepare_dataset.py>)
- [train_baseline.py](</C:/Users/flysusdjd/Documents/New project 3/ml_pipeline/train_baseline.py>)

### 10.1 `prepare_dataset.py` 不是训练模型，而是“准备训练数据”

它的核心步骤是：

1. 读取 `raw` 目录下各标签 CSV
2. 校验字段
3. 按窗口切片
4. 提取统计特征
5. 生成 `label_map.json`
6. 生成 `train/val/test` 拆分文件

### 10.2 什么叫滑动窗口

比如：

- `window_size = 20`
- `step_size = 5`

意思是：

- 每 20 条连续数据看成一个样本窗口
- 每次向前滑 5 条，再取下一个窗口

### 10.3 你提取了哪些特征

对每个信号通道：

- `mean`
- `std`
- `min`
- `max`
- `ptp`
- `rms`

通道包括：

- `ax, ay, az`
- `gx, gy, gz`
- `flexIndex`

### 10.4 为什么这样做

因为你当前项目的数据量、算力和工程复杂度更适合传统机器学习。

优点：

- 数据量要求低
- 训练快
- 更容易解释
- 网关端部署简单

### 10.5 `train_baseline.py` 做什么

它负责：

1. 读入 `train.csv / val.csv / test.csv`
2. 选择特征列
3. 训练 `RandomForestClassifier`
4. 评估精度
5. 保存 `random_forest_model.joblib`
6. 保存训练指标

### 10.6 为什么选随机森林

因为：

- 对中小数据集表现稳定
- 不需要复杂特征归一化
- 训练和推理速度都可以接受
- 输出类别概率，便于前端展示置信度

### 10.7 `joblib` 的作用

`joblib.dump(...)` 把训练好的模型、特征列、标签映射、数据集元信息一起保存到文件。

### 10.8 老师可能问

问：为什么不是深度学习？  
答：当前项目样本量有限，且目标是快速构建可落地原型。随机森林配合窗口统计特征已经能支持现阶段动作识别任务，而且更容易解释和部署。

问：为什么要按文件拆分训练/验证/测试，而不是按行随机拆分？  
答：按文件拆分更严格，可以避免同一采集文件的相邻窗口同时落入训练和测试，减少数据泄漏。

---

## 11. 难点八：推理引擎 `InferenceEngine` 的本质逻辑

文件位置：

- [inference.py](</C:/Users/flysusdjd/Documents/New project 3/pc_gateway/inference.py>)

### 11.1 它不是一来一条就立刻预测

核心结构：

```python
self._buffer: deque[SensorPacket] = deque(maxlen=self._window_size)
```

### 11.2 为什么必须有缓冲区

因为模型训练时用的是“窗口特征”，不是单点特征。

### 11.3 `consume_packet()` 做了什么

它的流程是：

1. 新包入队
2. 判断缓冲区是否够长
3. 调用 `_build_feature_row()`
4. 构造 `DataFrame`
5. 执行 `model.predict(...)`
6. 如果模型支持概率，再调 `predict_proba(...)`
7. 生成最新预测结果字典

### 11.4 为什么要保留 `feature_columns`

因为训练时和推理时的特征顺序必须完全一致。

### 11.5 `predict_proba` 的意义

如果模型支持概率输出，就可以给出：

- 主预测标签
- 置信度
- Top-N 候选标签

### 11.6 老师可能问

问：为什么 `consume_packet()` 可能返回 `None`？  
答：因为缓冲区还没凑够一个窗口时，还不能做预测。

问：推理失败时怎么办？  
答：引擎会捕获异常并记录 `lastError`，同时系统状态继续运行，避免整个网关崩溃。

---

## 12. 难点九：评估引擎 `EvaluationEngine` 为什么和推理引擎分开

文件位置：

- [evaluation.py](</C:/Users/flysusdjd/Documents/New project 3/pc_gateway/evaluation.py>)

### 12.1 分类和评估不是一回事

推理引擎回答的问题是：

- “现在更像什么动作？”

评估引擎回答的问题是：

- “这个动作做得标不标准？”
- “有没有风险？”
- “应该怎么纠正？”

### 12.2 评估引擎当前是规则驱动

不是机器学习模型。

它会根据：

- `flexIndex`
- 陀螺仪幅值
- 加速度稳定性
- 当前动作类别

计算：

- `depthScore`
- `stabilityScore`
- `rhythmScore`
- `standardScore`
- `compensationRisk`
- `suggestions`

### 12.3 为什么这样设计合理

因为当前项目的“标准度评分”和“代偿检测”数据标注很难大量获得，所以先用规则引擎做中间版本更可解释、更容易展示。

### 12.4 老师可能问

问：为什么分类模型和评分模型不合并？  
答：动作类别识别和动作质量评估是两个不同任务。前者是分类问题，后者更接近规则评估或回归评分，拆开后更清晰也更利于后续升级。

---

## 13. 难点十：FastAPI、Pydantic、Uvicorn 在你的项目里分别干什么

文件位置：

- [api.py](</C:/Users/flysusdjd/Documents/New project 3/pc_gateway/api.py>)
- [schemas.py](</C:/Users/flysusdjd/Documents/New project 3/pc_gateway/schemas.py>)
- [main.py](</C:/Users/flysusdjd/Documents/New project 3/pc_gateway/main.py>)

### 13.1 FastAPI 是什么

FastAPI 是你的后端 Web 框架，负责：

- 注册 HTTP 路由
- 注册 WebSocket 路由
- 接收前端请求
- 返回 JSON

### 13.2 Pydantic 是什么

`schemas.py` 里的类是请求数据模型，负责：

- 定义字段
- 校验类型
- 校验范围

例如：

```python
window_size: int = Field(default=20, ge=5, le=200)
```

### 13.3 Uvicorn 是什么

Uvicorn 是 ASGI 服务器，负责真正把 FastAPI 应用跑起来。

### 13.4 老师可能问

问：为什么要用 Pydantic，不直接收原始 JSON？  
答：因为 Pydantic 能自动做类型校验和参数约束，减少无效输入进入业务层，提高接口稳定性。

问：`@app.get` 这种写法是什么？  
答：这是 Python 装饰器，用来把下面的函数注册成某个路由处理函数。

---

## 14. 难点十一：数据库层为什么分成 `db.py`、`db_models.py`、`db_service.py`

文件位置：

- [db.py](</C:/Users/flysusdjd/Documents/New project 3/pc_gateway/db.py>)
- [db_models.py](</C:/Users/flysusdjd/Documents/New project 3/pc_gateway/db_models.py>)
- [db_service.py](</C:/Users/flysusdjd/Documents/New project 3/pc_gateway/db_service.py>)

### 14.1 `db.py`

作用是数据库基础设施：

- 建 `engine`
- 建 `sessionmaker`
- 提供 `session_scope()`
- 初始化表
- 做健康检查

### 14.2 `db_models.py`

作用是 ORM 表结构定义。

比如：

- `User`
- `UserToken`
- `Device`
- `SensorSession`
- `ModelVersion`
- `EvaluationResult`
- `TrainingReport`

### 14.3 `db_service.py`

作用是数据库业务逻辑：

- 用户注册登录
- token 管理
- 会话入库
- 评估结果入库
- 报告汇总
- 模型版本同步

### 14.4 ORM 是什么

ORM 是对象关系映射，意思是：

- Python 类对应数据库表
- Python 对象对应数据库记录

### 14.5 `sessionmaker` 是什么

它是 SQLAlchemy 的会话工厂。

### 14.6 老师可能问

问：为什么数据库里不存全部原始传感器点？  
答：因为原始高频时序数据更适合 CSV，本项目把数据库主要用于结构化业务数据，如用户、采集会话、评估结果、报告和模型版本。

问：`safe_` 前缀函数是干什么的？  
答：表示安全调用包装。即使数据库没启用或某次数据库操作失败，也不会直接拖垮主采集和推理流程。

---

## 15. 难点十二：网页前端为什么能像多页面一样切换

文件位置：

- [app.js](</C:/Users/flysusdjd/Documents/New project 3/pc_gateway/static/app.js>)
- [index.html](</C:/Users/flysusdjd/Documents/New project 3/pc_gateway/static/index.html>)

### 15.1 你的网页本质是单页应用

`app.js` 开头定义了：

```javascript
const ROUTES = ["/login", "/dashboard", "/training", "/history", "/debug"];
```

### 15.2 页面切换怎么实现

核心函数：

```javascript
function navigate(route, replace = false) {
  const target = ROUTES.includes(route) ? route : "/login";
  window.history[replace ? "replaceState" : "pushState"]({}, "", target);
  renderAll();
}
```

### 15.3 真正决定显示哪个页面的是 `renderRoute()`

它根据当前路径控制不同页面容器显示或隐藏。

### 15.4 为什么用户点击按钮后像跳页

因为很多按钮事件最终都调用 `navigate(...)`。

### 15.5 WebSocket 怎么接到前端状态里

`openSocket()` 创建：

```javascript
const socket = new WebSocket(`${protocol}//${window.location.host}/ws/live`);
```

再在 `message` 事件里更新全局 `state`。

### 15.6 老师可能问

问：为什么不拆成多个 HTML 文件？  
答：单页应用能更方便共享实时状态、减少页面跳转闪烁，也更适合 WebSocket 驱动的实时训练场景。

---

## 16. 难点十三：安卓端页面切换逻辑和电脑网页有什么区别

文件位置：

- [AuthActivity.java](</C:/Users/flysusdjd/Documents/New project 3/esp32s3/app/src/main/java/com/example/esp32s3/AuthActivity.java>)
- [MainActivity.java](</C:/Users/flysusdjd/Documents/New project 3/esp32s3/app/src/main/java/com/example/esp32s3/MainActivity.java>)
- [SessionManager.java](</C:/Users/flysusdjd/Documents/New project 3/esp32s3/app/src/main/java/com/example/esp32s3/SessionManager.java>)

### 16.1 安卓不是网页路由，它主要是 Activity + View 切换

登录页：

- `AuthActivity`

主页面：

- `MainActivity`

### 16.2 登录成功如何跳转

`AuthActivity` 中：

```java
Intent intent = new Intent(this, MainActivity.class);
startActivity(intent);
finish();
```

### 16.3 `setOnClickListener` 是什么

它是 Android View 的点击事件绑定方法。

例如：

```java
btnLogin.setOnClickListener(v -> submitLogin());
```

### 16.4 主页面内部的“多页面”怎么做

`MainActivity` 里有：

- `pageHome`
- `pageTraining`
- `pageGuide`
- `pageReport`
- `pageSettings`

切换函数：

```java
private void showAppPage(String page)
```

内部通过：

```java
pageView.setVisibility(visible ? View.VISIBLE : View.GONE);
```

来控制每个页面显示或隐藏。

### 16.5 `SharedPreferences` 在这里干什么

`SessionManager` 负责保存：

- 后端地址
- 登录 token
- token 过期时间
- 用户名
- 游客模式
- 语音开关

### 16.6 老师可能问

问：为什么安卓端不用网页 WebSocket，而是直接 BLE？  
答：因为安卓端当前主要承担移动训练终端角色，直接连 ESP32-S3 可以降低路径复杂度并减少对 PC 网关的依赖。

问：手机和电脑账户为什么能互通？  
答：因为它们都访问同一个后端认证接口和同一个数据库，用户数据不是存在本地，而是统一由服务端管理。

---

## 17. 难点十四：ESP32-S3 固件里最有技术含量的部分是什么

文件位置：

- [ESPS3.ino](</C:/Users/flysusdjd/Documents/New project 3/ESPS3/ESPS3.ino>)

### 17.1 固件不只是“读传感器然后发出去”

真正有技术含量的是：

1. BLE 服务和特征值初始化
2. MPU6050 初始化与故障容错
3. 柔性传感器基线校准
4. 信号平滑
5. 基线动态跟踪
6. 弯曲指数归一化
7. 周期性打包发送

### 17.2 柔性传感器为什么要校准基线

因为每次佩戴、每个人腿型、贴合程度都不完全一样，所以启动时先采集自然状态作为基线。

### 17.3 为什么要做平滑

代码里：

```cpp
smoothedFlexMv = smoothedFlexMv +
                 ((float)rawVoltageMv - smoothedFlexMv) * FLEX_SIGNAL_SMOOTH_ALPHA;
```

这是指数平滑，作用是降低抖动。

### 17.4 为什么要做基线动态跟踪

长时间佩戴时传感器可能有慢漂移，所以系统在小幅变化时会缓慢更新基线。

### 17.5 `flexIndex` 是什么

它不是原始 ADC，也不是原始毫伏值，而是归一化后的弯曲程度指数，更适合前端显示和模型输入。

### 17.6 老师可能问

问：为什么要从 `rawAdc -> rawMv -> flexIndex` 走三层表示？  
答：`rawAdc` 贴近硬件，`rawMv` 便于校准和分析，`flexIndex` 便于业务展示和模型使用。

---

## 18. 难点十五：异常处理为什么很关键

这个项目不是离线脚本，而是实时系统，所以异常处理是答辩加分点。

### 18.1 BLE 断开

`service.py` 里有：

- `_on_ble_disconnect`
- `_handle_disconnect`

### 18.2 数据包格式错误

`SensorPacket.from_payload()` 会在字段数不对时抛异常，`_process_packet()` 里会捕获并广播错误。

### 18.3 数据库不可用

`db_service.py` 里很多操作有 `safe_` 包装，数据库失败时尽量降级，不影响核心采集与推理链路。

### 18.4 模型还没训练好

`InferenceEngine.load_model()` 如果模型文件不存在，会记录状态而不是让整个服务起不来。

### 18.5 队列满

`_broadcast()` 中如果某个前端队列满了，会把它移除，避免拖慢整体系统。

---

## 19. Python 语法细问答

### 19.1 `self` 是什么

表示当前对象本身。类的方法通过 `self` 访问自己的属性和其他方法。

### 19.2 `def` 和 `async def` 的区别

- `def`：普通函数
- `async def`：异步协程函数

### 19.3 `-> dict[str, Any]` 是什么

是返回值类型标注，表示“这个函数预期返回字典，键是字符串，值可以是任意类型”。

### 19.4 `Path | None` 是什么

表示联合类型：要么是 `Path`，要么是 `None`。

### 19.5 `list[str]` 是什么

表示列表里的元素应当是字符串。

### 19.6 `@app.get` 是什么

装饰器，用来把函数注册成某个 HTTP GET 接口。

### 19.7 `try/except` 的作用

捕获异常，避免程序直接崩溃。

### 19.8 `deque(maxlen=20)` 是什么

双端队列，最多保留 20 个元素，超出时自动丢弃最旧元素。

### 19.9 `Field(..., ge=1, le=30)` 是什么

Pydantic 字段约束，表示这个值必须在 1 到 30 之间。

### 19.10 `lambda` 是什么

匿名函数，常用于短小回调或延迟执行表达式。

---

## 20. Java / Android 语法细问答

### 20.1 `setOnClickListener` 是什么

Android 组件的点击事件绑定方法。按钮被点击时执行指定逻辑。

### 20.2 `Intent` 是什么

安卓组件之间的跳转或通信意图对象。这里主要用于页面跳转。

### 20.3 `View.VISIBLE` 和 `View.GONE` 的区别

- `VISIBLE`：显示
- `GONE`：隐藏并且不占布局空间

### 20.4 `SharedPreferences` 是什么

安卓轻量本地存储，适合保存登录状态、配置项、简单开关。

### 20.5 `BluetoothGattCallback` 是什么

BLE GATT 通讯回调类，用于接收连接状态、服务发现、通知数据等事件。

### 20.6 `TextToSpeech.OnInitListener` 是什么

TTS 初始化回调接口，系统会告诉你语音引擎是否准备好了。

---

## 21. 严格答辩高频问答库

### 21.1 关于整体架构

问：你的项目最核心的一条数据链路是什么？  
答：ESP32-S3 读取 IMU 和柔性传感器数据，通过 BLE Notify 实时发送；PC 网关用 Bleak 接收并解析为 `SensorPacket`；若正在采集则写入 CSV，同时送入 `InferenceEngine` 做动作识别，再送入 `EvaluationEngine` 做标准度评估；结果通过 FastAPI 的 HTTP/WebSocket 给网页和数据库。

问：为什么你这个项目不是单纯的网页项目？  
答：因为它同时涉及嵌入式固件、BLE 通信、实时后端、机器学习训练与推理、数据库、网页前端和安卓移动端，是一个完整的跨端系统。

### 21.2 关于 BLE

问：为什么选择 BLE，不用串口或 Wi-Fi？  
答：BLE 更适合低功耗穿戴式场景，手机原生支持也更好，便于后续做移动训练终端。

问：为什么使用 Notify，不主动轮询读取？  
答：Notify 更适合连续实时数据流，延迟低，链路更自然，客户端无需不断发请求。

### 21.3 关于采集

问：为什么要人为打标签？  
答：因为监督学习训练必须知道每段数据对应的真实动作类别，采集阶段需要标签，用户训练阶段则不需要暴露这个概念。

问：为什么普通用户端不应该看到训练标签？  
答：因为标签是数据工程概念，不是用户产品语言。用户只需要选择动作或直接训练，标签采集和模型维护应放在开发者模式。

### 21.4 关于模型

问：你的模型输入到底是什么？  
答：不是单个原始点，而是一个时间窗口上的统计特征，包括 IMU 和 `flexIndex` 的均值、标准差、最小值、最大值、极差和均方根。

问：你的模型输出是什么？  
答：输出动作类别 id、类别名称、置信度，以及在支持时的候选类别概率。

问：为什么静止可能被识别成深蹲？  
答：通常是训练数据分布、静止样本覆盖不足、佩戴位置变化或标签之间边界不清导致的。模型只会根据它见过的数据分布做判断。

### 21.5 关于评估

问：标准度评分是模型算出来的吗？  
答：当前版本主要由规则评估引擎计算，不是深度模型直接回归出来的。分类模型负责识别动作类别，评分模块负责质量评估。

问：为什么评估模块目前先做规则，不直接做复杂模型？  
答：因为动作标准度和代偿行为的高质量标注成本更高，当前阶段先做可解释、可调试、可演示的规则系统更合理。

### 21.6 关于数据库

问：MySQL 里存了什么？  
答：用户、令牌、设备、采集会话、模型版本、评估结果、训练报告等结构化信息。

问：为什么模型文件不用数据库存？  
答：模型本体以 `joblib` 文件形式保存在文件系统更直接，数据库主要存模型版本元信息和指标。

### 21.7 关于前端

问：网页为什么像多页面，但又只有一个前端入口？  
答：因为它是单页应用，地址变化由 History API 管理，真正显示哪个页面由 `renderRoute()` 控制。

问：为什么实时数据不用一直请求 `/api/status`？  
答：因为 WebSocket 更适合实时流，前端可以持续接收后端主动推送的 `packet`、`prediction`、`evaluation` 事件。

### 21.8 关于安卓

问：手机端为什么可以和电脑共用账户？  
答：因为注册登录都走同一个后端接口，用户数据保存在同一个 MySQL，不依赖本地单机存储。

问：安卓的页面切换为什么不是多个完全独立 Activity？  
答：当前为了控制复杂度，登录使用单独 `AuthActivity`，主功能集中在 `MainActivity` 内部通过视图显隐切换实现。

---

## 22. 如果老师要求你“从代码角度解释项目亮点”，推荐这样答

你可以这样说：

“我这个项目的代码亮点主要有四个。第一是多端链路完整，ESP32-S3、PC 网关、网页端、安卓端和 MySQL 是打通的。第二是后端用了分层设计，`api.py`、`service.py`、`inference.py`、`evaluation.py`、`db_service.py` 职责清晰。第三是实时链路采用 BLE Notify + Python 异步 + WebSocket 推送，能支持连续传感器数据流。第四是机器学习部分采用滑动窗口加统计特征的方式，把原始时序数据转换成适合传统模型训练和部署的结构化特征。”

---

## 23. 如果老师要求你“指出项目当前还不够完美的地方”，推荐这样答

你可以这样说：

1. 当前动作识别模型类别还不够多，样本规模还可以继续扩充。
2. 标准度评估目前以规则引擎为主，后续可以逐步引入更复杂的评估模型。
3. 设备端目前主要负责采集和传输，真正轻量化模型还主要跑在网关和移动端逻辑中。
4. 原始数据与业务数据已经分层，但长期来看还可以进一步完善数据治理和模型版本管理。

---

## 24. 最后给你的答辩建议

老师越问得细，你越不要慌。

你的回答模板可以固定成：

1. “这个模块在系统里是干什么的。”
2. “它对应哪个文件 / 哪个类 / 哪个函数。”
3. “输入是什么，输出是什么。”
4. “为什么这么设计。”

只要你把这四句讲完整，哪怕老师问题很细，也会觉得你是真的理解了代码，而不是只会操作界面。
