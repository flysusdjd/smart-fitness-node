"""PC 网关 HTTP/WebSocket 接口：把前端页面、设备连接、采集、训练、认证和数据库能力暴露给浏览器。"""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from . import config
from .db_schemas import LoginRequest, RegisterUserRequest
from .schemas import (
    ConnectRequest,
    CreateLabelRequest,
    LabelsResponse,
    RemoveLabelFromModelRequest,
    ScanResponse,
    StartModelTrainingRequest,
    StartRecordingRequest,
)
from .service import GatewayService


gateway_service = GatewayService()
STATIC_DIR = Path(__file__).resolve().parent / "static"


# 应用生命周期：关闭服务时主动断开 BLE 并停止采集。
@asynccontextmanager
async def lifespan(_: FastAPI):
    yield
    await gateway_service.close()


# FastAPI 应用实例，挂载静态页面并注册所有业务接口。
app = FastAPI(
    title="Smart Fitness PC Gateway",
    version="0.2.0",
    lifespan=lifespan,
)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


# 根路径统一跳转到登录页。
@app.get("/", include_in_schema=False)
async def index() -> RedirectResponse:
    return RedirectResponse(url="/login", status_code=307)


# 这些路由都返回同一个前端单页应用，由浏览器端 JS 负责页面切换。
@app.get("/login", include_in_schema=False)
@app.get("/dashboard", include_in_schema=False)
@app.get("/training", include_in_schema=False)
@app.get("/history", include_in_schema=False)
@app.get("/debug", include_in_schema=False)
async def spa_pages() -> FileResponse:
    return FileResponse(
        STATIC_DIR / "index.html",
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )


# 健康检查接口，供启动脚本或浏览器快速确认服务可用。
@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


# 网关状态、标签、设备扫描和 BLE 连接相关接口。
# 这组接口主要被网页训练中心和调试模式调用，负责“设备是否在线、有哪些训练标签、能否连接硬件”。
@app.get("/api/status")
async def get_status() -> dict:
    # 返回当前网关的综合状态：BLE 连接状态、最新数据包、当前是否正在采集等。
    # 前端初始化页面和 WebSocket 断线重连后都会用它补一次完整状态。
    return gateway_service.get_status()


@app.get("/api/labels", response_model=LabelsResponse)
async def get_labels() -> dict:
    # 返回训练标签列表和每个标签已有多少组样本。
    # 调试模式的“管理员训练模型”面板靠这个接口判断哪些标签可以参与训练。
    return gateway_service.get_labels()


@app.post("/api/labels")
async def create_label(request: CreateLabelRequest) -> dict:
    # 新增一个采集/训练标签，例如 bench_standard、bench_wrong。
    # request 由 Pydantic 校验，避免空标签或过长标签进入后端。
    try:
        return gateway_service.create_label(request.label)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.delete("/api/labels/{label}")
async def delete_label(label: str) -> dict:
    # 删除某个标签及其对应的原始采集数据。
    # 注意：这只删除数据标签，不等价于直接删除已训练好的模型文件。
    try:
        return await gateway_service.delete_label(label)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/devices/scan", response_model=ScanResponse)
async def scan_devices(
    timeout_s: float = Query(default=config.DEFAULT_SCAN_TIMEOUT_S, ge=1.0, le=30.0),
) -> dict:
    # 扫描附近 BLE 设备，返回名称、地址、信号强度等列表。
    # 前端“扫描设备”按钮调用这里，真正的扫描由 GatewayService 调用 Bleak 完成。
    devices = await gateway_service.scan_devices(timeout_s)
    return {"devices": devices}


@app.post("/api/device/connect")
async def connect_device(request: ConnectRequest) -> dict:
    # 连接指定 BLE 地址；如果前端没有传 address，就按默认设备名扫描并连接。
    # 连接成功后，后端会订阅 ESP32-S3 的 Notify 数据流。
    try:
        return await gateway_service.connect(
            address=request.address,
            device_name=request.device_name,
            timeout_s=request.timeout_s,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/device/disconnect")
async def disconnect_device() -> dict:
    # 主动断开 BLE 设备连接，通常由训练中心或调试模式的“断开连接”按钮触发。
    return await gateway_service.disconnect()


# 采集会话接口：控制开始、停止、查看和删除本地训练记录。
@app.post("/api/recordings/start")
async def start_recording(request: StartRecordingRequest) -> dict:
    # 开始一组采集会话。普通用户训练时会用自动识别标签，开发者采集数据时会传具体标签。
    # 后端会同时准备 CSV/JSON 文件，并在数据库中记录 session 元信息。
    try:
        return await gateway_service.start_recording(
            label=request.label,
            subject_id=request.subject_id,
            notes=request.notes,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/recordings/stop")
async def stop_recording() -> dict:
    # 停止当前采集会话并保存结果。
    # 返回 session 是为了让前端能立刻展示这次训练/采集记录。
    session = await gateway_service.stop_recording()
    return {"session": session}


@app.get("/api/recordings/active")
async def get_active_recording() -> dict:
    # 查询当前是否存在正在进行的采集会话，用于页面刷新后恢复按钮状态。
    return {"session": gateway_service.get_status().get("activeSession")}


@app.get("/api/recordings")
async def list_recordings(limit: int = Query(default=100, ge=1, le=500)) -> dict:
    # 返回本地训练/采集记录列表，调试模式里的“训练模型记录”从这里读取。
    return {"items": gateway_service.list_recordings(limit)}


@app.delete("/api/recordings/{session_id}")
async def delete_recording(session_id: str) -> dict:
    # 删除某一次采集记录，包含 CSV、JSON 元数据和数据库对应记录。
    # 这里按 session_id 删除，比按文件名删除更安全。
    try:
        return await gateway_service.delete_recording(session_id)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


# 推理、评估和模型训练接口。
# 这组接口区分两个概念：
# 1. 推理接口：加载模型、查看模型状态，用于实时识别动作类别。
# 2. 训练接口：后台调用 ml_pipeline 重新训练模型，用于开发者维护标签和模型。
@app.get("/api/inference/status")
async def get_inference_status() -> dict:
    # 返回轻量级动作识别模型状态，例如模型是否加载、当前预测标签和置信度。
    return gateway_service.get_inference_status()


@app.get("/api/evaluation/status")
async def get_evaluation_status() -> dict:
    # 返回动作评估结果：动作阶段、标准度、深度/稳定性/节奏分数和纠正建议。
    return gateway_service.get_evaluation_status()


@app.get("/api/evaluation/server-status")
async def get_advanced_evaluation_status() -> dict:
    # 返回更复杂的服务端评估状态。
    # 这里对应项目规划里的“服务端训练/评估更复杂动作质量模型”的预留能力。
    return gateway_service.get_advanced_evaluation_status()


@app.post("/api/inference/reload")
async def reload_inference_model() -> dict:
    # 重新加载磁盘上的最新模型文件。
    # 管理员训练成功后，如果选择自动重载，会间接调用同样的逻辑。
    return await gateway_service.reload_inference_model()


@app.get("/api/models/training/status")
async def get_model_training_status() -> dict:
    # 查询后台训练任务状态：是否运行、训练阶段、日志、最近成功时间等。
    # 前端调试模式会定期或刷新时读取它，避免用户不知道训练是否结束。
    return gateway_service.get_model_training_status()


@app.post("/api/models/train")
async def start_model_training(request: StartModelTrainingRequest) -> dict:
    # 启动一次后台模型训练任务。
    # request.labels 决定参与训练的标签范围，window/step 决定滑窗切样本方式。
    try:
        return await gateway_service.start_model_training(
            labels=request.labels,
            window_size=request.window_size,
            step_size=request.step_size,
            auto_reload=request.auto_reload,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/models/remove-label")
async def remove_label_from_model(request: RemoveLabelFromModelRequest) -> dict:
    # “从模型中移除标签”的本质不是改模型内部参数，而是用剩余标签重新训练一个新模型。
    # 这样可以保留原始数据，同时让最新模型不再输出被移除的标签。
    try:
        return await gateway_service.remove_label_from_model(
            label=request.label,
            window_size=request.window_size,
            step_size=request.step_size,
            auto_reload=request.auto_reload,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/models/training/reset")
async def reset_model_training_status() -> dict:
    # 清空训练状态面板里的历史任务状态，不删除模型文件和训练数据。
    try:
        return gateway_service.clear_model_training_status()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


# 报告、数据库和认证相关接口。
# 这组接口支撑“用户系统、数据库同步、个人首页和历史报告”。
@app.get("/api/report/summary")
async def get_report_summary() -> dict:
    # 返回不依赖登录用户的本地报告汇总，用于首页/调试页展示总体训练情况。
    return gateway_service.get_report_summary()


@app.get("/api/database/status")
async def get_database_status() -> dict:
    # 返回数据库是否启用、是否连接成功、数据库类型等状态。
    # 调试模式可以用它说明 MySQL 是否已经接入。
    return gateway_service.get_database_status()


@app.post("/api/database/init")
async def init_database() -> dict:
    # 初始化数据库表结构。通常只在首次接入 MySQL 或重建数据库时使用。
    try:
        return gateway_service.init_database()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/auth/register")
async def register_user(request: RegisterUserRequest) -> dict:
    # 注册用户账号。网页端和安卓端都调用这个接口，所以账号可以互通。
    # 当前只要求用户名和密码，复杂资料后续可以再扩展。
    try:
        user = gateway_service.register_user(
            username=request.username,
            password=request.password,
        )
        return {"user": user}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/auth/login")
async def login_user(request: LoginRequest) -> dict:
    # 登录用户并返回访问令牌 accessToken。
    # 前端/安卓端后续访问需要身份的接口时，会把它放到 Authorization: Bearer 头里。
    try:
        return gateway_service.login_user(
            username=request.username,
            password=request.password,
        )
    except Exception as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


@app.get("/api/auth/me")
async def get_current_user(authorization: str | None = Header(default=None)) -> dict:
    # 根据 Authorization 请求头里的 Bearer Token 解析当前用户。
    # 这是“记住登录状态”的关键：页面刷新后用 token 换回用户信息。
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token.")

    token = authorization.split(" ", 1)[1].strip()
    try:
        return {"user": gateway_service.get_current_user(token)}
    except Exception as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


@app.get("/api/report/user-summary")
async def get_user_dashboard(authorization: str | None = Header(default=None)) -> dict:
    # 返回当前登录用户的个人首页数据，如训练次数、时长、评分趋势等。
    # 它同样需要 Bearer Token，避免读取到其他用户的训练报告。
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token.")

    token = authorization.split(" ", 1)[1].strip()
    try:
        return gateway_service.get_user_dashboard(token)
    except Exception as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


@app.get("/api/database/users")
async def list_database_users(limit: int = Query(default=50, ge=1, le=200)) -> dict:
    # 调试模式查看用户表内容，便于答辩时展示数据库确实保存了账号数据。
    try:
        return {"items": gateway_service.list_database_users(limit)}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/database/sessions")
async def list_database_sessions(limit: int = Query(default=100, ge=1, le=500)) -> dict:
    # 调试模式查看采集会话表，确认每次开始/结束训练都会形成 session 记录。
    try:
        return {"items": gateway_service.list_database_sessions(limit)}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/database/evaluations")
async def list_database_evaluations(limit: int = Query(default=100, ge=1, le=500)) -> dict:
    # 调试模式查看评估结果表，展示标准度评分和纠正建议的持久化结果。
    try:
        return {"items": gateway_service.list_database_evaluations(limit)}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/database/models")
async def list_database_models(limit: int = Query(default=20, ge=1, le=100)) -> dict:
    # 调试模式查看模型版本表，说明模型训练完成后会记录版本信息。
    try:
        return {"items": gateway_service.list_database_models(limit)}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/database/reports")
async def list_database_reports(limit: int = Query(default=50, ge=1, le=200)) -> dict:
    # 调试模式查看训练报告表，支撑历史报告和长期趋势分析。
    try:
        return {"items": gateway_service.list_database_reports(limit)}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


# 实时 WebSocket：把状态、数据包、预测和评估结果推送给前端。
# HTTP 接口适合“点击按钮后请求一次”，WebSocket 适合“设备数据持续变化时由后端主动推送”。
@app.websocket("/ws/live")
async def live_stream(websocket: WebSocket) -> None:
    # 每个浏览器页面连接后都会在 GatewayService 中注册一个队列。
    # 后端收到 BLE 数据、生成预测或评估结果时，会把事件放进队列，这里再 send_json 给网页。
    await websocket.accept()
    queue = await gateway_service.subscribe()
    try:
        while True:
            message = await queue.get()
            await websocket.send_json(message)
    except WebSocketDisconnect:
        await gateway_service.unsubscribe(queue)
    except Exception:
        await gateway_service.unsubscribe(queue)
        raise
