"""本地采集写入器：把 BLE 实时数据落盘为 CSV，并同步保存会话元数据。"""

from __future__ import annotations

import csv
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import TextIO

from .models import RecordingSession, SensorPacket


# 训练 CSV 的固定列顺序，与模型预处理脚本保持一致。
CSV_FIELDNAMES = [
    "recordTimeIso",
    "recordTimeMs",
    "sessionId",
    "label",
    "seq",
    "timestampMs",
    "ax",
    "ay",
    "az",
    "gx",
    "gy",
    "gz",
    "flexRawAdc",
    "flexRawMv",
    "flexIndex",
    "rawPacket",
]


# 把用户输入的标签转成安全文件名，避免非法路径字符。
def sanitize_for_filename(value: str) -> str:
    sanitized = re.sub(r"[^A-Za-z0-9_-]+", "_", value.strip())
    return sanitized.strip("_") or "session"


# 管理当前采集会话的 CSV 文件句柄和元数据写入。
class SessionRecorder:
    def __init__(self, data_root: Path) -> None:
        self._data_root = data_root
        self._data_root.mkdir(parents=True, exist_ok=True)
        self._active_session: RecordingSession | None = None
        self._csv_handle: TextIO | None = None
        self._csv_writer: csv.DictWriter[str] | None = None

    # 暴露当前会话，供服务层同步状态和数据库。
    @property
    def active_session(self) -> RecordingSession | None:
        return self._active_session

    @property
    def is_recording(self) -> bool:
        return self._active_session is not None

    # 创建标签目录、打开 CSV、写表头，并生成会话元数据。
    def start(
        self,
        *,
        label: str,
        subject_id: str | None,
        notes: str | None,
        device_name: str | None,
        device_address: str | None,
    ) -> RecordingSession:
        if self._active_session is not None:
            raise RuntimeError("A recording session is already active.")

        started_ms = int(time.time() * 1000)
        started_iso = datetime.fromtimestamp(
            started_ms / 1000.0,
            tz=timezone.utc,
        ).astimezone().isoformat()

        safe_label = sanitize_for_filename(label)
        session_id = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{safe_label}"

        label_dir = self._data_root / label
        label_dir.mkdir(parents=True, exist_ok=True)

        csv_path = label_dir / f"{session_id}.csv"
        meta_path = label_dir / f"{session_id}.json"

        csv_handle = csv_path.open("w", newline="", encoding="utf-8")
        csv_writer = csv.DictWriter(csv_handle, fieldnames=CSV_FIELDNAMES)
        csv_writer.writeheader()

        session = RecordingSession(
            session_id=session_id,
            label=label,
            subject_id=subject_id,
            notes=notes,
            started_at_iso=started_iso,
            started_at_ms=started_ms,
            csv_path=csv_path,
            meta_path=meta_path,
            device_name=device_name,
            device_address=device_address,
        )

        self._csv_handle = csv_handle
        self._csv_writer = csv_writer
        self._active_session = session
        self._write_metadata()
        return session

    # 把实时传感器数据追加到当前 CSV，并立即刷新到磁盘。
    def write_packet(self, packet: SensorPacket) -> None:
        if self._active_session is None or self._csv_writer is None:
            return

        row = packet.to_csv_row(
            session_id=self._active_session.session_id,
            label=self._active_session.label,
        )
        self._csv_writer.writerow(row)
        if self._csv_handle is not None:
            self._csv_handle.flush()
        self._active_session.rows_written += 1

    # 关闭 CSV 句柄、补齐停止时间和原因，并返回完成的会话对象。
    def stop(self, reason: str) -> RecordingSession | None:
        if self._active_session is None:
            return None

        stopped_ms = int(time.time() * 1000)
        stopped_iso = datetime.fromtimestamp(
            stopped_ms / 1000.0,
            tz=timezone.utc,
        ).astimezone().isoformat()

        self._active_session.stopped_at_ms = stopped_ms
        self._active_session.stopped_at_iso = stopped_iso
        self._active_session.stop_reason = reason

        if self._csv_handle is not None:
            self._csv_handle.close()

        finished = self._active_session
        self._write_metadata()

        self._csv_handle = None
        self._csv_writer = None
        self._active_session = None
        return finished

    # 把会话摘要写成 JSON，便于历史记录和报告汇总读取。
    def _write_metadata(self) -> None:
        if self._active_session is None:
            return
        self._active_session.meta_path.write_text(
            json.dumps(self._active_session.to_dict(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
