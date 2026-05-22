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


@asynccontextmanager
async def lifespan(_: FastAPI):
    yield
    await gateway_service.close()


app = FastAPI(
    title="Smart Fitness PC Gateway",
    version="0.2.0",
    lifespan=lifespan,
)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", include_in_schema=False)
async def index() -> RedirectResponse:
    return RedirectResponse(url="/login", status_code=307)


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


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/status")
async def get_status() -> dict:
    return gateway_service.get_status()


@app.get("/api/labels", response_model=LabelsResponse)
async def get_labels() -> dict:
    return gateway_service.get_labels()


@app.post("/api/labels")
async def create_label(request: CreateLabelRequest) -> dict:
    try:
        return gateway_service.create_label(request.label)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.delete("/api/labels/{label}")
async def delete_label(label: str) -> dict:
    try:
        return await gateway_service.delete_label(label)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/devices/scan", response_model=ScanResponse)
async def scan_devices(
    timeout_s: float = Query(default=config.DEFAULT_SCAN_TIMEOUT_S, ge=1.0, le=30.0),
) -> dict:
    devices = await gateway_service.scan_devices(timeout_s)
    return {"devices": devices}


@app.post("/api/device/connect")
async def connect_device(request: ConnectRequest) -> dict:
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
    return await gateway_service.disconnect()


@app.post("/api/recordings/start")
async def start_recording(request: StartRecordingRequest) -> dict:
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
    session = await gateway_service.stop_recording()
    return {"session": session}


@app.get("/api/recordings/active")
async def get_active_recording() -> dict:
    return {"session": gateway_service.get_status().get("activeSession")}


@app.get("/api/recordings")
async def list_recordings(limit: int = Query(default=100, ge=1, le=500)) -> dict:
    return {"items": gateway_service.list_recordings(limit)}


@app.delete("/api/recordings/{session_id}")
async def delete_recording(session_id: str) -> dict:
    try:
        return await gateway_service.delete_recording(session_id)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/inference/status")
async def get_inference_status() -> dict:
    return gateway_service.get_inference_status()


@app.get("/api/evaluation/status")
async def get_evaluation_status() -> dict:
    return gateway_service.get_evaluation_status()


@app.get("/api/evaluation/server-status")
async def get_advanced_evaluation_status() -> dict:
    return gateway_service.get_advanced_evaluation_status()


@app.post("/api/inference/reload")
async def reload_inference_model() -> dict:
    return await gateway_service.reload_inference_model()


@app.get("/api/models/training/status")
async def get_model_training_status() -> dict:
    return gateway_service.get_model_training_status()


@app.post("/api/models/train")
async def start_model_training(request: StartModelTrainingRequest) -> dict:
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
    try:
        return gateway_service.clear_model_training_status()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/report/summary")
async def get_report_summary() -> dict:
    return gateway_service.get_report_summary()


@app.get("/api/database/status")
async def get_database_status() -> dict:
    return gateway_service.get_database_status()


@app.post("/api/database/init")
async def init_database() -> dict:
    try:
        return gateway_service.init_database()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/auth/register")
async def register_user(request: RegisterUserRequest) -> dict:
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
    try:
        return gateway_service.login_user(
            username=request.username,
            password=request.password,
        )
    except Exception as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


@app.get("/api/auth/me")
async def get_current_user(authorization: str | None = Header(default=None)) -> dict:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token.")

    token = authorization.split(" ", 1)[1].strip()
    try:
        return {"user": gateway_service.get_current_user(token)}
    except Exception as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


@app.get("/api/report/user-summary")
async def get_user_dashboard(authorization: str | None = Header(default=None)) -> dict:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token.")

    token = authorization.split(" ", 1)[1].strip()
    try:
        return gateway_service.get_user_dashboard(token)
    except Exception as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


@app.get("/api/database/users")
async def list_database_users(limit: int = Query(default=50, ge=1, le=200)) -> dict:
    try:
        return {"items": gateway_service.list_database_users(limit)}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/database/sessions")
async def list_database_sessions(limit: int = Query(default=100, ge=1, le=500)) -> dict:
    try:
        return {"items": gateway_service.list_database_sessions(limit)}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/database/evaluations")
async def list_database_evaluations(limit: int = Query(default=100, ge=1, le=500)) -> dict:
    try:
        return {"items": gateway_service.list_database_evaluations(limit)}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/database/models")
async def list_database_models(limit: int = Query(default=20, ge=1, le=100)) -> dict:
    try:
        return {"items": gateway_service.list_database_models(limit)}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/database/reports")
async def list_database_reports(limit: int = Query(default=50, ge=1, le=200)) -> dict:
    try:
        return {"items": gateway_service.list_database_reports(limit)}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.websocket("/ws/live")
async def live_stream(websocket: WebSocket) -> None:
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
