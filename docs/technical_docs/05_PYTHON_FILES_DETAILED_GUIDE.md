# Python 代码文件逐个详细说明

本文档专门解释项目里的每一个 `.py` 文件。它比总技术文档更偏代码层，重点回答三个问题：

1. 这个 Python 文件在项目中负责什么？
2. 文件里的每个类、函数、常量分别做什么？
3. 老师如果追问代码细节，应该怎么回答？

当前项目内业务 Python 文件主要有 20 个：

| 序号 | 文件 |
|---:|---|
| 1 | `pc_gateway/__init__.py` |
| 2 | `pc_gateway/__main__.py` |
| 3 | `pc_gateway/main.py` |
| 4 | `pc_gateway/config.py` |
| 5 | `pc_gateway/api.py` |
| 6 | `pc_gateway/service.py` |
| 7 | `pc_gateway/models.py` |
| 8 | `pc_gateway/recorder.py` |
| 9 | `pc_gateway/inference.py` |
| 10 | `pc_gateway/evaluation.py` |
| 11 | `pc_gateway/advanced_evaluation.py` |
| 12 | `pc_gateway/reporting.py` |
| 13 | `pc_gateway/db.py` |
| 14 | `pc_gateway/db_models.py` |
| 15 | `pc_gateway/db_service.py` |
| 16 | `pc_gateway/schemas.py` |
| 17 | `pc_gateway/db_schemas.py` |
| 18 | `pc_gateway/security.py` |
| 19 | `ml_pipeline/prepare_dataset.py` |
| 20 | `ml_pipeline/train_baseline.py` |

---

## 1. Python 后端整体调用关系

### 1.1 启动链路

```text
python -m pc_gateway
    -> pc_gateway/__main__.py
        -> pc_gateway/main.py
            -> import pc_gateway.api
                -> 创建 FastAPI app
                -> 创建 GatewayService
            -> uvicorn.run("pc_gateway.api:app")
```

解释：

- `__main__.py` 是 Python 包启动入口。
- `main.py` 负责真正启动服务。
- `api.py` 定义 FastAPI 路由。
- `api.py` 中创建 `GatewayService()`。
- `GatewayService` 再组合 BLE、采集、推理、评估、数据库和报告模块。

### 1.2 实时训练链路

```text
ESP32-S3 BLE Notify
    -> service.py 的 _notification_handler()
    -> service.py 的 _process_packet()
    -> models.py 的 SensorPacket.from_payload()
    -> recorder.py 写 CSV
    -> inference.py 做机器学习推理
    -> evaluation.py 做实时评分
    -> advanced_evaluation.py 做高级评估框架
    -> service.py 通过 WebSocket 广播
    -> static/app.js 更新网页
```

### 1.3 模型训练链路

```text
网页调试模式点击训练模型
    -> api.py /api/models/train
    -> service.py start_model_training()
    -> service.py _run_model_training()
    -> ml_pipeline/prepare_dataset.py
    -> ml_pipeline/train_baseline.py
    -> 保存 random_forest_model.joblib
    -> service.py reload_inference_model()
    -> inference.py 重新加载模型
```

### 1.4 数据库链路

```text
网页或安卓注册/登录
    -> api.py /api/auth/register 或 /api/auth/login
    -> service.py register_user/login_user
    -> db_service.py
    -> db.py session_scope
    -> db_models.py ORM 表
    -> MySQL
```

答辩时一句话总结：

> Python 后端采用分层设计：`api.py` 负责接口，`service.py` 负责业务编排，`models.py` 和 `schemas.py` 负责数据结构，`recorder/inference/evaluation/reporting` 分别负责采集、推理、评估和报告，`db/db_service/db_models` 负责 MySQL，`ml_pipeline` 负责离线训练模型。

---

## 2. `pc_gateway/__init__.py`

### 2.1 文件作用

这个文件是 Python 包初始化文件。

路径：

```text
pc_gateway/__init__.py
```

它的作用不是业务逻辑，而是告诉 Python：

> `pc_gateway` 是一个可以被导入的包。

### 2.2 为什么需要它

有了这个文件之后，项目中才能写：

```python
from pc_gateway.main import main
from .service import GatewayService
```

如果没有它，部分 Python 版本或运行方式下，相对导入可能会出问题。

### 2.3 老师可能问

**问：这个文件为什么是空的？**

答：

> 它是包标识文件，主要用于模块组织。现在不需要在包初始化时执行额外逻辑，所以可以为空。

**问：它和 `__main__.py` 有什么区别？**

答：

> `__init__.py` 让目录变成包，`__main__.py` 让这个包可以用 `python -m pc_gateway` 方式运行。

---

## 3. `pc_gateway/__main__.py`

### 3.1 文件作用

这是 `pc_gateway` 包的命令行启动入口。

当运行：

```powershell
python -m pc_gateway
```

Python 会执行：

```text
pc_gateway/__main__.py
```

### 3.2 主要逻辑

文件做了两件事：

| 逻辑 | 说明 |
|---|---|
| 修正 `sys.path` | 如果直接运行包导致相对导入失败，就把项目根目录加入 Python 搜索路径 |
| 调用 `main()` | 从 `pc_gateway.main` 导入并执行启动函数 |

### 3.3 关键代码思想

它判断：

```python
if __package__ in (None, ""):
```

含义是：

> 当前文件可能不是以标准包方式运行，此时需要手动把项目根目录加入 `sys.path`。

这样可以兼容不同启动方式：

```powershell
python -m pc_gateway
python pc_gateway/__main__.py
```

### 3.4 老师可能问

**问：为什么要处理 `sys.path`？**

答：

> 因为 Python 的相对导入依赖包上下文。如果用户用不同方式启动程序，解释器可能找不到 `pc_gateway` 包。这里主动把项目根目录加入 `sys.path`，可以提高启动兼容性。

**问：业务逻辑在这里吗？**

答：

> 不在。这里只是启动桥接，真正启动网关的逻辑在 `main.py`。

---

## 4. `pc_gateway/main.py`

### 4.1 文件定位

`main.py` 是 PC 网关的进程启动器。

它负责：

- 确保项目路径可导入。
- 检查端口是否可用。
- 自动选择端口。
- 检测局域网 IP。
- 预先检查 FastAPI 应用能否导入。
- 自动打开浏览器。
- 启动 Uvicorn 服务。

### 4.2 关键常量

| 常量 | 值 | 作用 |
|---|---:|---|
| `DEFAULT_HOST` | `0.0.0.0` | 监听所有网卡，让手机能通过局域网访问 |
| `DEFAULT_PORT` | `8787` | 默认网关端口 |
| `PORT_SCAN_LIMIT` | `10` | 如果 8787 被占用，最多向后寻找 10 个端口 |

### 4.3 函数逐个说明

#### `_ensure_project_root_on_path()`

作用：

- 找到项目根目录。
- 如果根目录不在 `sys.path` 中，就插入到最前面。

为什么重要：

> FastAPI 启动时需要导入 `pc_gateway.api:app`，如果路径不对，就会报 `ModuleNotFoundError`。

#### `_is_port_available(host, port)`

作用：

- 创建一个 socket。
- 尝试绑定指定 host 和 port。
- 如果绑定成功，说明端口可用。
- 如果抛出 `OSError`，说明端口被占用。

用到的技术：

```python
socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.bind((host, port))
```

#### `_choose_port(host, preferred_port, limit)`

作用：

- 从 `preferred_port` 开始尝试。
- 如果 8787 不可用，就试 8788、8789。
- 找到可用端口就返回。
- 全部失败则抛出错误。

这个函数解释了你之前看到的：

```text
端口 8787 已被占用，已自动切换到 8788
```

#### `_detect_lan_ip()`

作用：

- 通过 UDP socket 连接 `8.8.8.8:80` 来判断本机对外使用的局域网 IP。
- 不是真的向 Google 发数据，只是利用 socket 获取本机出口地址。
- 如果失败，就返回 `127.0.0.1`。

为什么要它：

> 手机 App 不能访问电脑的 `127.0.0.1`，必须访问电脑的局域网 IP，所以启动时打印手机访问地址。

#### `_check_app_importable()`

作用：

- 提前导入 `pc_gateway.api`。
- 如果 `api.py`、`config.py` 或其他后端模块有语法错误，启动阶段就直接报出来。

之前出现过：

```text
NameError: name 'w' is not defined
```

就是在这个导入检查阶段发现的。

#### `_open_browser_later(url)`

作用：

- 用 `threading.Timer` 延迟 1 秒打开浏览器。
- 避免浏览器在 Uvicorn 完全启动前打开导致访问失败。

#### `main()`

这是主入口。

执行顺序：

1. 调用 `_ensure_project_root_on_path()`。
2. 调用 `_choose_port()` 选择端口。
3. 拼出本机访问地址 `http://127.0.0.1:端口/login`。
4. 拼出手机访问地址 `http://局域网IP:端口/login`。
5. 如果端口不是 8787，打印自动切换信息。
6. 调用 `_check_app_importable()` 检查后端可导入。
7. 打印访问地址。
8. 延迟打开浏览器。
9. 调用 `uvicorn.run("pc_gateway.api:app")` 启动服务。
10. 如果启动失败，打印详细错误堆栈。

### 4.4 老师可能问

**问：为什么 host 用 `0.0.0.0`，不是 `127.0.0.1`？**

答：

> `127.0.0.1` 只能本机访问。`0.0.0.0` 表示监听所有网卡，这样手机在同一局域网下才能通过电脑 IP 访问网关。

**问：自动选端口有什么意义？**

答：

> 开发调试时经常有旧进程占用端口。自动选端口可以降低启动失败率，也方便用户继续使用。

**问：局域网 IP 怎么来的？**

答：

> 通过 UDP socket 判断本机默认出口网卡，不依赖外部接口返回结果，只是借助 socket 获取本地 IP。

---

## 5. `pc_gateway/config.py`

### 5.1 文件定位

`config.py` 是全项目 Python 后端的配置中心。

它负责统一管理：

- 项目路径。
- 数据目录。
- 模型路径。
- BLE 设备名和 UUID。
- 默认端口和窗口大小。
- 推荐训练标签。
- MySQL 数据库连接。
- Token 有效期。

### 5.2 为什么要集中配置

如果不集中配置，路径和 UUID 会散落在多个文件中：

- `service.py` 要 BLE UUID。
- `inference.py` 要模型路径。
- `recorder.py` 要数据目录。
- `db.py` 要数据库 URL。
- `api.py` 要默认扫描时间。

集中到 `config.py` 后，修改时只需要改一个地方。

### 5.3 环境变量加载

```python
load_dotenv(PROJECT_ROOT / ".env")
load_dotenv(PROJECT_ROOT / ".env.local", override=True)
```

含义：

- 先读 `.env`。
- 再读 `.env.local`。
- `.env.local` 优先级更高。

这样可以：

- `.env.example` 放模板。
- `.env` 放常规配置。
- `.env.local` 放你电脑私有配置。

### 5.4 函数说明

#### `_get_bool_env(name, default=False)`

作用：

- 从环境变量读取布尔值。
- 支持这些写法表示 True：

```text
1, true, yes, on
```

用途：

- `MYSQL_ENABLED`
- `DATABASE_ECHO`

#### `_build_mysql_url()`

作用：

- 根据 `MYSQL_USER`、`MYSQL_PASSWORD`、`MYSQL_HOST`、`MYSQL_PORT`、`MYSQL_DATABASE` 拼出 SQLAlchemy 数据库 URL。

生成格式类似：

```text
mysql+pymysql://root:password@127.0.0.1:3306/smart_fitness?charset=utf8mb4
```

它使用 `quote_plus()` 处理用户名和密码中的特殊字符。

### 5.5 路径配置

| 配置 | 说明 |
|---|---|
| `PROJECT_ROOT` | 项目根目录 |
| `RAW_DATA_ROOT` | 原始训练 CSV 目录 |
| `PROCESSED_ROOT` | 处理后特征和标签映射目录 |
| `MODELS_ROOT` | 模型保存目录 |
| `MODEL_PATH` | 当前随机森林模型文件 |
| `LABEL_MAP_PATH` | 标签映射文件 |
| `DATASET_META_PATH` | 数据集元信息文件 |
| `ADVANCED_EVAL_PROFILE_PATH` | 高级评估配置文件 |

### 5.6 BLE 配置

| 配置 | 说明 |
|---|---|
| `DEVICE_NAME` | 目标设备名 `ESP32S3_Fitness_BLE` |
| `SERVICE_UUID` | ESP32 BLE 服务 UUID |
| `CHARACTERISTIC_UUID` | 数据 Notify 特征 UUID |

这些必须和 ESP32 固件中的 UUID 保持一致。

### 5.7 推荐标签配置

```python
RECOMMENDED_LABELS = [
    "idle",
    "squat_standard",
    "squat_wrong",
    "bench_standard",
    "bench_wrong",
]
```

含义：

- `idle`：静止。
- `squat_standard`：标准深蹲。
- `squat_wrong`：错误深蹲。
- `bench_standard`：标准卧推。
- `bench_wrong`：错误卧推。

### 5.8 老师可能问

**问：为什么 UUID 要写到配置里？**

答：

> UUID 是手机、PC 和 ESP32 之间的通信契约，集中配置可以保证后端统一使用同一套 UUID，也方便后续更换设备。

**问：为什么数据库 URL 不直接写死？**

答：

> 数据库账号密码属于环境配置，不应该写死在业务代码中。用 `.env` 可以适配不同电脑和后续服务器部署。

---

## 6. `pc_gateway/api.py`

### 6.1 文件定位

`api.py` 是 FastAPI 后端接口层。

它不直接处理复杂业务，而是：

- 接收 HTTP 请求。
- 校验请求参数。
- 调用 `GatewayService`。
- 把业务异常转换为 HTTP 错误。
- 返回 JSON。
- 提供 WebSocket 实时推送。
- 提供网页静态文件入口。

### 6.2 全局对象

#### `gateway_service = GatewayService()`

这是后端业务核心实例。

所有接口基本都调用它。

#### `STATIC_DIR`

指向：

```text
pc_gateway/static
```

用于返回网页 `index.html` 和静态资源。

#### `app = FastAPI(...)`

创建 FastAPI 应用。

标题：

```text
Smart Fitness PC Gateway
```

版本：

```text
0.2.0
```

### 6.3 生命周期函数

#### `lifespan()`

作用：

- FastAPI 启动时进入。
- 应用关闭时调用 `gateway_service.close()`。

为什么重要：

> 如果程序关闭时设备还连接着或正在采集，`close()` 会停止采集并断开 BLE，避免资源悬空。

### 6.4 页面路由

#### `index()`

路由：

```text
GET /
```

作用：

- 自动跳转到 `/login`。

#### `spa_pages()`

路由：

```text
GET /login
GET /dashboard
GET /training
GET /history
GET /debug
```

作用：

- 都返回同一个 `index.html`。
- 前端再根据 URL 判断显示哪个页面。

为什么这么做：

> 这是单页应用 SPA 的常见做法。后端只返回一个入口文件，页面切换由前端 JS 控制。

响应头里设置：

```text
Cache-Control: no-store
```

目的是：

> 开发阶段避免浏览器缓存旧的 JS/CSS，修改前端后刷新能看到新效果。

### 6.5 系统状态 API

#### `health()`

路由：

```text
GET /health
```

返回：

```json
{"status": "ok"}
```

用途：

- 判断网关是否活着。
- 手机端或浏览器可以快速测试连接。

#### `get_status()`

路由：

```text
GET /api/status
```

调用：

```python
gateway_service.get_status()
```

返回：

- 设备是否连接。
- 是否正在采集。
- 最新传感器包。
- 推理状态。
- 评估状态。
- 报告摘要。
- 数据库状态。

### 6.6 标签 API

#### `get_labels()`

路由：

```text
GET /api/labels
```

返回：

- 推荐标签。
- 当前已有标签。
- 每个标签下 CSV 数量。

#### `create_label()`

路由：

```text
POST /api/labels
```

请求模型：

```python
CreateLabelRequest
```

作用：

- 创建标签目录。
- 例如创建 `bench_standard` 后，会生成：

```text
ml_pipeline/data/raw/bench_standard/
```

#### `delete_label(label)`

路由：

```text
DELETE /api/labels/{label}
```

作用：

- 删除某个标签对应的数据目录。
- 同时删除数据库里对应标签的会话记录。

保护逻辑在 `service.py`：

- 当前正在采集这个标签时不能删除。
- 模型正在训练时不能删除。
- 路径必须在 raw 数据目录内。

### 6.7 BLE 设备 API

#### `scan_devices()`

路由：

```text
GET /api/devices/scan
```

参数：

```text
timeout_s
```

作用：

- 调用 Bleak 扫描附近 BLE 设备。
- 返回设备名、地址、RSSI、是否疑似目标设备。

#### `connect_device()`

路由：

```text
POST /api/device/connect
```

请求模型：

```python
ConnectRequest
```

作用：

- 根据地址或设备名连接 ESP32-S3。
- 开启 Notify。

#### `disconnect_device()`

路由：

```text
POST /api/device/disconnect
```

作用：

- 断开 BLE。
- 停止录制。
- 更新状态。

### 6.8 采集记录 API

#### `start_recording()`

路由：

```text
POST /api/recordings/start
```

请求：

- `label`
- `subject_id`
- `notes`

作用：

- 开始一次采集。
- 后续 BLE 数据会写入 CSV。

#### `stop_recording()`

路由：

```text
POST /api/recordings/stop
```

作用：

- 停止当前采集。
- 写入结束时间。
- 保存评估结果和报告快照。

#### `get_active_recording()`

路由：

```text
GET /api/recordings/active
```

作用：

- 查看当前是否有正在进行的采集。

#### `list_recordings()`

路由：

```text
GET /api/recordings
```

作用：

- 列出本地 JSON 元数据记录。
- 调试模式“训练模型记录”依赖它。

#### `delete_recording(session_id)`

路由：

```text
DELETE /api/recordings/{session_id}
```

作用：

- 删除某次采集的 CSV 和 JSON。
- 同时删除数据库会话记录。

### 6.9 推理和评估 API

#### `get_inference_status()`

路由：

```text
GET /api/inference/status
```

返回模型加载状态、窗口大小、最新预测。

#### `get_evaluation_status()`

路由：

```text
GET /api/evaluation/status
```

返回实时评分、动作阶段、纠正建议。

#### `get_advanced_evaluation_status()`

路由：

```text
GET /api/evaluation/server-status
```

返回高级评估框架状态。

#### `reload_inference_model()`

路由：

```text
POST /api/inference/reload
```

作用：

- 重新加载 `random_forest_model.joblib`。
- 重置评估引擎窗口。

### 6.10 模型训练 API

#### `get_model_training_status()`

路由：

```text
GET /api/models/training/status
```

返回：

- 是否正在训练。
- 当前阶段。
- 选择标签。
- 输出日志。
- 最近错误。

#### `start_model_training()`

路由：

```text
POST /api/models/train
```

作用：

- 调用 `prepare_dataset.py`。
- 再调用 `train_baseline.py`。
- 成功后可自动重载模型。

#### `remove_label_from_model()`

路由：

```text
POST /api/models/remove-label
```

作用：

- 不是直接编辑模型文件。
- 而是排除这个标签后，用剩余标签重新训练模型。

#### `reset_model_training_status()`

路由：

```text
POST /api/models/training/reset
```

作用：

- 清空训练状态显示。
- 如果模型正在训练中则不允许清空。

### 6.11 报告 API

#### `get_report_summary()`

路由：

```text
GET /api/report/summary
```

作用：

- 返回本地训练记录汇总。

#### `get_user_dashboard()`

路由：

```text
GET /api/report/user-summary
```

需要：

```text
Authorization: Bearer <token>
```

作用：

- 返回当前登录用户的训练总览。

### 6.12 数据库 API

包括：

| 路由 | 作用 |
|---|---|
| `/api/database/status` | 数据库连接状态 |
| `/api/database/init` | 初始化数据库表 |
| `/api/database/users` | 用户列表 |
| `/api/database/sessions` | 训练会话列表 |
| `/api/database/evaluations` | 评估结果列表 |
| `/api/database/models` | 模型版本列表 |
| `/api/database/reports` | 报告列表 |

这些主要给调试模式使用。

### 6.13 认证 API

#### `register_user()`

路由：

```text
POST /api/auth/register
```

作用：

- 注册用户名密码。
- 调用 `DatabaseService.register_user()`。

#### `login_user()`

路由：

```text
POST /api/auth/login
```

作用：

- 验证用户名密码。
- 返回 token。

#### `get_current_user()`

路由：

```text
GET /api/auth/me
```

作用：

- 根据 Bearer token 返回当前用户。

### 6.14 WebSocket

#### `live_stream(websocket)`

路由：

```text
WS /ws/live
```

逻辑：

1. 接受 WebSocket。
2. 调用 `gateway_service.subscribe()` 创建消息队列。
3. 不断从队列取消息。
4. `send_json()` 发送给前端。
5. 断开后取消订阅。

WebSocket 推送事件包括：

- `status`
- `packet`
- `prediction`
- `inference_status`
- `evaluation_status`
- `advanced_evaluation_status`
- `recording_started`
- `recording_stopped`
- `report_summary`
- `model_training_status`

### 6.15 老师可能问

**问：为什么 `api.py` 不直接写 BLE 和模型逻辑？**

答：

> 为了分层。`api.py` 是接口层，只负责 HTTP/WebSocket；BLE、模型、数据库等业务由 `GatewayService` 管理，这样代码更清晰，也方便后续复用。

**问：为什么很多接口都 try/except 后抛 `HTTPException`？**

答：

> 业务层抛的是 Python 异常，API 层需要把它转换成前端能识别的 HTTP 状态码和 JSON 错误信息。

---

## 7. `pc_gateway/service.py`

### 7.1 文件定位

`service.py` 是整个 PC 网关最核心的业务编排文件。

它相当于“大脑”：

- 管 BLE。
- 管采集。
- 管推理。
- 管评估。
- 管数据库。
- 管报告。
- 管模型训练。
- 管 WebSocket 广播。

### 7.2 顶部常量

#### `NON_MODEL_LABELS`

```python
NON_MODEL_LABELS = {"user_auto_training"}
```

含义：

> `user_auto_training` 是普通用户训练保存标签，不用于训练机器学习模型。

为什么：

> 用户训练不一定是人工标注的准确标签，如果直接拿来训练模型，可能污染训练集。

#### `LABEL_ALIASES`

作用：

- 把中文标签或不同写法统一成内部英文标签。

例如：

| 用户输入 | 内部标签 |
|---|---|
| `静止` | `idle` |
| `站立` | `idle` |
| `深蹲` | `squat_standard` |
| `深蹲错误` | `squat_wrong` |
| `卧推` | `bench_standard` |
| `卧推错误` | `bench_wrong` |

为什么需要：

> 前端可能显示中文，开发者可能输入不同写法，后端统一成固定英文标签，保证目录和模型训练一致。

### 7.3 `GatewayService.__init__()`

初始化所有子模块：

| 成员 | 类型 | 作用 |
|---|---|---|
| `_data_root` | `Path` | 原始数据目录 |
| `_recorder` | `SessionRecorder` | CSV 采集器 |
| `_inference` | `InferenceEngine` | 机器学习推理 |
| `_evaluation` | `EvaluationEngine` | 实时动作评估 |
| `_advanced_evaluation` | `AdvancedEvaluationService` | 高级评估框架 |
| `_reporting` | `ReportService` | 训练报告汇总 |
| `_database` | `DatabaseService` | MySQL 业务 |
| `_client` | `BleakClient` | 当前 BLE 客户端 |
| `_device` | `DeviceInfo` | 当前连接设备 |
| `_status` | `GatewayStatus` | 网关整体状态 |
| `_subscribers` | WebSocket 队列集合 | 所有前端实时订阅者 |
| `_lock` | `asyncio.Lock` | 防止并发连接/断开冲突 |
| `_model_training_task` | `asyncio.Task` | 后台训练任务 |
| `_model_training_status` | `dict` | 训练状态 |

初始化末尾调用：

```python
self._database.safe_sync_current_model_version()
```

作用：

> 如果数据库可用，把当前模型版本同步到 MySQL。

### 7.4 BLE 相关方法

#### `scan_devices(timeout_s)`

作用：

- 调用 `_discover_devices()` 扫描 BLE。
- 返回设备字典列表。

#### `connect(address, device_name, timeout_s)`

执行流程：

1. 加锁，防止同时连接。
2. 如果已经连接，直接返回当前状态。
3. 调用 `_find_device()` 找目标设备。
4. 创建 `BleakClient`。
5. `client.connect()` 连接设备。
6. `client.start_notify()` 订阅 ESP32 数据特征。
7. 保存 `_client` 和 `_device`。
8. 清空推理和评估缓冲区。
9. 更新状态为已连接。
10. 数据库中 upsert 设备为 online。
11. 广播状态给网页。

关键点：

```python
await client.start_notify(config.CHARACTERISTIC_UUID, self._notification_handler)
```

这表示：

> 之后 ESP32 每次 BLE Notify，都会触发 `_notification_handler()`。

#### `disconnect()`

执行流程：

1. 加锁。
2. 保存当前 client 和 device_address。
3. 清空 `_client`、`_device`。
4. 状态改为未连接。
5. 清空推理和评估缓冲。
6. 如果 BLE 还连着，调用 `client.disconnect()`。
7. 数据库标记设备 offline。
8. 停止录制。
9. 广播状态。

#### `_discover_devices(timeout_s)`

作用：

- 使用 `BleakScanner.discover()` 扫描设备。
- 兼容不同 Bleak 版本：
  - 新版支持 `return_adv=True`。
  - 旧版不支持则退回普通扫描。

#### `_to_target(device, advertisement)`

作用：

- 把 Bleak 的设备对象转换成项目内部 `DeviceInfo`。
- 提取：
  - 设备名。
  - local name。
  - address。
  - service UUID。
  - RSSI。

#### `_mark_candidate(info)`

作用：

- 判断某个设备是否可能是目标设备。

判断规则：

1. 设备名完全等于 `ESP32S3_Fitness_BLE`。
2. 广播里包含目标 Service UUID。
3. 设备名中包含 `ESP32`。

#### `_candidate_score(info)`

作用：

- 给扫描到的设备打分。

分数逻辑：

| 情况 | 基础分 |
|---|---:|
| 设备名完全匹配 | 300 |
| Service UUID 匹配 | 250 |
| 名称包含 ESP32 | 200 |
| 有普通名称 | 50 |

再结合 RSSI 排序。

#### `_sort_targets(targets)`

作用：

- 按候选分数和信号强度排序。

#### `_find_device(address, device_name, timeout_s)`

查找顺序：

1. 如果指定地址，优先匹配地址。
2. 再匹配设备名。
3. 再找候选设备。
4. 都找不到就抛错误。

### 7.5 数据采集方法

#### `start_recording(label, subject_id, notes)`

作用：

- 开始一次训练数据采集。

执行流程：

1. 检查设备是否已连接。
2. 规范化标签名。
3. 调用 `SessionRecorder.start()` 创建 CSV 和 JSON。
4. 状态改为 recording。
5. 数据库中创建 `sensor_sessions`。
6. 广播 `recording_started` 和 `status`。

注意：

> 如果没有连接设备，会抛出“设备未连接，请先连接设备后再开始采集”。

#### `stop_recording(reason="manual_stop")`

作用：

- 停止当前采集。

执行流程：

1. 调用 `SessionRecorder.stop()` 关闭 CSV。
2. 状态改为非 recording。
3. 数据库更新会话结束时间和行数。
4. 保存当前评估结果。
5. 重新生成报告摘要。
6. 数据库保存报告快照。
7. 广播 `recording_stopped`、`report_summary`、`status`。

### 7.6 状态查询方法

#### `get_status()`

作用：

- 返回网关当前完整状态。

它会实时同步：

- 当前 active session。
- inference 状态。
- evaluation 状态。
- advanced evaluation 状态。
- report summary。
- database 状态。

#### `get_inference_status()`

返回机器学习模型状态。

#### `get_evaluation_status()`

返回规则评估状态。

#### `get_advanced_evaluation_status()`

返回高级评估框架状态。

#### `get_report_summary()`

调用 `ReportService.build_summary()` 重新生成报告。

#### `get_database_status()`

调用数据库健康检查。

### 7.7 标签管理方法

#### `get_labels()`

作用：

- 扫描 `data/raw` 下的标签目录。
- 统计每个标签下有多少 CSV。
- 合并推荐标签。

返回：

```json
{
  "recommended": [...],
  "available": [...],
  "counts": {...}
}
```

#### `create_label(raw_label)`

作用：

- 规范化标签名。
- 创建标签目录。
- 返回是否新建。

#### `delete_label(raw_label)`

作用：

- 删除标签目录和数据库中对应会话。

安全保护：

1. 正在采集的标签不能删。
2. 模型训练中不能删。
3. 删除路径必须位于 raw 数据目录内。
4. 不存在的标签会报错。

返回：

- 删除的 CSV 数量。
- 删除的 JSON 数量。
- 数据库删除结果。
- 最新标签列表。

### 7.8 训练记录管理方法

#### `list_recordings(limit)`

作用：

- 遍历 `data/raw/<label>/*.json`。
- 读取每次采集的元数据。
- 返回最近的记录。

前端调试模式的“训练模型记录”依赖它。

#### `delete_recording(session_id)`

作用：

- 删除某一次采集。

执行流程：

1. 如果这条记录正在采集中，不允许删除。
2. 在 raw 目录中查找 `<session_id>.json`。
3. 从 JSON 中找到 CSV 路径和 meta 路径。
4. 删除 CSV。
5. 删除 JSON。
6. 删除数据库会话。
7. 更新报告摘要。
8. 广播状态。

### 7.9 认证和数据库转发方法

这些方法基本是转发给 `DatabaseService`：

| 方法 | 作用 |
|---|---|
| `init_database()` | 建表并同步模型版本 |
| `register_user()` | 注册 |
| `login_user()` | 登录 |
| `get_current_user()` | 根据 token 获取用户 |
| `list_database_users()` | 用户列表 |
| `list_database_sessions()` | 会话列表 |
| `list_database_evaluations()` | 评估结果列表 |
| `list_database_models()` | 模型版本列表 |
| `list_database_reports()` | 报告列表 |
| `get_user_dashboard()` | 当前用户首页统计 |

### 7.10 模型管理方法

#### `reload_inference_model()`

作用：

- 重新加载模型。
- 重置 `EvaluationEngine`。
- 重置 `AdvancedEvaluationService`。
- 同步模型版本到数据库。
- 广播最新推理和评估状态。

为什么要重置评估引擎：

> 模型窗口大小可能变了，评估引擎也要用新的窗口大小。

#### `start_model_training(labels, window_size, step_size, auto_reload)`

作用：

- 启动后台模型训练任务。

前置检查：

1. 如果已有训练任务在跑，不允许重复启动。
2. 标签必须在可训练标签中。
3. 至少选择一个标签。
4. 至少要有两个有样本的标签。

为什么至少两个标签：

> 分类模型必须有至少两个类别，否则模型只能永远预测唯一类别，比如只有深蹲样本时，静止也会被识别成深蹲。

之后：

- 更新训练状态为 `queued`。
- 创建后台任务 `_run_model_training()`。

#### `remove_label_from_model(label, window_size, step_size, auto_reload)`

作用：

- 从模型中移除某标签。

本质：

> 不是直接删除模型文件中的某一类，而是排除该标签后，用剩余标签重新训练一个新模型。

前置检查：

- 当前不能有训练任务。
- 被移除标签必须有本地训练样本。
- 移除后剩余可训练标签不能少于 2 个。

#### `_run_model_training(labels, window_size, step_size, auto_reload)`

后台训练流程：

1. 状态改为 `preparing`。
2. 拼出命令运行 `prepare_dataset.py`。
3. 保存预处理输出日志。
4. 如果预处理失败，抛错。
5. 状态改为 `training`。
6. 拼出命令运行 `train_baseline.py`。
7. 保存训练输出日志。
8. 如果训练失败，抛错。
9. 如果 `auto_reload=True`，自动调用 `reload_inference_model()`。
10. 状态改为 `completed`。
11. 如果任何阶段失败，状态改为 `failed`，记录错误。
12. 最后广播训练状态。

#### `_run_process(command)`

作用：

- 用 `asyncio.create_subprocess_exec()` 启动外部 Python 脚本。
- 捕获 stdout 和 stderr。
- 返回 exit code 和输出文本。

#### `_training_python_command()`

作用：

- 优先使用：

```text
ml_pipeline/.venv/Scripts/python.exe
```

- 如果虚拟环境不存在，就用当前解释器 `sys.executable`。

### 7.11 标签规范化方法

#### `_list_training_labels()`

作用：

- 返回可用于训练的标签。
- 包含推荐标签和 raw 目录里已有标签。
- 排除 `user_auto_training`。

#### `_normalize_label_name(raw_label)`

作用：

- 去空格。
- 转小写。
- 把空格和连字符变下划线。
- 合并多个下划线。
- 映射中文别名。
- 校验只能包含中文、英文、数字、下划线。

#### `_is_empty_alias_label_dir(path)`

作用：

- 如果某个中文别名目录是空的，就在标签列表中隐藏它。

### 7.12 BLE 数据处理方法

#### `_notification_handler(_, data)`

作用：

- BLE Notify 回调函数。
- 把 bytearray 解码为 UTF-8 字符串。
- 创建异步任务 `_process_packet(payload)`。

为什么不用同步处理：

> BLE 回调应该尽快返回，真正的数据处理放到异步任务中，避免阻塞 BLE 通知。

#### `_process_packet(payload)`

这是实时数据处理核心。

执行流程：

1. 记录接收时间。
2. 调用 `SensorPacket.from_payload()` 解析 11 字段 CSV。
3. 解析失败则广播 error。
4. 更新最新数据包、接收计数。
5. 如果正在录制，调用 recorder 写 CSV。
6. 调用 inference 进行模型推理。
7. 调用 evaluation 计算评分和建议。
8. 调用 advanced_evaluation 输出高级评估。
9. 广播 packet、inference、evaluation、advanced evaluation。
10. 如果产生新预测，广播 prediction。

### 7.13 断开处理方法

#### `_on_ble_disconnect()`

Bleak 的断开回调。

作用：

- 创建异步任务 `_handle_disconnect()`。

#### `_handle_disconnect()`

作用：

- 清空 BLE client。
- 状态改为未连接。
- 清空推理和评估缓冲。
- 数据库标记设备离线。
- 停止录制，原因是 `device_disconnected`。
- 广播状态。

### 7.14 WebSocket 广播方法

#### `subscribe()`

作用：

- 给一个新 WebSocket 创建队列。
- 加入 `_subscribers`。
- 立即推送当前状态、报告、高级评估和训练状态。

#### `unsubscribe(queue)`

作用：

- WebSocket 断开时移除队列。

#### `_broadcast(event, data)`

作用：

- 遍历所有订阅队列。
- `put_nowait()` 推送事件。
- 如果队列满了，说明前端可能掉线或处理不过来，把队列移除。

### 7.15 老师可能问

**问：为什么 `service.py` 这么重要？**

答：

> 它是业务编排层，把 BLE、采集、推理、评估、数据库和 WebSocket 串成完整闭环。没有它，API 层和各个子模块就是分散的。

**问：为什么用户训练标签不进模型？**

答：

> 用户训练过程没有人工确认标签质量，直接用于训练会污染模型。开发者采集标签才是模型训练数据。

**问：删除记录会不会把数据库也删掉？**

答：

> 会。`delete_recording()` 会删除本地 CSV/JSON，同时调用数据库服务删除对应的 sensor session 和 evaluation。

---

## 8. `pc_gateway/models.py`

### 8.1 文件定位

`models.py` 定义网关内部使用的数据结构。

注意：

> 这里的 `models.py` 不是机器学习模型，而是 Python 数据模型。

### 8.2 常量

#### `EXPECTED_FIELD_COUNT = 11`

表示 ESP32 BLE 数据包必须有 11 个字段：

```text
seq,timestampMs,ax,ay,az,gx,gy,gz,flexRawAdc,flexRawMv,flexIndex
```

### 8.3 `SensorPacket`

表示从 ESP32 收到的一条传感器数据。

字段：

| 字段 | 说明 |
|---|---|
| `seq` | 设备端数据包序号 |
| `timestamp_ms` | 设备端毫秒时间 |
| `ax, ay, az` | 三轴加速度 |
| `gx, gy, gz` | 三轴陀螺仪 |
| `flex_raw_adc` | 柔性传感器 ADC |
| `flex_raw_mv` | 柔性传感器毫伏 |
| `flex_index` | 弯曲指数 |
| `raw_packet` | 原始 CSV 字符串 |
| `received_time_ms` | 网关接收时间 |
| `received_time_iso` | 网关接收 ISO 时间 |

#### `from_payload(payload, received_time_ms)`

作用：

- 把 ESP32 发来的 CSV 字符串解析为 `SensorPacket`。

步骤：

1. 用逗号分割。
2. 检查字段数是否为 11。
3. 全部转换为 int。
4. 生成接收时间 ISO 字符串。
5. 返回 `SensorPacket` 实例。

错误情况：

- 字段数不是 11。
- 某个字段无法转换为整数。

#### `to_event_dict()`

作用：

- 转成前端 WebSocket/API 使用的字典。

字段命名采用前端更常见的 camelCase：

```text
timestampMs
flexRawAdc
flexRawMv
flexIndex
```

#### `to_csv_row(session_id, label)`

作用：

- 转成 CSV 行。
- 增加 `sessionId` 和 `label`。
- 用于 `SessionRecorder.write_packet()`。

### 8.4 `DeviceInfo`

表示扫描到的 BLE 设备。

字段：

| 字段 | 说明 |
|---|---|
| `name` | BLE 设备名 |
| `address` | BLE 地址 |
| `rssi` | 信号强度 |
| `local_name` | 广播里的 local name |
| `service_uuids` | 广播服务 UUID |
| `is_target_candidate` | 是否可能是目标 ESP32 |
| `candidate_reason` | 为什么认为它是候选设备 |

#### `to_dict()`

作用：

- 转成 API 返回给前端的字典。
- 增加 `displayName`。
- 如果没有名字，显示 `Unknown`。

### 8.5 `RecordingSession`

表示一次采集会话。

字段：

| 字段 | 说明 |
|---|---|
| `session_id` | 会话 ID |
| `label` | 标签 |
| `subject_id` | 用户或受试者标识 |
| `notes` | 备注 |
| `started_at_iso/ms` | 开始时间 |
| `csv_path` | CSV 文件路径 |
| `meta_path` | JSON 元数据路径 |
| `device_name/address` | 设备信息 |
| `rows_written` | 已写入行数 |
| `stopped_at_iso/ms` | 结束时间 |
| `stop_reason` | 停止原因 |

#### `to_dict()`

作用：

- 转成 JSON 可序列化字典。
- 把 `Path` 转成字符串。

### 8.6 `GatewayStatus`

表示整个网关当前状态。

字段：

| 字段 | 说明 |
|---|---|
| `connected` | 是否连接设备 |
| `recording` | 是否正在采集 |
| `device_name/address` | 当前设备 |
| `last_packet_time_ms` | 最近数据包时间 |
| `packets_received` | 已接收数据包数 |
| `last_error` | 最近错误 |
| `active_session` | 当前采集会话 |
| `latest_packet` | 最新传感器包 |
| `inference` | 推理状态 |
| `evaluation` | 评估状态 |
| `advanced_evaluation` | 高级评估状态 |
| `report_summary` | 报告摘要 |
| `database` | 数据库状态 |

### 8.7 老师可能问

**问：为什么要用 dataclass？**

答：

> 这些对象主要用来存储结构化数据，`dataclass` 可以减少样板代码，让字段定义更清晰。

**问：为什么字段名有 snake_case 和 camelCase？**

答：

> Python 内部使用 snake_case，更符合 Python 风格；返回给前端时转成 camelCase，更符合 JavaScript 风格。

---

## 9. `pc_gateway/recorder.py`

### 9.1 文件定位

`recorder.py` 负责把实时传感器数据保存成训练数据。

它是机器学习数据来源的关键模块。

### 9.2 `CSV_FIELDNAMES`

定义 CSV 文件表头：

```text
recordTimeIso, recordTimeMs, sessionId, label,
seq, timestampMs,
ax, ay, az, gx, gy, gz,
flexRawAdc, flexRawMv, flexIndex,
rawPacket
```

相比 ESP32 原始 11 字段，多了：

- 网关接收时间。
- 会话 ID。
- 标签。
- 原始包。

### 9.3 `sanitize_for_filename(value)`

作用：

- 把标签转成适合文件名的字符串。
- 非字母、数字、下划线、连字符的字符会变成 `_`。
- 如果结果为空，返回 `session`。

用途：

> 生成 session_id 和文件名时，避免中文或特殊符号造成文件路径问题。

### 9.4 `SessionRecorder`

负责采集生命周期。

#### `__init__(data_root)`

作用：

- 保存数据根目录。
- 自动创建目录。
- 初始化当前会话、CSV 文件句柄和 CSV writer。

#### `active_session`

属性。

作用：

- 返回当前正在采集的 `RecordingSession`。
- 没有采集时返回 `None`。

#### `is_recording`

属性。

作用：

- 判断当前是否正在采集。

#### `start(label, subject_id, notes, device_name, device_address)`

作用：

- 开始一次采集。

执行流程：

1. 如果已有 active session，抛出错误。
2. 记录开始时间。
3. 生成 session_id。
4. 创建标签目录。
5. 创建 CSV 文件。
6. 写入 CSV 表头。
7. 创建 JSON 元数据路径。
8. 保存 active session。
9. 写入初始 metadata。
10. 返回 `RecordingSession`。

文件命名类似：

```text
20260428_182229_squat_standard.csv
20260428_182229_squat_standard.json
```

#### `write_packet(packet)`

作用：

- 把一条 `SensorPacket` 写入 CSV。

逻辑：

1. 如果当前没有 active session，直接返回。
2. 调用 `packet.to_csv_row()` 转成 CSV 行。
3. `writerow()` 写入。
4. `flush()` 立即落盘。
5. `rows_written += 1`。

为什么每次 flush：

> 防止程序异常退出时数据丢失，尤其是采集时突然断电或断开。

#### `stop(reason)`

作用：

- 停止当前采集。

执行流程：

1. 如果没有采集，返回 None。
2. 记录停止时间。
3. 保存停止原因。
4. 关闭 CSV 文件。
5. 写入最终 metadata。
6. 清空 active session。
7. 返回完成的 `RecordingSession`。

#### `_write_metadata()`

作用：

- 把当前会话写成 JSON。
- 保存到 `meta_path`。

### 9.5 老师可能问

**问：采集的数据保存在哪里？**

答：

> 保存到 `ml_pipeline/data/raw/<label>/` 下，每次采集有一个 CSV 和一个 JSON。CSV 是每帧传感器数据，JSON 是会话元信息。

**问：为什么停止时还要再写一次 JSON？**

答：

> 开始时 JSON 只有开始时间和路径，停止后才知道结束时间、停止原因和总行数，所以停止时要更新元数据。

---

## 10. `pc_gateway/inference.py`

### 10.1 文件定位

`inference.py` 是实时机器学习推理模块。

它负责：

- 加载训练好的 `random_forest_model.joblib`。
- 维护传感器滑动窗口。
- 提取和训练时一致的统计特征。
- 调用模型预测动作标签。
- 输出置信度和 Top labels。

### 10.2 常量

#### `FEATURE_COLUMNS`

```python
["ax", "ay", "az", "gx", "gy", "gz", "flexIndex"]
```

代表用于模型的 7 个输入信号。

#### `FEATURE_STATS`

```python
("mean", "std", "min", "max", "ptp", "rms")
```

每个信号提取 6 个统计量。

总特征数默认：

```text
7 * 6 = 42
```

### 10.3 `_now_dict()`

作用：

- 返回当前时间的毫秒和 ISO 字符串。

返回：

```json
{
  "ms": 1710000000000,
  "iso": "2026-..."
}
```

### 10.4 `InferenceEngine.__init__()`

初始化：

| 成员 | 作用 |
|---|---|
| `_model_path` | 模型文件路径 |
| `_label_map_path` | 标签映射路径 |
| `_default_window_size` | 默认窗口大小 |
| `_window_size` | 当前窗口大小 |
| `_buffer` | 保存最近 N 个 `SensorPacket` |
| `_model` | 加载后的 sklearn 模型 |
| `_feature_columns` | 模型需要的特征列 |
| `_label_id_to_name` | 标签编号到名称 |
| `_dataset_meta` | 数据集元信息 |
| `_latest_prediction` | 最近预测 |
| `_last_error` | 最近错误 |
| `_loaded_at_ms/iso` | 模型加载时间 |

初始化最后调用：

```python
self.load_model(silent=True)
```

意思：

> 网关启动时尝试加载模型；如果模型不存在，静默处理，不让服务启动失败。

### 10.5 `window_size`

属性。

作用：

- 返回当前推理窗口大小。
- 评估引擎会用它保持窗口一致。

### 10.6 `clear_buffer()`

作用：

- 清空滑动窗口。
- 清空最近预测。

使用场景：

- 设备刚连接。
- 设备断开。
- 重载模型。

### 10.7 `load_model(silent=False)`

作用：

- 加载 joblib 模型。

执行流程：

1. 清空旧模型、旧特征、旧标签、旧元信息。
2. 检查模型文件是否存在。
3. 如果不存在，记录错误并返回状态。
4. 用 `joblib.load()` 读取模型文件。
5. 检查模型文件必须是 dict。
6. 从 dict 中取出：
   - `model`
   - `feature_columns`
   - `dataset_meta`
   - `label_map`
7. 如果没有 `label_map`，从 label_map 文件读取。
8. 规范化标签映射。
9. 根据 dataset_meta 更新窗口大小。
10. 记录加载时间。
11. 清空缓冲。
12. 返回状态。

模型文件结构来自 `train_baseline.py`：

```python
{
    "model": model,
    "feature_columns": feature_columns,
    "label_map": label_map,
    "dataset_meta": dataset_meta,
}
```

### 10.8 `consume_packet(packet)`

这是实时推理入口。

执行流程：

1. 把新 `SensorPacket` 放入 `_buffer`。
2. 如果没有模型，返回 None。
3. 如果缓冲区长度小于窗口大小，返回 None。
4. 调用 `_build_feature_row()` 生成特征。
5. 构造 pandas DataFrame。
6. 按 `_feature_columns` 排列特征列。
7. 调用模型 `predict()`。
8. 调用 `_predict_top_labels()` 获取概率排名。
9. 生成 `_latest_prediction`。
10. 返回预测结果。

预测结果包含：

| 字段 | 说明 |
|---|---|
| `labelId` | 模型输出类别编号 |
| `label` | 类别名称 |
| `confidence` | 置信度 |
| `topLabels` | 前几个候选类别 |
| `windowSize` | 窗口大小 |
| `bufferedPoints` | 当前缓冲点数 |
| `updatedAtMs/Iso` | 更新时间 |

### 10.9 `status_dict()`

返回模型状态：

- 是否加载模型。
- 模型路径。
- 标签映射路径。
- 特征数量。
- 窗口大小。
- 缓冲点数。
- 是否 ready。
- 最近错误。
- 最近预测。
- 数据集元信息。

### 10.10 私有工具方法

#### `_default_feature_columns()`

生成默认特征列：

```text
ax_mean, ax_std, ax_min, ax_max, ax_ptp, ax_rms,
...
flexIndex_mean, ...
```

#### `_load_label_map_from_file()`

从 `label_map.json` 读取标签映射。

#### `_normalize_label_map(label_map)`

作用：

- 兼容两种标签映射形式：

```json
{"idle": 0, "squat_standard": 1}
```

或：

```json
{"0": "idle", "1": "squat_standard"}
```

最后统一成：

```python
{0: "idle", 1: "squat_standard"}
```

#### `_apply_window_size_from_meta(dataset_meta)`

作用：

- 从训练数据元信息中读取 `window_size`。
- 保证实时推理窗口和训练时一致。

#### `_build_feature_row(packets)`

作用：

- 对最近 N 个包提取 42 个统计特征。

每个信号计算：

- 平均值。
- 标准差。
- 最小值。
- 最大值。
- 峰峰值。
- 均方根。

#### `_predict_top_labels(input_df, predicted_label_id)`

作用：

- 如果模型支持 `predict_proba()`，返回概率最高的前三个标签。
- 如果不支持概率，就只返回预测标签，概率设为 1.0。

### 10.11 老师可能问

**问：推理和训练为什么要用一样的特征？**

答：

> 机器学习模型训练时看到的是窗口统计特征，实时推理时也必须生成完全同样的特征列，否则模型输入维度和含义会不一致。

**问：为什么要等窗口满了才预测？**

答：

> 因为模型训练基于固定窗口。如果只有几条数据，特征不完整，预测不可靠。

---

## 11. `pc_gateway/evaluation.py`

### 11.1 文件定位

`evaluation.py` 是实时动作质量评估模块。

它不是分类模型，而是规则引擎。

它负责：

- 判断动作阶段。
- 计算动作幅度分。
- 计算稳定性分。
- 计算节奏分。
- 合成标准度分。
- 判断代偿风险。
- 生成纠正建议。
- 生成语音反馈文案。

### 11.2 `_now_dict()`

返回当前毫秒和 ISO 时间。

### 11.3 `_clamp(value, minimum, maximum)`

作用：

- 把数值限制在指定范围内。

例如：

```python
_clamp(120, 0, 100) -> 100
_clamp(-5, 0, 100) -> 0
```

### 11.4 `EvaluationEngine.__init__()`

初始化：

| 成员 | 作用 |
|---|---|
| `_window_size` | 评估窗口大小，至少 5 |
| `_buffer` | 最近 N 个 SensorPacket |
| `_latest` | 当前评估状态 |
| `_voice_cooldown_ms` | 语音播报冷却时间 |
| `_last_voice_text` | 上一次播报文本 |
| `_last_voice_ms` | 上一次播报时间 |

### 11.5 `clear()`

作用：

- 清空缓冲区。
- 重置评估状态。
- 清空语音冷却记录。

使用场景：

- 重新连接设备。
- 断开设备。
- 重载模型。

### 11.6 `consume(packet, inference_status)`

这是评估主入口。

执行流程：

1. 把新包加入缓冲区。
2. 从 `inference_status.latestPrediction` 取模型预测标签。
3. 如果没有预测，默认 `idle`。
4. 把标签转成人类可读名称。
5. 判断动作大类：
   - `idle`
   - `squat`
   - `bench`
   - `general`
6. 从缓冲区取出：
   - flexIndex 序列。
   - 加速度模长序列。
   - 陀螺仪模长序列。
7. 调用 `_detect_phase()` 判断动作阶段。
8. 调用 `_depth_score()` 计算动作幅度分。
9. 调用 `_stability_score()` 计算稳定性分。
10. 调用 `_rhythm_score()` 计算节奏分。
11. 加权计算标准度：

```text
standardScore = 0.4 * depthScore
              + 0.35 * stabilityScore
              + 0.25 * rhythmScore
```

12. 如果模型识别为错误动作，限制最高分：
    - `squat_wrong` 最高 62。
    - `bench_wrong` 最高 65。
13. 计算风险等级。
14. 生成建议。
15. 生成语音反馈。
16. 更新 `_latest`。
17. 返回评估状态。

### 11.7 `status_dict()`

返回最近一次评估结果。

### 11.8 `_empty_status()`

返回默认状态。

含义：

- 尚无实时数据。
- 标准度为 0。
- 风险 unknown。
- 语音不触发。

### 11.9 `_action_family(label)`

把标签转动作大类：

| 标签 | 大类 |
|---|---|
| `idle` | `idle` |
| `squat_standard` / `squat_wrong` | `squat` |
| `bench_standard` / `bench_wrong` | `bench` |
| 其他 | `general` |

### 11.10 `_humanize_label(label)`

把内部标签转中文显示：

| 内部标签 | 显示 |
|---|---|
| `idle` | 静止 |
| `squat_standard` | 深蹲-标准 |
| `squat_wrong` | 深蹲-错误 |
| `bench_standard` | 卧推-标准 |
| `bench_wrong` | 卧推-错误 |

### 11.11 `_detect_phase(action_family, flex_values, gyro_magnitudes)`

作用：

- 判断动作阶段。

核心依据：

- 最近 flexIndex 变化量。
- 最新陀螺仪模长。

深蹲阶段大致包括：

- 下蹲阶段。
- 起身阶段。
- 蹲底控制。
- 动作过渡。

卧推阶段大致包括：

- 下放阶段。
- 推起阶段。
- 动作过渡。

静止判断：

- flexIndex 很小。
- gyro 很小。

### 11.12 `_depth_score(action_family, latest_flex, peak_flex)`

作用：

- 根据弯曲峰值估计动作幅度。

逻辑：

- 静止直接 100。
- 深蹲目标峰值约 30。
- 卧推目标峰值约 25。
- 当前峰值 / 目标峰值 * 100。
- 限制在 0-100。

### 11.13 `_stability_score(acc_magnitudes, gyro_magnitudes, flex_values)`

作用：

- 估计动作稳定性。

方法：

- 计算加速度变化的标准差。
- 计算角速度变化的标准差。
- 计算 flexIndex 变化的标准差。
- 波动越大，扣分越多。

适合解释为：

> 如果动作过程中加速度和角速度变化过于剧烈，说明动作抖动或控制不足，稳定性分降低。

### 11.14 `_rhythm_score(flex_values, gyro_magnitudes)`

作用：

- 估计动作节奏。

逻辑：

- 动作幅度越明显，给一定奖励。
- flex 和 gyro 变化太乱会扣分。
- 输出 0-100。

### 11.15 `_compensation_risk(action_label, standard_score, stability_score, rhythm_score)`

输出：

| 风险 | 条件 |
|---|---|
| `high` | 明显错误标签、标准度低、稳定性低 |
| `medium` | 标准度或节奏一般 |
| `low` | 分数较好 |

### 11.16 `_build_suggestions(...)`

作用：

- 根据动作类型和分数生成最多 3 条纠正建议。

逻辑：

- 静止：提示保持站立、准备采集。
- 深蹲错误：优先提示膝盖内扣、轨迹、深度、节奏。
- 深蹲标准但分数低：根据深度、稳定性、节奏分别提示。
- 卧推：提示幅度、上肢控制、发力节奏。
- 其他动作：提示控制速度和幅度。

### 11.17 `_build_voice_feedback(suggestions)`

作用：

- 从建议中取第一条作为语音文本。
- 判断是否应该播报。

冷却逻辑：

- 如果文案变化，允许播报。
- 如果文案没变，但超过冷却时间，也允许播报。
- 否则不播报，避免一直重复。

返回：

```json
{
  "enabled": true,
  "mode": "preview",
  "ttsReady": false,
  "text": "...",
  "shouldSpeak": true,
  "lastTriggeredAtMs": 123456
}
```

### 11.18 `_acc_magnitude(packet)`

计算加速度模长：

```text
sqrt(ax^2 + ay^2 + az^2)
```

### 11.19 `_gyro_magnitude(packet)`

计算角速度模长：

```text
sqrt(gx^2 + gy^2 + gz^2)
```

### 11.20 `_std_diff(values)`

作用：

- 计算相邻差分的标准差。
- 用来衡量变化是否平稳。

### 11.21 老师可能问

**问：标准度分是怎么来的？**

答：

> 当前标准度由动作幅度、稳定性和节奏三个子分数组成，权重分别是 0.4、0.35、0.25。幅度主要看 flexIndex 峰值，稳定性看加速度和角速度波动，节奏看动作变化是否平稳。

**问：这是不是最终评估模型？**

答：

> 不是最终复杂模型，是一个可解释的规则评估框架。它适合原型阶段实时反馈，后续可以用专家标注数据训练更复杂的评估模型替换。

---

## 12. `pc_gateway/advanced_evaluation.py`

### 12.1 文件定位

这是服务端复杂动作评估模型的预留框架。

相比 `evaluation.py`：

- `evaluation.py` 更偏实时基础评分。
- `advanced_evaluation.py` 更偏代偿风险、动作总结和未来复杂模型接入。

### 12.2 `_now_dict()`

返回当前时间。

### 12.3 `_clamp()`

限制数值范围。

### 12.4 `AdvancedEvaluationService.__init__()`

初始化：

| 成员 | 作用 |
|---|---|
| `_profile_path` | 高级评估配置路径 |
| `_window_size` | 窗口大小，至少 8 |
| `_buffer` | 最近传感器包 |
| `_profile` | 评估阈值配置 |
| `_latest` | 最近高级评估状态 |

### 12.5 `clear()`

清空缓冲和状态。

### 12.6 `status_dict()`

返回最新高级评估。

### 12.7 `consume(packet, inference_status, evaluation_status)`

这是高级评估入口。

执行流程：

1. 加入传感器窗口。
2. 从推理状态获取动作标签。
3. 判断动作大类。
4. 取 flex、加速度模长、陀螺仪模长。
5. 从基础评估中读取：
   - standardScore。
   - depthScore。
   - stabilityScore。
   - rhythmScore。
6. 调用 `_compensation_flags()` 识别风险标志。
7. 调用 `_posture_summary()` 生成动作总结。
8. 取第一个风险作为纠正重点。
9. 判断模型 readiness。
10. 根据标准度分生成分数等级。
11. 更新 `_latest`。

### 12.8 `_load_profile()`

作用：

- 读取 `advanced_evaluation_profile.json`。
- 如果文件存在且解析成功，使用其中阈值。
- 如果不存在，使用默认阈值。

默认阈值包括：

| 阈值 | 含义 |
|---|---|
| `squat_depth_good` | 深蹲深度合格线 |
| `stability_good` | 稳定性合格线 |
| `rhythm_good` | 节奏合格线 |
| `gyro_peak_alert` | 角速度过大警戒线 |
| `flex_peak_low` | 有效动作幅度过低线 |

### 12.9 `_empty_status()`

返回默认高级评估状态。

包含：

- 是否 available。
- modelReady。
- profilePath。
- profileLoaded。
- actionLabel。
- standardBand。
- compensationFlags。
- postureSummary。
- correctionFocus。

### 12.10 `_action_family(label)`

同 `evaluation.py`，把标签归为：

- idle。
- squat。
- bench。
- general。

### 12.11 `_score_band(score)`

把分数转等级：

| 分数 | 等级 |
|---:|---|
| >= 85 | `excellent` |
| >= 70 | `good` |
| >= 55 | `watch` |
| < 55 | `risk` |

### 12.12 `_compensation_flags(...)`

识别代偿风险。

可能输出：

| code | 含义 |
|---|---|
| `knee_valgus_pattern` | 深蹲错误模式，疑似膝盖内扣 |
| `depth_insufficient` | 深度不足 |
| `stability_loss` | 稳定性不足 |
| `rhythm_unsteady` | 节奏不稳 |
| `excessive_angular_velocity` | 角速度峰值过高 |
| `range_of_motion_small` | 有效活动幅度太小 |

每个 flag 包含：

- code。
- label。
- level。
- detail。

### 12.13 `_posture_summary(...)`

作用：

- 根据动作类型、分数和风险标志生成一句总结。

例如：

- 静止：当前处于静止状态。
- 深蹲错误：优先纠正膝盖轨迹。
- 分数高且无风险：动作完成较好。
- 有风险：优先关注第一个风险。

### 12.14 `_acc_mag(packet)` 和 `_gyro_mag(packet)`

分别计算加速度模长和角速度模长。

### 12.15 老师可能问

**问：第 4 点说服务端训练复杂动作评估模型，这里实现了吗？**

答：

> 当前实现的是复杂评估模型的服务端框架和规则阈值版本。它已经把输入、输出、配置文件和前端展示结构搭起来了，后续可以把 `_compensation_flags` 这一层替换成训练好的复杂模型。

---

## 13. `pc_gateway/reporting.py`

### 13.1 文件定位

`reporting.py` 负责从本地采集数据和模型指标生成报告摘要。

它主要服务：

- 网页个人首页。
- 历史报告。
- 调试模式报告统计。

### 13.2 `ReportService.__init__()`

参数：

| 参数 | 作用 |
|---|---|
| `data_root` | 原始数据目录，默认 `config.RAW_DATA_ROOT` |
| `metrics_path` | 模型指标文件，默认 `models/metrics.json` |

### 13.3 `build_summary(recent_limit=5)`

作用：

- 汇总训练数据和模型指标。

输出内容：

| 字段 | 含义 |
|---|---|
| `available` | 报告是否可用 |
| `stage` | 当前项目阶段 |
| `totalSessions` | 总采集次数 |
| `coveredLabels` | 已覆盖标签 |
| `coveredLabelCount` | 标签数量 |
| `coverageRatio` | 推荐标签覆盖率 |
| `totalRows` | 总数据行 |
| `totalDurationMinutes` | 总采集时长 |
| `labelBreakdown` | 各标签会话数 |
| `recentSessions` | 最近记录 |
| `dailyTrend` | 最近 7 天趋势 |
| `modelMetrics` | 模型准确率等 |

内部流程：

1. `_load_sessions()` 读取本地 JSON。
2. `Counter` 统计标签。
3. 汇总行数和时长。
4. `_load_model_metrics()` 读取模型指标。
5. `_build_daily_trend()` 生成趋势。
6. `_current_stage()` 判断项目阶段。

### 13.4 `_load_sessions()`

作用：

- 遍历 `data/raw/<label>/*.json`。
- 读取所有会话元数据。
- 按开始时间倒序排序。

如果某个 JSON 解析失败，会跳过。

### 13.5 `_load_model_metrics()`

作用：

- 读取 `metrics.json`。
- 返回验证集准确率、测试集准确率、特征数量和摘要文字。

如果文件不存在：

- 返回 `available=False`。

### 13.6 `_session_duration_ms(session)`

作用：

- 根据 `startedAtMs` 和 `stoppedAtMs` 计算会话时长。

### 13.7 `_build_daily_trend(sessions)`

作用：

- 按日期统计每天采集次数。
- 返回最近 7 天。

### 13.8 `_current_stage(covered_labels, model_metrics)`

作用：

- 根据标签覆盖和模型指标判断项目阶段。

大概阶段：

- 基础采集阶段。
- 二分类验证阶段。
- 多动作采集阶段。
- 模型联调阶段。

### 13.9 `_metrics_summary(val_accuracy, test_accuracy)`

作用：

- 把准确率数字转成中文摘要。

例如：

```text
当前验证集准确率约为 95.0%，测试集准确率约为 90.0%
```

### 13.10 老师可能问

**问：报告是实时算的还是数据库查的？**

答：

> 当前 `ReportService` 主要从本地 JSON 和模型 metrics 文件汇总，数据库服务也会保存报告快照。这样即使数据库暂时不可用，本地报告仍能生成。

---

## 14. `pc_gateway/db.py`

### 14.1 文件定位

`db.py` 是数据库连接管理层。

它不定义表，也不写具体业务，只负责：

- 创建 SQLAlchemy Engine。
- 创建 Session。
- 管理事务。
- 初始化表。
- 做数据库健康检查。

### 14.2 `Base`

```python
Base = declarative_base()
```

作用：

> 所有 ORM 表模型都继承这个 Base，最后 `Base.metadata.create_all()` 才知道要创建哪些表。

### 14.3 `DatabaseManager`

#### `__init__()`

初始化：

- `_engine = None`
- `_session_factory = None`

采用懒加载：

> 不在程序启动时立刻连接数据库，而是在真正使用时才创建 engine。

#### `enabled`

属性。

返回：

```python
config.MYSQL_ENABLED
```

作用：

> 判断是否启用 MySQL。

#### `_ensure_engine()`

作用：

- 如果没有启用 MySQL，抛出错误。
- 如果 engine 未创建，则创建 SQLAlchemy engine。
- 同时创建 session factory。

参数：

| 参数 | 作用 |
|---|---|
| `pool_pre_ping=True` | 使用连接前先检查是否断开 |
| `pool_recycle=3600` | 防止 MySQL 长连接超时 |
| `echo=config.DATABASE_ECHO` | 是否打印 SQL |
| `future=True` | 使用 SQLAlchemy 2 风格 |

#### `_ensure_session_factory()`

作用：

- 确保 session factory 已经初始化。
- 返回 sessionmaker。

#### `session_scope()`

这是数据库事务上下文管理器。

使用方式：

```python
with db_manager.session_scope() as session:
    ...
```

逻辑：

1. 创建 session。
2. yield 给业务代码。
3. 如果成功，commit。
4. 如果异常，rollback。
5. 最后 close。

#### `create_all()`

作用：

- 导入 `db_models`，确保所有表注册到 Base。
- 调用 `Base.metadata.create_all(engine)` 创建表。

#### `health()`

作用：

- 返回数据库状态。

如果 MySQL 未启用：

```json
{
  "enabled": false,
  "connected": false,
  "message": "MySQL backend is disabled."
}
```

如果启用：

- 执行 `SELECT 1`。
- 成功返回 connected true。
- 失败返回错误信息。

### 14.4 `db_manager`

全局单例：

```python
db_manager = DatabaseManager()
```

数据库服务统一用这个对象。

### 14.5 老师可能问

**问：为什么用 `session_scope()`？**

答：

> 它统一管理事务，成功自动提交，失败自动回滚，最后自动关闭连接，避免每个业务函数都重复写 commit/rollback/close。

**问：MySQL 没开启会怎么样？**

答：

> `DatabaseManager.enabled` 会返回 false，数据库相关功能不可用，但 BLE 采集、CSV 保存和模型推理仍然可以运行。

---

## 15. `pc_gateway/db_models.py`

### 15.1 文件定位

`db_models.py` 定义 MySQL 表结构。

使用技术：

- SQLAlchemy ORM。
- `Mapped` 类型注解。
- `mapped_column` 定义字段。
- `relationship` 定义表关系。

### 15.2 `utcnow()`

作用：

- 返回当前 UTC 时间。
- 用作创建时间和更新时间默认值。

### 15.3 `TimestampMixin`

这是公共时间字段混入类。

字段：

| 字段 | 说明 |
|---|---|
| `created_at` | 创建时间 |
| `updated_at` | 更新时间 |

很多表继承它，避免重复写字段。

### 15.4 `User`

表名：

```text
users
```

作用：

- 保存用户账号。

字段：

| 字段 | 说明 |
|---|---|
| `id` | 主键 |
| `username` | 用户名，唯一 |
| `email` | 邮箱，唯一 |
| `password_hash` | 密码哈希 |
| `full_name` | 真实姓名，预留 |
| `student_no` | 学号，预留 |
| `role` | 用户角色 |

关系：

- 一个用户有多个 token。
- 一个用户有多个训练会话。

### 15.5 `UserToken`

表名：

```text
user_tokens
```

作用：

- 保存登录令牌。

字段：

| 字段 | 说明 |
|---|---|
| `id` | 主键 |
| `user_id` | 外键到 users |
| `token` | 访问 token |
| `expires_at` | 过期时间 |
| `last_used_at` | 最近使用时间 |
| `created_at` | 创建时间 |

关系：

- 多个 token 属于一个用户。

### 15.6 `Device`

表名：

```text
devices
```

作用：

- 记录 BLE 设备。

字段：

| 字段 | 说明 |
|---|---|
| `device_code` | 设备编号，预留 |
| `device_name` | 设备名称 |
| `ble_address` | BLE 地址，唯一 |
| `firmware_version` | 固件版本，预留 |
| `status` | online/offline |
| `first_seen_at` | 首次发现时间 |
| `last_seen_at` | 最近发现时间 |

关系：

- 一个设备可以产生多个训练会话。

### 15.7 `SensorSession`

表名：

```text
sensor_sessions
```

作用：

- 保存一次采集会话的结构化信息。

字段：

| 字段 | 说明 |
|---|---|
| `session_id` | 本地会话 ID |
| `label` | 标签 |
| `subject_id` | 用户或受试者 |
| `notes` | 备注 |
| `started_at` | 开始时间 |
| `stopped_at` | 停止时间 |
| `duration_ms` | 持续时间 |
| `rows_written` | 写入行数 |
| `csv_path` | CSV 路径 |
| `meta_path` | JSON 路径 |
| `source_type` | 来源，当前主要是 pc_gateway |
| `stop_reason` | 停止原因 |
| `user_id` | 关联用户 |
| `device_id` | 关联设备 |

关系：

- 属于一个用户。
- 属于一个设备。
- 可以有一个评估结果。

### 15.8 `ModelVersion`

表名：

```text
model_versions
```

作用：

- 保存模型版本信息。

字段：

| 字段 | 说明 |
|---|---|
| `model_name` | 模型名称 |
| `model_type` | 模型类型，如 random_forest |
| `task_type` | 任务类型，如 action_classification |
| `version` | 版本号 |
| `labels_json` | 模型包含的标签 |
| `feature_count` | 特征数量 |
| `val_accuracy` | 验证集准确率 |
| `test_accuracy` | 测试集准确率 |
| `model_path` | 模型文件路径 |
| `metrics_path` | 指标文件路径 |
| `is_active` | 是否当前启用 |

### 15.9 `EvaluationResult`

表名：

```text
evaluation_results
```

作用：

- 保存一次会话的动作评估结果。

字段：

| 字段 | 说明 |
|---|---|
| `sensor_session_id` | 关联采集会话 |
| `user_id` | 关联用户 |
| `action_label` | 动作标签 |
| `standard_score` | 标准度 |
| `depth_score` | 幅度分 |
| `stability_score` | 稳定性分 |
| `rhythm_score` | 节奏分 |
| `compensation_risk` | 风险等级 |
| `suggestions_json` | 纠正建议 |
| `voice_feedback_text` | 语音文案 |
| `source` | 评估来源 |

### 15.10 `TrainingReport`

表名：

```text
training_reports
```

作用：

- 保存训练报告快照。

字段：

| 字段 | 说明 |
|---|---|
| `user_id` | 用户 |
| `report_date` | 报告日期 |
| `total_sessions` | 总训练次数 |
| `total_duration_minutes` | 总时长 |
| `avg_score` | 平均分 |
| `best_action` | 表现较好的动作 |
| `weak_action` | 薄弱动作 |
| `summary_text` | 报告摘要 |
| `report_json` | 完整报告 JSON |

### 15.11 老师可能问

**问：为什么原始传感器数据不全放数据库？**

答：

> 原始时序数据量比较大，CSV 更适合模型训练和文件追溯。数据库主要保存结构化索引、用户、会话、评估和报告。

**问：为什么有 `model_versions`？**

答：

> 模型训练会不断迭代，需要记录当前启用模型、标签范围、准确率和文件路径，方便追踪模型版本。

---

## 16. `pc_gateway/db_service.py`

### 16.1 文件定位

`db_service.py` 是数据库业务服务层。

它基于 `db.py` 的连接能力和 `db_models.py` 的表结构，提供真正业务操作。

### 16.2 `DatabaseService.__init__()`

保存全局数据库管理器：

```python
self._manager = db_manager
```

### 16.3 用户认证方法

#### `_build_local_email(username)`

作用：

- 根据用户名生成本地占位邮箱。

格式：

```text
username@local.smart-fitness
```

因为当前注册只需要用户名和密码，不需要用户输入邮箱。

#### `register_user(username, password)`

作用：

- 注册用户。

执行流程：

1. 生成本地邮箱。
2. 查询用户名或邮箱是否已存在。
3. 如果存在，抛出错误。
4. 使用 `hash_password()` 生成密码哈希。
5. 创建 `User`。
6. `session.flush()` 获取 id。
7. 返回用户字典。

#### `login(username, password)`

作用：

- 登录。

执行流程：

1. 根据用户名查用户。
2. 用 `verify_password()` 校验密码。
3. 失败则抛出错误。
4. 创建 `UserToken`。
5. token 过期时间来自 `token_expiry()`。
6. 返回 access token 和用户信息。

返回：

```json
{
  "accessToken": "...",
  "tokenType": "bearer",
  "expiresAt": "...",
  "user": {...}
}
```

#### `current_user(token_value)`

作用：

- 根据 token 查当前用户。

逻辑：

- token 必须存在。
- token 未过期。
- 更新 `last_used_at`。
- 返回用户信息。

### 16.4 列表查询方法

#### `list_users(limit)`

返回最近创建的用户。

#### `list_sensor_sessions(limit)`

返回最近采集会话。

#### `list_evaluations(limit)`

返回最近评估结果。

#### `list_models(limit)`

返回最近模型版本。

#### `list_reports(limit)`

返回最近训练报告。

### 16.5 设备方法

#### `upsert_device(device_info, status="online")`

作用：

- 如果设备不存在，则创建。
- 如果存在，则更新设备名和状态。
- 更新 `last_seen_at`。

为什么叫 upsert：

> update + insert，存在就更新，不存在就插入。

#### `mark_device_offline(address)`

作用：

- 根据 BLE 地址找到设备。
- 把状态改为 offline。
- 更新时间。

### 16.6 会话方法

#### `create_sensor_session(local_session, device_address)`

作用：

- 把 `RecordingSession` 写入数据库。

执行流程：

1. 根据 BLE 地址查设备。
2. 根据 `subject_id` 查用户。
3. 创建 `SensorSession`。
4. 写入 label、notes、csv_path、meta_path 等。
5. 关联 user_id 和 device_id。

#### `finish_sensor_session(local_session)`

作用：

- 采集结束后更新数据库会话。

更新：

- rows_written。
- stop_reason。
- stopped_at。
- duration_ms。
- csv_path。
- meta_path。

#### `delete_sensor_session(session_id)`

作用：

- 删除某个数据库会话。
- 如果有 evaluation，也一起删。

#### `delete_sensor_sessions_by_label(label)`

作用：

- 删除某个标签下所有数据库会话和评估结果。

返回：

- 删除会话数量。
- 删除评估数量。
- session IDs。

### 16.7 评估方法

#### `save_evaluation_result(session_id, evaluation_status)`

作用：

- 把实时评估状态保存到数据库。

前置：

- `evaluation_status` 必须存在且 `available=True`。
- 必须找到对应 `SensorSession`。

保存字段：

- action_label。
- standard_score。
- depth_score。
- stability_score。
- rhythm_score。
- compensation_risk。
- suggestions_json。
- voice_feedback_text。
- source。

如果该会话已有评估结果：

> 更新已有结果，而不是重复插入。

### 16.8 模型版本方法

#### `sync_current_model_version()`

作用：

- 把当前模型文件同步到 `model_versions` 表。

执行流程：

1. 检查 `random_forest_model.joblib` 是否存在。
2. 读取 `metrics.json`。
3. 读取 `label_map.json`。
4. 用模型文件修改时间生成版本号：

```text
rf-<mtime_ns>
```

5. 把旧模型版本设置为非 active。
6. 如果新版本不存在则创建。
7. 写入标签、特征数、准确率、路径。
8. 设置 `is_active=True`。

### 16.9 报告方法

#### `create_report_snapshot(report_summary)`

作用：

- 把当前报告摘要保存到 `training_reports` 表。

逻辑：

- 根据 labelBreakdown 找 best_action 和 weak_action。
- 从 evaluation_results 计算平均分。
- 写入总会话数、总时长、报告 JSON。

### 16.10 用户首页方法

#### `get_user_dashboard(token_value)`

作用：

- 根据 token 获取某个用户的训练首页数据。

执行流程：

1. 验证 token。
2. 查询该用户所有 sensor_sessions。
3. 查询该用户所有 evaluation_results。
4. 计算总会话数。
5. 计算总时长。
6. 计算平均分。
7. 统计标签分布。
8. 构造最近 7 天分数趋势。
9. 返回最近评估和最近会话。

返回字段：

- user。
- totalSessions。
- totalDurationMinutes。
- averageScore。
- labelBreakdown。
- latestEvaluation。
- recentSessions。
- scoreTrend。

### 16.11 safe 方法

这些方法包括：

- `safe_upsert_device`
- `safe_mark_device_offline`
- `safe_create_sensor_session`
- `safe_finish_sensor_session`
- `safe_delete_sensor_session`
- `safe_delete_sensor_sessions_by_label`
- `safe_save_evaluation_result`
- `safe_sync_current_model_version`
- `safe_create_report_snapshot`

作用：

> 数据库不可用或执行失败时，不让整个 BLE 采集和模型推理崩溃。

它们内部调用：

```python
_safe_call()
```

### 16.12 工具方法

#### `_safe_call(func)`

逻辑：

- 如果数据库没启用，返回 None。
- try 执行业务。
- 任何异常都返回 None。

#### `_generate_token()`

调用 `security.generate_access_token()`。

#### `_find_device(session, address)`

按 BLE 地址查设备。

#### `_find_user(session, subject_id)`

根据 username、student_no 或 email 查用户。

#### `_dt_from_ms(value)`

把毫秒时间戳转 UTC datetime。

#### `_user_to_dict()`

把 User ORM 对象转前端字典。

#### `_device_to_dict()`

把 Device ORM 对象转字典。

#### `_sensor_session_to_dict()`

把 SensorSession ORM 对象转字典。

#### `_evaluation_to_dict()`

把 EvaluationResult ORM 对象转字典。

#### `_model_to_dict()`

把 ModelVersion ORM 对象转字典。

#### `_report_to_dict()`

把 TrainingReport ORM 对象转字典。

### 16.13 老师可能问

**问：为什么要有 safe 方法？**

答：

> 传感器采集和模型推理是核心链路，不能因为数据库暂时不可用就完全停止。safe 方法让数据库写入失败时系统仍能继续实时采集，最多是数据库记录缺失。

**问：用户首页统计从哪里来？**

答：

> 从 `sensor_sessions` 和 `evaluation_results` 表聚合，计算总次数、总时长、平均分、标签分布和趋势。

---

## 17. `pc_gateway/schemas.py`

### 17.1 文件定位

`schemas.py` 定义普通业务 API 的请求和响应模型。

使用 Pydantic。

作用：

> 在请求进入业务层之前做数据校验，避免非法参数直接进入 `service.py`。

### 17.2 `ConnectRequest`

用于连接设备。

字段：

| 字段 | 说明 |
|---|---|
| `address` | 可选 BLE 地址 |
| `device_name` | 目标设备名，默认配置中的设备名 |
| `timeout_s` | 扫描超时，范围 1-30 秒 |

### 17.3 `StartRecordingRequest`

用于开始采集。

字段：

| 字段 | 说明 |
|---|---|
| `label` | 标签，不能为空 |
| `subject_id` | 用户或受试者 ID |
| `notes` | 备注 |

### 17.4 `StartModelTrainingRequest`

用于训练模型。

字段：

| 字段 | 说明 |
|---|---|
| `labels` | 要训练的标签列表 |
| `window_size` | 窗口大小，5-200 |
| `step_size` | 步长，1-100 |
| `auto_reload` | 训练成功后是否自动重载模型 |

### 17.5 `RemoveLabelFromModelRequest`

用于从模型中移除标签。

字段：

| 字段 | 说明 |
|---|---|
| `label` | 要移除的标签 |
| `window_size` | 重新训练窗口大小 |
| `step_size` | 重新训练步长 |
| `auto_reload` | 是否自动重载 |

本质：

> 移除标签就是排除该标签后重新训练。

### 17.6 `CreateLabelRequest`

用于创建标签。

字段：

| 字段 | 限制 |
|---|---|
| `label` | 1-48 个字符 |

### 17.7 `ScanResponse`

扫描设备响应。

字段：

```python
devices: list[dict]
```

### 17.8 `LabelsResponse`

标签列表响应。

字段：

| 字段 | 说明 |
|---|---|
| `recommended` | 推荐标签 |
| `available` | 已有标签 |
| `counts` | 每个标签样本文件数 |

### 17.9 老师可能问

**问：为什么要 Pydantic？**

答：

> 它可以自动校验请求参数，比如窗口大小不能小于 5，扫描时间不能超过 30 秒。这样错误会在接口层被拦截，业务层更安全。

---

## 18. `pc_gateway/db_schemas.py`

### 18.1 文件定位

`db_schemas.py` 定义认证相关 API 请求模型。

目前只有两个：

- 注册。
- 登录。

### 18.2 `RegisterUserRequest`

字段：

| 字段 | 限制 |
|---|---|
| `username` | 3-64 个字符 |
| `password` | 8-128 个字符 |

### 18.3 `LoginRequest`

字段：

| 字段 | 限制 |
|---|---|
| `username` | 3-64 个字符 |
| `password` | 8-128 个字符 |

### 18.4 为什么独立成 `db_schemas.py`

因为认证和数据库用户相关模型可以和普通设备/训练 API 分开管理。

答辩说法：

> `schemas.py` 放设备、采集、模型训练接口模型，`db_schemas.py` 放用户认证接口模型，逻辑更清晰。

---

## 19. `pc_gateway/security.py`

### 19.1 文件定位

`security.py` 负责用户系统的安全工具。

它处理：

- 密码哈希。
- 密码验证。
- token 生成。
- token 过期时间。

### 19.2 `_now()`

返回当前 UTC 时间。

### 19.3 `hash_password(password, iterations=200_000)`

作用：

- 把明文密码转成不可逆哈希。

步骤：

1. 生成 16 字节随机盐：

```python
os.urandom(16)
```

2. 使用 PBKDF2-HMAC-SHA256：

```python
hashlib.pbkdf2_hmac("sha256", password, salt, iterations)
```

3. 把算法、迭代次数、盐、摘要拼成字符串：

```text
pbkdf2_sha256$200000$salt$digest
```

### 19.4 `verify_password(password, stored_hash)`

作用：

- 验证明文密码是否匹配数据库中的哈希。

步骤：

1. 拆分 `stored_hash`。
2. 检查算法是否是 `pbkdf2_sha256`。
3. 解码 salt。
4. 用同样参数重新计算 digest。
5. 用 `hmac.compare_digest()` 比较。

为什么用 `compare_digest()`：

> 它比普通 `==` 更适合比较敏感数据，可以降低时序攻击风险。

### 19.5 `generate_access_token()`

作用：

- 生成随机 token。

使用：

```python
secrets.token_urlsafe(32)
```

### 19.6 `token_expiry()`

作用：

- 根据配置中的 `TOKEN_TTL_HOURS` 计算 token 过期时间。

默认一般是 168 小时，也就是 7 天。

### 19.7 老师可能问

**问：密码有没有明文保存？**

答：

> 没有。密码通过 PBKDF2-HMAC-SHA256 加随机盐哈希后保存，数据库里只有哈希字符串。

**问：当前安全还有什么不足？**

答：

> 当前是本地原型，局域网使用 HTTP。正式上线需要 HTTPS、更严格的 token 管理、权限控制和防暴力破解。

---

## 20. `ml_pipeline/prepare_dataset.py`

### 20.1 文件定位

这是机器学习数据准备脚本。

它把原始 CSV 变成模型训练需要的特征数据。

输入：

```text
ml_pipeline/data/raw/<label>/*.csv
```

输出：

```text
ml_pipeline/data/processed/windows/windows.csv
ml_pipeline/data/processed/features/features.csv
ml_pipeline/data/processed/labels/label_map.json
ml_pipeline/data/processed/labels/dataset_meta.json
ml_pipeline/data/splits/train.csv
ml_pipeline/data/splits/val.csv
ml_pipeline/data/splits/test.csv
```

### 20.2 常量

#### `FEATURE_COLUMNS`

```python
["ax", "ay", "az", "gx", "gy", "gz", "flexIndex"]
```

#### `REQUIRED_COLUMNS`

```python
["label", "seq", "timestampMs", *FEATURE_COLUMNS]
```

意思：

> 每个训练 CSV 至少要有标签、序号、设备时间戳和 7 个传感器特征。

### 20.3 `parse_args()`

解析命令行参数。

参数：

| 参数 | 默认 | 作用 |
|---|---:|---|
| `--data-root` | `ml_pipeline/data` | 数据根目录 |
| `--window-size` | 20 | 每个窗口多少条数据 |
| `--step-size` | 5 | 滑动窗口步长 |
| `--labels` | None | 只处理指定标签 |
| `--train-size` | 0.7 | 训练集比例 |
| `--val-size` | 0.15 | 验证集比例 |
| `--test-size` | 0.15 | 测试集比例 |

### 20.4 `ensure_dirs(data_root)`

作用：

- 创建必要目录。

创建：

```text
raw
processed/windows
processed/features
processed/labels
splits
```

返回这些路径的字典。

### 20.5 `load_csv_files(raw_root, labels=None)`

作用：

- 扫描 raw 目录下所有标签文件夹。
- 找到每个标签下的 CSV。
- 如果指定 labels，就只读取这些标签。

返回：

```python
[(label, csv_path), ...]
```

### 20.6 `validate_columns(df, csv_path)`

作用：

- 检查 CSV 是否包含必需字段。
- 缺字段就抛 `ValueError`。

为什么重要：

> 如果缺少 `flexIndex` 或 IMU 字段，训练出的特征就不完整，模型无法训练。

### 20.7 `build_window_records(label, csv_path, df, window_size, step_size)`

这是核心特征提取函数。

输入：

- 标签。
- CSV 路径。
- pandas DataFrame。
- 窗口大小。
- 步长。

执行流程：

1. 重置 DataFrame 索引。
2. 如果数据长度小于窗口大小，返回空。
3. 从第 0 行开始滑动窗口。
4. 每个窗口长度为 `window_size`。
5. 每次起点增加 `step_size`。
6. 对窗口内 7 个信号提取统计特征。
7. 保存窗口元信息。

窗口元信息包括：

- label。
- source_file。
- source_path。
- window_index。
- start_row。
- end_row。
- start_seq。
- end_seq。
- start_timestamp_ms。
- end_timestamp_ms。

每个信号提取：

| 统计量 | 含义 |
|---|---|
| `mean` | 平均值 |
| `std` | 标准差 |
| `min` | 最小值 |
| `max` | 最大值 |
| `ptp` | 峰峰值 |
| `rms` | 均方根 |

### 20.8 `split_by_file(features_df, args)`

作用：

- 按源 CSV 文件划分训练集、验证集、测试集。

为什么不是随机按窗口划分：

> 同一次采集切出来的窗口高度相似。如果随机按窗口划分，同一次采集可能同时出现在训练集和测试集，导致测试准确率虚高。

流程：

1. 提取 `source_file` 和 `label` 的唯一组合。
2. 检查至少 3 个源文件。
3. 用 `train_test_split` 划分 train 和 temp。
4. 再把 temp 划成 val 和 test。
5. 根据文件名筛选原 features_df。

使用：

```python
stratify=files_df["label"]
```

含义：

> 尽量保持各类别比例一致。

### 20.9 `main()`

完整执行流程：

1. 解析参数。
2. 创建目录。
3. 读取 labels 参数。
4. 扫描 CSV 文件。
5. 如果没有 CSV，退出。
6. 遍历每个 CSV：
   - 读 CSV。
   - 校验字段。
   - 提取窗口特征。
7. 如果没有生成窗口，退出。
8. 保存 `windows.csv`。
9. 生成 `label_map.json`。
10. 添加 `label_id`。
11. 保存 `features.csv`。
12. 调用 `split_by_file()` 划分数据集。
13. 保存 `train.csv`、`val.csv`、`test.csv`。
14. 生成 `dataset_meta.json`。
15. 打印 summary JSON。

### 20.10 老师可能问

**问：窗口大小 20 是什么意思？**

答：

> 设备约 10Hz 发送数据，窗口大小 20 表示大约用 2 秒的数据作为一个识别样本。这样可以捕捉动作过程，而不是只看一个瞬间。

**问：步长 5 是什么意思？**

答：

> 每次窗口向后移动 5 条数据，这样窗口之间有重叠，可以增加训练样本数量，并保持动作连续性。

---

## 21. `ml_pipeline/train_baseline.py`

### 21.1 文件定位

这是基础模型训练脚本。

它读取 `prepare_dataset.py` 输出的数据集，训练 Random Forest 分类器。

### 21.2 `NON_FEATURE_COLUMNS`

这些列不是模型输入特征：

```text
label, label_id, source_file, source_path,
window_index, start_row, end_row,
start_seq, end_seq,
start_timestamp_ms, end_timestamp_ms
```

解释：

- `label` 和 `label_id` 是答案，不能作为输入。
- `source_file` 等是数据来源信息，不能让模型“记文件名”。
- `window_index` 和行号也不是动作信号。

### 21.3 `parse_args()`

参数：

```text
--n-jobs
```

默认：

```text
1
```

说明：

> Windows 上多进程有时不稳定，所以默认单线程训练。

### 21.4 `load_split(csv_path)`

作用：

- 检查 split 文件是否存在。
- 用 pandas 读取。

如果文件不存在：

- 抛 `FileNotFoundError`。

### 21.5 `select_feature_columns(df)`

作用：

- 从 DataFrame 里筛出真正的特征列。
- 排除 `NON_FEATURE_COLUMNS`。

最终一般得到 42 个特征。

### 21.6 `main()`

完整训练流程：

1. 解析参数。
2. 确定数据目录。
3. 创建 models 目录。
4. 读取：
   - `train.csv`
   - `val.csv`
   - `test.csv`
5. 选择特征列。
6. 读取 label_map 和 dataset_meta。
7. 拆分 X 和 y：
   - `x_train`
   - `y_train`
   - `x_val`
   - `y_val`
   - `x_test`
   - `y_test`
8. 检查至少两个类别。
9. 创建 Random Forest 模型。
10. 训练模型。
11. 在验证集和测试集预测。
12. 计算指标。
13. 保存模型。
14. 保存 metrics。
15. 打印简要结果。

### 21.7 Random Forest 参数

```python
RandomForestClassifier(
    n_estimators=300,
    max_depth=None,
    min_samples_split=2,
    min_samples_leaf=1,
    random_state=42,
    n_jobs=args.n_jobs,
    class_weight="balanced",
)
```

解释：

| 参数 | 含义 |
|---|---|
| `n_estimators=300` | 300 棵决策树 |
| `max_depth=None` | 不限制树深度 |
| `min_samples_split=2` | 节点至少 2 个样本才可分裂 |
| `min_samples_leaf=1` | 叶子节点至少 1 个样本 |
| `random_state=42` | 固定随机种子，保证复现实验 |
| `n_jobs` | 并行线程数 |
| `class_weight="balanced"` | 自动平衡类别权重 |

### 21.8 输出指标

`metrics.json` 包含：

| 字段 | 说明 |
|---|---|
| `feature_count` | 特征数量 |
| `train_samples` | 训练样本数 |
| `val_samples` | 验证样本数 |
| `test_samples` | 测试样本数 |
| `val_accuracy` | 验证准确率 |
| `test_accuracy` | 测试准确率 |
| `classification_report` | 精确率、召回率、F1 |
| `confusion_matrix` | 混淆矩阵 |

### 21.9 模型文件

保存到：

```text
ml_pipeline/data/models/random_forest_model.joblib
```

内容：

```python
{
    "model": model,
    "feature_columns": feature_columns,
    "label_map": label_map,
    "dataset_meta": dataset_meta,
}
```

为什么不只保存 model：

> 实时推理必须知道训练时用的特征列、标签映射和窗口大小，所以这些元信息要和模型一起保存。

### 21.10 老师可能问

**问：为什么至少两个标签？**

答：

> 分类模型必须学习类别之间的差异。如果只有一个标签，模型没有对比对象，训练出来也只能永远预测这个标签。

**问：为什么用 `class_weight="balanced"`？**

答：

> 采集数据可能不均衡，比如静止样本多、错误动作样本少。平衡类别权重可以降低样本不均衡对模型的影响。

---

## 22. 文件之间的职责边界

### 22.1 `api.py` 和 `service.py`

| 文件 | 职责 |
|---|---|
| `api.py` | 接口层，处理 HTTP/WebSocket |
| `service.py` | 业务层，处理设备、采集、模型、数据库、广播 |

答辩说法：

> API 层不直接写复杂业务，避免接口文件过度臃肿。

### 22.2 `models.py` 和 `schemas.py`

| 文件 | 职责 |
|---|---|
| `models.py` | 网关内部数据结构 |
| `schemas.py` | API 请求/响应校验 |

### 22.3 `db_models.py` 和 `db_service.py`

| 文件 | 职责 |
|---|---|
| `db_models.py` | 定义数据库表 |
| `db_service.py` | 操作数据库业务 |

### 22.4 `inference.py` 和 `evaluation.py`

| 文件 | 职责 |
|---|---|
| `inference.py` | 机器学习动作分类 |
| `evaluation.py` | 基于规则的动作质量评分 |

### 22.5 `prepare_dataset.py` 和 `train_baseline.py`

| 文件 | 职责 |
|---|---|
| `prepare_dataset.py` | 原始数据转特征 |
| `train_baseline.py` | 特征训练模型 |

---

## 23. 答辩高频追问速记

### 23.1 老师问：你的 Python 后端入口在哪里？

回答：

> 入口是 `pc_gateway/__main__.py` 和 `pc_gateway/main.py`。`__main__.py` 负责支持 `python -m pc_gateway` 启动，`main.py` 负责选端口、检测局域网 IP、检查 FastAPI 应用能否导入，然后用 Uvicorn 启动 `pc_gateway.api:app`。

### 23.2 老师问：实时数据怎么从设备到网页？

回答：

> ESP32 通过 BLE Notify 发 CSV 数据，`service.py` 里的 `_notification_handler` 接收后交给 `_process_packet`，再用 `SensorPacket.from_payload` 解析，随后送入 recorder、inference、evaluation，最后通过 WebSocket 广播给网页。

### 23.3 老师问：训练模型时后端做了什么？

回答：

> 调试模式调用 `/api/models/train`，API 层转给 `GatewayService.start_model_training`，它后台运行 `prepare_dataset.py` 生成窗口特征和数据集切分，再运行 `train_baseline.py` 训练随机森林，训练成功后保存 joblib 模型并自动重载。

### 23.4 老师问：标准度评分怎么计算？

回答：

> `evaluation.py` 里计算三个子分数：动作幅度、稳定性和节奏。综合分是 `0.4*幅度 + 0.35*稳定性 + 0.25*节奏`。错误动作标签还会限制最高分，避免模型识别为错误但评分过高。

### 23.5 老师问：数据库表怎么和功能对应？

回答：

> 用户存在 `users`，登录 token 存 `user_tokens`，设备存 `devices`，采集会话存 `sensor_sessions`，模型版本存 `model_versions`，动作评分存 `evaluation_results`，训练报告存 `training_reports`。

### 23.6 老师问：如果数据库断了怎么办？

回答：

> 项目有 `safe_*` 数据库方法。数据库异常不会影响 BLE 采集、CSV 保存和模型推理，只是用户系统和数据库报告功能受影响。

### 23.7 老师问：为什么普通用户不选训练标签？

回答：

> 标签是开发者采集训练数据时使用的概念。普通用户只应该开始训练并获得反馈。代码里用 `user_auto_training` 区分普通用户训练，避免把未经人工确认的用户训练数据直接混入模型训练集。

---

## 24. 最建议你背熟的 6 个文件

如果时间有限，优先背这 6 个：

| 文件 | 为什么重要 |
|---|---|
| `pc_gateway/service.py` | 项目后端大脑，老师最可能问 |
| `pc_gateway/api.py` | 所有接口和 WebSocket |
| `pc_gateway/inference.py` | 机器学习实时推理 |
| `pc_gateway/evaluation.py` | 标准度评分和纠错建议 |
| `ml_pipeline/prepare_dataset.py` | 数据怎么变成特征 |
| `ml_pipeline/train_baseline.py` | 模型怎么训练 |

一句话背法：

> `service.py` 串流程，`api.py` 暴露接口，`inference.py` 识别动作，`evaluation.py` 评估质量，`prepare_dataset.py` 做特征，`train_baseline.py` 训练模型。

