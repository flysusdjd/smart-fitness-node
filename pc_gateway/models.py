"""运行时数据模型：定义 BLE 数据包、设备信息、采集会话和网关状态的结构化表示。"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


# 固件发送的 CSV 数据包字段数，解析时用它校验协议是否一致。
EXPECTED_FIELD_COUNT = 11


@dataclass(slots=True)
# 单条 BLE 传感器数据包，负责从固件 CSV 转成结构化字段。
class SensorPacket:
    seq: int
    timestamp_ms: int
    ax: int
    ay: int
    az: int
    gx: int
    gy: int
    gz: int
    flex_raw_adc: int
    flex_raw_mv: int
    flex_index: int
    raw_packet: str
    received_time_ms: int
    received_time_iso: str

    # 解析固件上报的逗号分隔数据，同时记录 PC 端接收时间。
    @classmethod
    def from_payload(cls, payload: str, received_time_ms: int) -> "SensorPacket":
        parts = [part.strip() for part in payload.split(",")]
        if len(parts) != EXPECTED_FIELD_COUNT:
            raise ValueError(
                f"Expected {EXPECTED_FIELD_COUNT} CSV fields, got {len(parts)}: {payload}"
            )

        values = [int(part) for part in parts]
        received_iso = datetime.fromtimestamp(
            received_time_ms / 1000.0,
            tz=timezone.utc,
        ).astimezone().isoformat()

        return cls(
            seq=values[0],
            timestamp_ms=values[1],
            ax=values[2],
            ay=values[3],
            az=values[4],
            gx=values[5],
            gy=values[6],
            gz=values[7],
            flex_raw_adc=values[8],
            flex_raw_mv=values[9],
            flex_index=values[10],
            raw_packet=payload,
            received_time_ms=received_time_ms,
            received_time_iso=received_iso,
        )

    # 转换为前端 WebSocket 使用的驼峰命名字段。
    def to_event_dict(self) -> dict[str, Any]:
        return {
            "seq": self.seq,
            "timestampMs": self.timestamp_ms,
            "ax": self.ax,
            "ay": self.ay,
            "az": self.az,
            "gx": self.gx,
            "gy": self.gy,
            "gz": self.gz,
            "flexRawAdc": self.flex_raw_adc,
            "flexRawMv": self.flex_raw_mv,
            "flexIndex": self.flex_index,
            "rawPacket": self.raw_packet,
            "receivedTimeMs": self.received_time_ms,
            "receivedTimeIso": self.received_time_iso,
        }

    # 转换为本地训练 CSV 行，补充会话和标签信息。
    def to_csv_row(self, session_id: str, label: str) -> dict[str, Any]:
        return {
            "recordTimeIso": self.received_time_iso,
            "recordTimeMs": self.received_time_ms,
            "sessionId": session_id,
            "label": label,
            "seq": self.seq,
            "timestampMs": self.timestamp_ms,
            "ax": self.ax,
            "ay": self.ay,
            "az": self.az,
            "gx": self.gx,
            "gy": self.gy,
            "gz": self.gz,
            "flexRawAdc": self.flex_raw_adc,
            "flexRawMv": self.flex_raw_mv,
            "flexIndex": self.flex_index,
            "rawPacket": self.raw_packet,
        }


@dataclass(slots=True)
# 扫描到的 BLE 设备信息，包含候选匹配原因。
class DeviceInfo:
    name: str | None
    address: str
    rssi: int | None = None
    local_name: str | None = None
    service_uuids: list[str] = field(default_factory=list)
    is_target_candidate: bool = False
    candidate_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["displayName"] = self.local_name or self.name or "Unknown"
        return payload


@dataclass(slots=True)
# 本地一次采集的文件路径、标签、设备和写入计数。
class RecordingSession:
    session_id: str
    label: str
    subject_id: str | None
    notes: str | None
    started_at_iso: str
    started_at_ms: int
    csv_path: Path
    meta_path: Path
    device_name: str | None = None
    device_address: str | None = None
    rows_written: int = 0
    stopped_at_iso: str | None = None
    stopped_at_ms: int | None = None
    stop_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "sessionId": self.session_id,
            "label": self.label,
            "subjectId": self.subject_id,
            "notes": self.notes,
            "startedAtIso": self.started_at_iso,
            "startedAtMs": self.started_at_ms,
            "stoppedAtIso": self.stopped_at_iso,
            "stoppedAtMs": self.stopped_at_ms,
            "stopReason": self.stop_reason,
            "csvPath": str(self.csv_path),
            "metaPath": str(self.meta_path),
            "deviceName": self.device_name,
            "deviceAddress": self.device_address,
            "rowsWritten": self.rows_written,
        }


@dataclass(slots=True)
# 网关整体状态快照，前端轮询和 WebSocket 都使用这个结构。
class GatewayStatus:
    connected: bool = False
    recording: bool = False
    device_name: str | None = None
    device_address: str | None = None
    last_packet_time_ms: int | None = None
    packets_received: int = 0
    last_error: str | None = None
    active_session: dict[str, Any] | None = None
    latest_packet: dict[str, Any] | None = None
    inference: dict[str, Any] | None = None
    evaluation: dict[str, Any] | None = None
    advanced_evaluation: dict[str, Any] | None = None
    report_summary: dict[str, Any] | None = None
    database: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "connected": self.connected,
            "recording": self.recording,
            "deviceName": self.device_name,
            "deviceAddress": self.device_address,
            "lastPacketTimeMs": self.last_packet_time_ms,
            "packetsReceived": self.packets_received,
            "lastError": self.last_error,
            "activeSession": self.active_session,
            "latestPacket": self.latest_packet,
            "inference": self.inference,
            "evaluation": self.evaluation,
            "advancedEvaluation": self.advanced_evaluation,
            "reportSummary": self.report_summary,
            "database": self.database,
        }
