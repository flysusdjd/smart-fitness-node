"""PC 网关核心服务：协调 BLE 连接、采集落盘、实时推理评估、模型训练和前端事件推送。"""

from __future__ import annotations

import asyncio
from asyncio.subprocess import PIPE
import json
import re
import shutil
import sys
import time
from pathlib import Path
from typing import Any

from bleak import BleakClient, BleakScanner

from .advanced_evaluation import AdvancedEvaluationService
from . import config
from .db_service import DatabaseService
from .evaluation import EvaluationEngine
from .inference import InferenceEngine
from .models import DeviceInfo, GatewayStatus, SensorPacket
from .recorder import SessionRecorder
from .reporting import ReportService


# 这些标签用于体验/自动记录，不参与模型训练类别。
NON_MODEL_LABELS = {"user_auto_training"}
# 中文输入和常见别名统一映射到模型内部标签，减少误建新目录。
LABEL_ALIASES = {
    "静止": "idle",
    "站立": "idle",
    "待机": "idle",
    "深蹲": "squat_standard",
    "标准深蹲": "squat_standard",
    "深蹲标准": "squat_standard",
    "深蹲_标准": "squat_standard",
    "深蹲错误": "squat_wrong",
    "错误深蹲": "squat_wrong",
    "深蹲_错误": "squat_wrong",
    "深蹲纠错": "squat_wrong",
    "卧推": "bench_standard",
    "标准卧推": "bench_standard",
    "卧推标准": "bench_standard",
    "卧推_标准": "bench_standard",
    "卧推错误": "bench_wrong",
    "错误卧推": "bench_wrong",
    "卧推_错误": "bench_wrong",
    "卧推纠错": "bench_wrong",
}


# 网关核心服务：协调 BLE、采集、推理、评估、模型训练、数据库和 WebSocket 推送。
class GatewayService:
    def __init__(self, data_root: Path | None = None) -> None:
        self._data_root = data_root or config.RAW_DATA_ROOT
        self._recorder = SessionRecorder(self._data_root)
        self._inference = InferenceEngine()
        self._evaluation = EvaluationEngine(window_size=self._inference.window_size)
        self._advanced_evaluation = AdvancedEvaluationService(window_size=self._inference.window_size)
        self._reporting = ReportService(data_root=self._data_root)
        self._database = DatabaseService()
        self._client: BleakClient | None = None
        self._device: DeviceInfo | None = None
        self._status = GatewayStatus(
            inference=self._inference.status_dict(),
            evaluation=self._evaluation.status_dict(),
            advanced_evaluation=self._advanced_evaluation.status_dict(),
            report_summary=self._reporting.build_summary(),
            database=self._database.status(),
        )
        self._subscribers: set[asyncio.Queue[dict[str, Any]]] = set()
        self._lock = asyncio.Lock()
        self._model_training_task: asyncio.Task[None] | None = None
        self._model_training_status: dict[str, Any] = {
            "running": False,
            "phase": "idle",
            "selectedLabels": [],
            "availableLabels": self._list_training_labels(),
            "windowSize": 20,
            "stepSize": 5,
            "autoReload": True,
            "startedAtIso": None,
            "finishedAtIso": None,
            "lastSuccessAtIso": None,
            "lastError": None,
            "prepareExitCode": None,
            "trainExitCode": None,
            "modelReloaded": False,
            "output": "",
        }
        self._database.safe_sync_current_model_version()

    # 应用关闭时停止采集并释放 BLE 连接。
    async def close(self) -> None:
        await self.stop_recording("service_shutdown")
        await self.disconnect()

    # 扫描附近 BLE 设备并返回排序后的候选列表。
    async def scan_devices(self, timeout_s: float = config.DEFAULT_SCAN_TIMEOUT_S) -> list[dict[str, Any]]:
        devices = await self._discover_devices(timeout_s)
        return [device["info"].to_dict() for device in devices]

    # 连接目标 ESP32 设备，订阅通知并重置实时推理/评估状态。
    async def connect(
        self,
        *,
        address: str | None = None,
        device_name: str = config.DEVICE_NAME,
        timeout_s: float = config.DEFAULT_SCAN_TIMEOUT_S,
    ) -> dict[str, Any]:
        async with self._lock:
            if self._client is not None and self._client.is_connected:
                return self.get_status()

            target = await self._find_device(address=address, device_name=device_name, timeout_s=timeout_s)
            client = BleakClient(target["device"], disconnected_callback=self._on_ble_disconnect)
            await client.connect()
            # BLE 数据入口：订阅 ESP32-S3 固件暴露的 Characteristic Notify。
            # 设备每发一包传感器字符串，Bleak 就会回调 _notification_handler。
            await client.start_notify(config.CHARACTERISTIC_UUID, self._notification_handler)

            self._client = client
            self._device = target["info"]
            self._inference.clear_buffer()
            self._evaluation.clear()
            self._advanced_evaluation.clear()
            self._status.connected = True
            self._status.device_name = self._device.local_name or self._device.name
            self._status.device_address = self._device.address
            self._status.last_error = None
            self._status.inference = self._inference.status_dict()
            self._status.evaluation = self._evaluation.status_dict()
            self._status.advanced_evaluation = self._advanced_evaluation.status_dict()
            self._status.database = self._database.status()
            self._database.safe_upsert_device(self._device, status="online")

        await self._broadcast("status", self.get_status())
        await self._broadcast("evaluation_status", self._status.evaluation)
        await self._broadcast("advanced_evaluation_status", self._status.advanced_evaluation)
        return self.get_status()

    # 主动断开设备连接，同时停止采集并通知前端刷新状态。
    async def disconnect(self) -> dict[str, Any]:
        async with self._lock:
            client = self._client
            device_address = self._status.device_address
            self._client = None
            self._device = None
            self._status.connected = False
            self._status.device_name = None
            self._status.device_address = None
            self._inference.clear_buffer()
            self._evaluation.clear()
            self._advanced_evaluation.clear()
            self._status.inference = self._inference.status_dict()
            self._status.evaluation = self._evaluation.status_dict()
            self._status.advanced_evaluation = self._advanced_evaluation.status_dict()
            self._status.database = self._database.status()

        if client is not None and client.is_connected:
            await client.disconnect()

        self._database.safe_mark_device_offline(address=device_address)
        await self.stop_recording("manual_disconnect")
        await self._broadcast("status", self.get_status())
        await self._broadcast("evaluation_status", self._status.evaluation)
        await self._broadcast("advanced_evaluation_status", self._status.advanced_evaluation)
        return self.get_status()

    # 开始本地 CSV 采集，并尽量同步一条数据库会话记录。
    async def start_recording(
        self,
        *,
        label: str,
        subject_id: str | None,
        notes: str | None,
    ) -> dict[str, Any]:
        if not self._status.connected or self._device is None:
            raise RuntimeError("设备未连接，请先连接设备后再开始采集。")

        label = self._normalize_label_name(label)
        session = self._recorder.start(
            label=label,
            subject_id=subject_id,
            notes=notes,
            device_name=self._device.local_name or self._device.name,
            device_address=self._device.address,
        )
        self._status.recording = True
        self._status.active_session = session.to_dict()
        self._database.safe_create_sensor_session(
            local_session=session,
            device_address=self._device.address if self._device else None,
        )
        await self._broadcast("recording_started", session.to_dict())
        await self._broadcast("status", self.get_status())
        return session.to_dict()

    # 结束采集后写入数据库评估结果和报告快照。
    async def stop_recording(self, reason: str = "manual_stop") -> dict[str, Any] | None:
        session = self._recorder.stop(reason)
        self._status.recording = False
        self._status.active_session = None
        if session is not None:
            self._database.safe_finish_sensor_session(session)
            self._database.safe_save_evaluation_result(
                session_id=session.session_id,
                evaluation_status=self._status.evaluation,
            )
            self._status.report_summary = self._reporting.build_summary()
            self._database.safe_create_report_snapshot(self._status.report_summary)
            await self._broadcast("recording_stopped", session.to_dict())
            await self._broadcast("report_summary", self._status.report_summary)
            await self._broadcast("status", self.get_status())
            return session.to_dict()
        return None

    def get_status(self) -> dict[str, Any]:
        if self._recorder.active_session is not None:
            self._status.active_session = self._recorder.active_session.to_dict()
        else:
            self._status.active_session = None
        self._status.inference = self._inference.status_dict()
        self._status.evaluation = self._evaluation.status_dict()
        self._status.advanced_evaluation = self._advanced_evaluation.status_dict()
        if self._status.report_summary is None:
            self._status.report_summary = self._reporting.build_summary()
        self._status.database = self._database.status()
        return self._status.to_dict()

    # 统计本地标签目录和样本数量，并补齐推荐标签。
    def get_labels(self) -> dict[str, Any]:
        available = []
        if self._data_root.exists():
            for path in self._data_root.iterdir():
                if not path.is_dir():
                    continue
                if self._is_empty_alias_label_dir(path):
                    continue
                available.append(path.name)
        available = sorted(available)
        counts: dict[str, int] = {}
        for label in available:
            label_dir = self._data_root / label
            counts[label] = len(list(label_dir.glob("*.csv"))) if label_dir.exists() else 0
        for label in config.RECOMMENDED_LABELS:
            counts.setdefault(label, 0)
        return {
            "recommended": list(config.RECOMMENDED_LABELS),
            "available": available,
            "counts": counts,
        }

    def create_label(self, raw_label: str) -> dict[str, Any]:
        label = self._normalize_label_name(raw_label)
        label_dir = self._data_root / label
        existed = label_dir.exists()
        label_dir.mkdir(parents=True, exist_ok=True)
        return {
            "label": label,
            "created": not existed,
            "path": str(label_dir),
            "labels": self.get_labels(),
        }

    # 删除标签目录前检查正在采集/训练状态，并同步清理数据库记录。
    async def delete_label(self, raw_label: str) -> dict[str, Any]:
        label = self._normalize_label_name(raw_label)
        if self._recorder.active_session is not None and self._recorder.active_session.label == label:
            raise RuntimeError("当前标签正在采集中，请先结束采集后再删除。")
        if self._model_training_task is not None and not self._model_training_task.done():
            raise RuntimeError("模型正在训练中，请训练结束后再删除标签。")

        label_dir = (self._data_root / label).resolve()
        data_root = self._data_root.resolve()
        if data_root not in label_dir.parents:
            raise RuntimeError("标签路径不合法，已取消删除。")
        if not label_dir.exists() or not label_dir.is_dir():
            raise RuntimeError("标签不存在或还没有采集数据。")

        csv_count = len(list(label_dir.glob("*.csv")))
        meta_count = len(list(label_dir.glob("*.json")))
        shutil.rmtree(label_dir)
        db_deleted = self._database.safe_delete_sensor_sessions_by_label(label)
        self._status.report_summary = self._reporting.build_summary()
        await self._broadcast("report_summary", self._status.report_summary)
        await self._broadcast("status", self.get_status())
        return {
            "label": label,
            "deletedCsv": csv_count,
            "deletedMeta": meta_count,
            "databaseDeleted": db_deleted,
            "labels": self.get_labels(),
        }

    def get_model_training_status(self) -> dict[str, Any]:
        self._model_training_status["availableLabels"] = self._list_training_labels()
        return dict(self._model_training_status)

    def clear_model_training_status(self) -> dict[str, Any]:
        if self._model_training_task is not None and not self._model_training_task.done():
            raise RuntimeError("模型正在训练中，请等待训练结束后再清空状态。")

        self._model_training_status = {
            "running": False,
            "phase": "idle",
            "selectedLabels": [],
            "availableLabels": self._list_training_labels(),
            "windowSize": 20,
            "stepSize": 5,
            "autoReload": True,
            "startedAtIso": None,
            "finishedAtIso": None,
            "lastSuccessAtIso": None,
            "lastError": None,
            "prepareExitCode": None,
            "trainExitCode": None,
            "modelReloaded": False,
            "output": "",
        }
        return self.get_model_training_status()

    def list_recordings(self, limit: int = 100) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        if not self._data_root.exists():
            return records

        for label_dir in sorted(self._data_root.iterdir(), reverse=True):
            if not label_dir.is_dir():
                continue
            for meta_file in sorted(label_dir.glob("*.json"), reverse=True):
                try:
                    payload = json.loads(meta_file.read_text(encoding="utf-8"))
                except json.JSONDecodeError:
                    continue
                records.append(payload)
                if len(records) >= limit:
                    return records
        return records

    async def delete_recording(self, session_id: str) -> dict[str, Any]:
        if self._recorder.active_session is not None and self._recorder.active_session.session_id == session_id:
            raise RuntimeError("当前记录正在采集中，请先结束采集后再删除。")

        target_meta: Path | None = None
        payload: dict[str, Any] | None = None

        if self._data_root.exists():
            for meta_file in self._data_root.glob(f"**/{session_id}.json"):
                try:
                    payload = json.loads(meta_file.read_text(encoding="utf-8"))
                    target_meta = meta_file
                    break
                except json.JSONDecodeError:
                    continue

        if payload is None:
            raise RuntimeError("未找到对应的训练记录。")

        csv_path = Path(str(payload.get("csvPath") or ""))
        meta_path = Path(str(payload.get("metaPath") or target_meta))
        deleted_files: list[str] = []

        for file_path in [csv_path, meta_path]:
            if file_path and str(file_path) and file_path.exists():
                file_path.unlink()
                deleted_files.append(str(file_path))

        db_deleted = self._database.safe_delete_sensor_session(session_id)
        self._status.report_summary = self._reporting.build_summary()
        await self._broadcast("report_summary", self._status.report_summary)
        await self._broadcast("status", self.get_status())

        return {
            "sessionId": session_id,
            "deletedFiles": deleted_files,
            "databaseDeleted": db_deleted,
        }


    def get_inference_status(self) -> dict[str, Any]:
        return self._inference.status_dict()

    def get_evaluation_status(self) -> dict[str, Any]:
        return self._evaluation.status_dict()

    def get_advanced_evaluation_status(self) -> dict[str, Any]:
        return self._advanced_evaluation.status_dict()

    def get_report_summary(self) -> dict[str, Any]:
        summary = self._reporting.build_summary()
        self._status.report_summary = summary
        return summary

    def get_database_status(self) -> dict[str, Any]:
        self._status.database = self._database.status()
        return self._status.database

    def init_database(self) -> dict[str, Any]:
        status = self._database.init_schema()
        self._database.safe_sync_current_model_version()
        self._status.database = status
        return status

    def register_user(
        self,
        *,
        username: str,
        password: str,
    ) -> dict[str, Any]:
        return self._database.register_user(
            username=username,
            password=password,
        )

    def login_user(self, *, username: str, password: str) -> dict[str, Any]:
        return self._database.login(username=username, password=password)

    def get_current_user(self, token: str) -> dict[str, Any]:
        return self._database.current_user(token)

    def list_database_users(self, limit: int = 50) -> list[dict[str, Any]]:
        return self._database.list_users(limit)

    def list_database_sessions(self, limit: int = 100) -> list[dict[str, Any]]:
        return self._database.list_sensor_sessions(limit)

    def list_database_evaluations(self, limit: int = 100) -> list[dict[str, Any]]:
        return self._database.list_evaluations(limit)

    def list_database_models(self, limit: int = 20) -> list[dict[str, Any]]:
        return self._database.list_models(limit)

    def list_database_reports(self, limit: int = 50) -> list[dict[str, Any]]:
        return self._database.list_reports(limit)

    def get_user_dashboard(self, token: str) -> dict[str, Any]:
        return self._database.get_user_dashboard(token)

    async def reload_inference_model(self) -> dict[str, Any]:
        self._inference.load_model()
        self._evaluation = EvaluationEngine(window_size=self._inference.window_size)
        self._advanced_evaluation = AdvancedEvaluationService(window_size=self._inference.window_size)
        self._status.inference = self._inference.status_dict()
        self._status.evaluation = self._evaluation.status_dict()
        self._status.advanced_evaluation = self._advanced_evaluation.status_dict()
        self._database.safe_sync_current_model_version()
        await self._broadcast("inference_status", self._status.inference)
        await self._broadcast("evaluation_status", self._status.evaluation)
        await self._broadcast("advanced_evaluation_status", self._status.advanced_evaluation)
        await self._broadcast("status", self.get_status())
        return self._status.inference

    # 提交模型训练任务前校验标签数量和样本覆盖。
    async def start_model_training(
        self,
        *,
        labels: list[str],
        window_size: int,
        step_size: int,
        auto_reload: bool = True,
    ) -> dict[str, Any]:
        if self._model_training_task is not None and not self._model_training_task.done():
            raise RuntimeError("模型正在训练中，请等待当前训练结束。")

        available_labels = self._list_training_labels()
        selected_labels = [label for label in labels if label in available_labels]
        if not selected_labels:
            raise RuntimeError("请至少选择一个可训练标签。")
        label_counts = self.get_labels().get("counts", {})
        labels_with_samples = [label for label in selected_labels if int(label_counts.get(label, 0) or 0) > 0]
        if len(labels_with_samples) < 2:
            raise RuntimeError("至少需要两个有样本的数据标签才能训练模型。当前模型只有一个类别，所以静止也会被识别成深蹲。")
        selected_labels = labels_with_samples

        self._model_training_status.update({
            "running": True,
            "phase": "queued",
            "selectedLabels": selected_labels,
            "availableLabels": available_labels,
            "windowSize": int(window_size),
            "stepSize": int(step_size),
            "autoReload": bool(auto_reload),
            "startedAtIso": self._now_iso(),
            "finishedAtIso": None,
            "lastError": None,
            "prepareExitCode": None,
            "trainExitCode": None,
            "modelReloaded": False,
            "output": "训练任务已创建，等待开始。\n",
        })
        await self._broadcast("model_training_status", self.get_model_training_status())
        self._model_training_task = asyncio.create_task(
            self._run_model_training(selected_labels, int(window_size), int(step_size), bool(auto_reload))
        )
        return self.get_model_training_status()

    # 通过重新训练剩余类别来移除某个模型标签。
    async def remove_label_from_model(
        self,
        *,
        label: str,
        window_size: int,
        step_size: int,
        auto_reload: bool = True,
    ) -> dict[str, Any]:
        normalized_label = self._normalize_label_name(label)
        if self._model_training_task is not None and not self._model_training_task.done():
            raise RuntimeError("模型正在训练中，请等待当前训练结束。")

        label_counts = self.get_labels().get("counts", {})
        trainable_labels = [
            item
            for item in self._list_training_labels()
            if int(label_counts.get(item, 0) or 0) > 0
        ]
        if normalized_label not in trainable_labels:
            raise RuntimeError("该标签当前没有本地可训练样本，无法通过重新训练从模型中移除。")

        remaining_labels = [item for item in trainable_labels if item != normalized_label]
        if len(remaining_labels) < 2:
            raise RuntimeError("移除后剩余可训练标签少于 2 个，无法重新训练分类模型。")

        return await self.start_model_training(
            labels=remaining_labels,
            window_size=window_size,
            step_size=step_size,
            auto_reload=auto_reload,
        )

    # WebSocket 订阅入口：api.py 的 /ws/live 会为每个浏览器页面调用一次。
    # 返回值是一个 asyncio.Queue，相当于给这个浏览器单独开一个“消息收件箱”。
    async def subscribe(self) -> asyncio.Queue[dict[str, Any]]:
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=100)
        self._subscribers.add(queue)
        # 新连接的页面先收到完整初始状态，避免只能等下一帧设备数据才有画面。
        await queue.put({"event": "status", "data": self.get_status()})
        await queue.put({"event": "report_summary", "data": self.get_report_summary()})
        await queue.put({"event": "advanced_evaluation_status", "data": self.get_advanced_evaluation_status()})
        await queue.put({"event": "model_training_status", "data": self.get_model_training_status()})
        return queue

    async def unsubscribe(self, queue: asyncio.Queue[dict[str, Any]]) -> None:
        # 浏览器关闭、刷新或网络断开时移除对应队列，防止后端继续往无效页面推送。
        self._subscribers.discard(queue)

    # 后台依次运行数据预处理和训练脚本，必要时自动重载新模型。
    async def _run_model_training(
        self,
        labels: list[str],
        window_size: int,
        step_size: int,
        auto_reload: bool,
    ) -> None:
        combined_logs: list[str] = []
        try:
            self._set_model_training_status(phase="preparing", output="正在生成训练数据集...\n")
            await self._broadcast("model_training_status", self.get_model_training_status())

            prepare_cmd = [
                *self._training_python_command(),
                str(config.PROJECT_ROOT / "ml_pipeline" / "prepare_dataset.py"),
                "--window-size",
                str(window_size),
                "--step-size",
                str(step_size),
                "--labels",
                *labels,
            ]
            prepare_result = await self._run_process(prepare_cmd)
            combined_logs.append("=== prepare_dataset.py ===")
            combined_logs.append(prepare_result["output"])
            self._set_model_training_status(
                prepareExitCode=prepare_result["exitCode"],
                output="\n".join(part for part in combined_logs if part).strip(),
            )
            if prepare_result["exitCode"] != 0:
                raise RuntimeError("数据预处理失败，请查看训练输出日志。")

            self._set_model_training_status(phase="training", output="\n".join(part for part in combined_logs if part).strip())
            await self._broadcast("model_training_status", self.get_model_training_status())

            train_cmd = [
                *self._training_python_command(),
                str(config.PROJECT_ROOT / "ml_pipeline" / "train_baseline.py"),
            ]
            train_result = await self._run_process(train_cmd)
            combined_logs.append("=== train_baseline.py ===")
            combined_logs.append(train_result["output"])
            self._set_model_training_status(
                trainExitCode=train_result["exitCode"],
                output="\n".join(part for part in combined_logs if part).strip(),
            )
            if train_result["exitCode"] != 0:
                raise RuntimeError("模型训练失败，请查看训练输出日志。")

            if auto_reload:
                self._set_model_training_status(phase="reloading", output="\n".join(part for part in combined_logs if part).strip())
                await self._broadcast("model_training_status", self.get_model_training_status())
                await self.reload_inference_model()
                self._set_model_training_status(modelReloaded=True)

            self._set_model_training_status(
                running=False,
                phase="completed",
                finishedAtIso=self._now_iso(),
                lastSuccessAtIso=self._now_iso(),
                lastError=None,
                output="\n".join(part for part in combined_logs if part).strip(),
            )
        except Exception as exc:
            self._set_model_training_status(
                running=False,
                phase="failed",
                finishedAtIso=self._now_iso(),
                lastError=str(exc),
                output=("\n".join(part for part in combined_logs if part).strip() + f"\n\n错误：{exc}").strip(),
            )
        finally:
            await self._broadcast("model_training_status", self.get_model_training_status())

    # 异步执行训练子进程并收集 stdout/stderr 作为前端日志。
    async def _run_process(self, command: list[str]) -> dict[str, Any]:
        process = await asyncio.create_subprocess_exec(
            *command,
            cwd=str(config.PROJECT_ROOT),
            stdout=PIPE,
            stderr=PIPE,
        )
        stdout, stderr = await process.communicate()
        output = "\n".join(
            part for part in [
                stdout.decode("utf-8", errors="ignore").strip(),
                stderr.decode("utf-8", errors="ignore").strip(),
            ] if part
        )
        return {
            "exitCode": int(process.returncode or 0),
            "output": output,
        }

    def _training_python_command(self) -> list[str]:
        venv_python = config.PROJECT_ROOT / "ml_pipeline" / ".venv" / "Scripts" / "python.exe"
        if venv_python.exists():
            return [str(venv_python)]
        return [sys.executable]

    # 列出可训练标签，过滤体验型标签和空的别名目录。
    def _list_training_labels(self) -> list[str]:
        available = set(config.RECOMMENDED_LABELS)
        if self._data_root.exists():
            available.update(
                path.name
                for path in self._data_root.iterdir()
                if path.is_dir() and not self._is_empty_alias_label_dir(path)
            )
        return sorted(label for label in available if label not in NON_MODEL_LABELS)

    # 规范化标签名并处理中文别名，保证目录名和模型标签一致。
    def _normalize_label_name(self, raw_label: str) -> str:
        normalized = re.sub(r"[\s\-]+", "_", str(raw_label or "").strip().lower())
        normalized = re.sub(r"_+", "_", normalized).strip("_")
        if not normalized:
            raise RuntimeError("标签名不能为空。")
        compact = normalized.replace("_", "")
        alias = LABEL_ALIASES.get(normalized) or LABEL_ALIASES.get(compact)
        if alias:
            return alias
        if not all(ch.isalnum() or ch == "_" or "\u4e00" <= ch <= "\u9fff" for ch in normalized):
            raise RuntimeError("标签名只能包含中文、英文、数字和下划线。")
        return normalized

    def _is_empty_alias_label_dir(self, path: Path) -> bool:
        alias = LABEL_ALIASES.get(path.name) or LABEL_ALIASES.get(path.name.replace("_", ""))
        if not alias:
            return False
        return not any(path.iterdir())

    def _set_model_training_status(self, **updates: Any) -> None:
        self._model_training_status.update(updates)
        self._model_training_status["availableLabels"] = self._list_training_labels()

    def _now_iso(self) -> str:
        return time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime())

    # 按地址、名称、Service UUID 或 ESP32 关键词选择最可能的设备。
    async def _find_device(
        self,
        *,
        address: str | None,
        device_name: str,
        timeout_s: float,
    ) -> dict[str, Any]:
        devices = await self._discover_devices(timeout_s)

        for device in devices:
            if address and device["info"].address.lower() == address.lower():
                return device

        for device in devices:
            names = {
                (device["info"].name or "").strip(),
                (device["info"].local_name or "").strip(),
            }
            if device_name in names:
                return device

        for device in devices:
            if device["info"].is_target_candidate:
                return device

        raise RuntimeError(f"未找到目标设备，设备名={device_name!r}，地址={address!r}")

    # 兼容不同 bleak 版本的扫描返回格式。
    async def _discover_devices(self, timeout_s: float) -> list[dict[str, Any]]:
        try:
            discovered = await BleakScanner.discover(timeout=timeout_s, return_adv=True)
            if isinstance(discovered, dict):
                results = [
                    self._to_target(device, advertisement)
                    for device, advertisement in discovered.values()
                ]
                return self._sort_targets(results)
        except TypeError:
            pass

        devices = await BleakScanner.discover(timeout=timeout_s)
        return self._sort_targets([self._to_target(device, None) for device in devices])

    # 把 bleak 原始设备对象包装成可评分的候选结构。
    def _to_target(self, device: Any, advertisement: Any | None) -> dict[str, Any]:
        name = getattr(device, "name", None)
        local_name = getattr(advertisement, "local_name", None)
        address = getattr(device, "address", "")
        service_uuids = [
            str(uuid).lower()
            for uuid in (getattr(advertisement, "service_uuids", None) or [])
        ]
        rssi = getattr(advertisement, "rssi", None)
        if rssi is None:
            rssi = getattr(device, "rssi", None)

        info = DeviceInfo(
            name=name,
            address=address,
            rssi=rssi,
            local_name=local_name,
            service_uuids=service_uuids,
        )
        self._mark_candidate(info)
        return {
            "device": device,
            "info": info,
            "score": self._candidate_score(info),
        }

    # 给可能是目标 ESP32 的设备打候选标记和原因。
    def _mark_candidate(self, info: DeviceInfo) -> None:
        names = [
            candidate.strip().lower()
            for candidate in (info.name, info.local_name)
            if candidate
        ]
        target_name = config.DEVICE_NAME.lower()
        service_uuid = config.SERVICE_UUID.lower()

        if target_name in names:
            info.is_target_candidate = True
            info.candidate_reason = "设备名完全匹配"
            return

        if service_uuid in info.service_uuids:
            info.is_target_candidate = True
            info.candidate_reason = "广播中包含目标 Service UUID"
            return

        if any("esp32" in name for name in names):
            info.is_target_candidate = True
            info.candidate_reason = "设备名中包含 ESP32"
            return

    def _candidate_score(self, info: DeviceInfo) -> tuple[int, int]:
        base = 0
        reason = info.candidate_reason or ""
        if reason == "设备名完全匹配":
            base = 300
        elif reason == "广播中包含目标 Service UUID":
            base = 250
        elif reason == "设备名中包含 ESP32":
            base = 200
        elif info.name or info.local_name:
            base = 50

        rssi = info.rssi if info.rssi is not None else -999
        return (base, rssi)

    def _sort_targets(self, targets: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return sorted(targets, key=lambda item: item["score"], reverse=True)

    # BLE Notify 回调接口。
    # 这里不直接做复杂推理，先把字节数据转成字符串，再交给 _process_packet 异步处理，避免阻塞蓝牙回调线程。
    def _notification_handler(self, _: Any, data: bytearray) -> None:
        payload = bytes(data).decode("utf-8", errors="ignore").strip()
        if not payload:
            return
        asyncio.create_task(self._process_packet(payload))

    # 单帧传感器数据处理主链路。
    # 输入来自 BLE Notify，输出包括：CSV 记录、InferenceEngine 预测、EvaluationEngine 评估、WebSocket 实时广播。
    async def _process_packet(self, payload: str) -> None:
        received_time_ms = int(time.time() * 1000)
        try:
            packet = SensorPacket.from_payload(payload, received_time_ms)
        except Exception as exc:
            self._status.last_error = str(exc)
            await self._broadcast("error", {"message": str(exc), "rawPacket": payload})
            await self._broadcast("status", self.get_status())
            return

        self._status.latest_packet = packet.to_event_dict()
        self._status.last_packet_time_ms = received_time_ms
        self._status.packets_received += 1
        self._status.last_error = None

        if self._recorder.is_recording:
            self._recorder.write_packet(packet)
            if self._recorder.active_session is not None:
                self._status.active_session = self._recorder.active_session.to_dict()

        prediction = self._inference.consume_packet(packet)
        self._status.inference = self._inference.status_dict()
        self._status.evaluation = self._evaluation.consume(
            packet,
            inference_status=self._status.inference,
        )
        self._status.advanced_evaluation = self._advanced_evaluation.consume(
            packet,
            inference_status=self._status.inference,
            evaluation_status=self._status.evaluation,
        )

        await self._broadcast("packet", packet.to_event_dict())
        await self._broadcast("inference_status", self._status.inference)
        await self._broadcast("evaluation_status", self._status.evaluation)
        await self._broadcast("advanced_evaluation_status", self._status.advanced_evaluation)
        if prediction is not None:
            await self._broadcast("prediction", prediction)

    def _on_ble_disconnect(self, _: BleakClient) -> None:
        asyncio.create_task(self._handle_disconnect())

    # 处理设备意外断开，清理状态并自动结束当前采集。
    async def _handle_disconnect(self) -> None:
        async with self._lock:
            device_address = self._status.device_address
            self._client = None
            self._device = None
            self._status.connected = False
            self._status.device_name = None
            self._status.device_address = None
            self._inference.clear_buffer()
            self._evaluation.clear()
            self._advanced_evaluation.clear()
            self._status.inference = self._inference.status_dict()
            self._status.evaluation = self._evaluation.status_dict()
            self._status.advanced_evaluation = self._advanced_evaluation.status_dict()
            self._status.database = self._database.status()

        self._database.safe_mark_device_offline(address=device_address)
        await self.stop_recording("device_disconnected")
        await self._broadcast("status", self.get_status())
        await self._broadcast("evaluation_status", self._status.evaluation)
        await self._broadcast("advanced_evaluation_status", self._status.advanced_evaluation)

    # 后端内部实时广播接口。
    # BLE 数据包、模型预测、动作评估、训练状态变化都会通过这里发给所有 WebSocket 客户端。
    async def _broadcast(self, event: str, data: Any) -> None:
        dead_queues: list[asyncio.Queue[dict[str, Any]]] = []
        for queue in self._subscribers:
            try:
                # put_nowait 不会阻塞 BLE 数据处理；如果某个页面太慢，队列满了就标记为失效。
                queue.put_nowait({"event": event, "data": data})
            except asyncio.QueueFull:
                dead_queues.append(queue)

        for queue in dead_queues:
            # 清理跟不上实时流的客户端，保护网关主流程稳定运行。
            self._subscribers.discard(queue)



