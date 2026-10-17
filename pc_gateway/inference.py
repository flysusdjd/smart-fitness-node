"""实时动作识别引擎：维护传感器滑动窗口，提取统计特征，并调用已训练模型预测动作标签。"""

from __future__ import annotations

import json
import time
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd

from . import config
from .models import SensorPacket


# 实时推理和离线训练共用的原始传感器字段。
FEATURE_COLUMNS = ["ax", "ay", "az", "gx", "gy", "gz", "flexIndex"]
FEATURE_STATS = ("mean", "std", "min", "max", "ptp", "rms")


# 生成毫秒时间戳和本地 ISO 时间，便于前端显示。
def _now_dict() -> dict[str, Any]:
    now_ms = int(time.time() * 1000)
    now_iso = datetime.fromtimestamp(
        now_ms / 1000.0,
        tz=timezone.utc,
    ).astimezone().isoformat()
    return {
        "ms": now_ms,
        "iso": now_iso,
    }


# 维护滑动窗口并调用已训练模型生成动作识别结果。
class InferenceEngine:
    def __init__(
        self,
        *,
        model_path: Path | None = None,
        label_map_path: Path | None = None,
        default_window_size: int = config.DEFAULT_INFERENCE_WINDOW_SIZE,
    ) -> None:
        self._model_path = model_path or config.MODEL_PATH
        self._label_map_path = label_map_path or config.LABEL_MAP_PATH
        self._default_window_size = default_window_size
        self._window_size = default_window_size
        self._buffer: deque[SensorPacket] = deque(maxlen=self._window_size)
        self._model: Any | None = None
        self._feature_columns: list[str] = self._default_feature_columns()
        self._label_id_to_name: dict[int, str] = {}
        self._dataset_meta: dict[str, Any] = {}
        self._latest_prediction: dict[str, Any] | None = None
        self._last_error: str | None = None
        self._loaded_at_ms: int | None = None
        self._loaded_at_iso: str | None = None
        self.load_model(silent=True)

    # 当前窗口长度来自模型元数据，保证实时推理和训练一致。
    @property
    def window_size(self) -> int:
        return self._window_size

    # 连接切换或模型重载时清空旧数据，避免跨会话污染预测。
    def clear_buffer(self) -> None:
        self._buffer = deque(maxlen=self._window_size)
        self._latest_prediction = None

    # 加载 joblib 模型、标签映射和数据集元信息。
    def load_model(self, *, silent: bool = False) -> dict[str, Any]:
        self._model = None
        self._feature_columns = self._default_feature_columns()
        self._label_id_to_name = {}
        self._dataset_meta = {}
        self._loaded_at_ms = None
        self._loaded_at_iso = None
        self._last_error = None

        if not self._model_path.exists():
            self._last_error = f"未找到模型文件：{self._model_path}"
            if silent:
                self._last_error = None
            self.clear_buffer()
            return self.status_dict()

        try:
            payload = joblib.load(self._model_path)
            if not isinstance(payload, dict):
                raise ValueError("模型文件格式不正确，缺少字典结构。")

            model = payload.get("model")
            if model is None:
                raise ValueError("模型文件中缺少 model 字段。")

            feature_columns = payload.get("feature_columns") or self._default_feature_columns()
            dataset_meta = payload.get("dataset_meta") or {}
            label_map = payload.get("label_map")
            if label_map is None:
                label_map = self._load_label_map_from_file()

            self._model = model
            self._feature_columns = [str(column) for column in feature_columns]
            self._label_id_to_name = self._normalize_label_map(label_map)
            self._dataset_meta = dataset_meta
            self._apply_window_size_from_meta(dataset_meta)

            now = _now_dict()
            self._loaded_at_ms = now["ms"]
            self._loaded_at_iso = now["iso"]
            self.clear_buffer()
        except Exception as exc:
            self._last_error = str(exc)
            self._model = None
            self.clear_buffer()

        return self.status_dict()

    # 接收一帧传感器数据，窗口满后提取特征并输出预测。
    def consume_packet(self, packet: SensorPacket) -> dict[str, Any] | None:
        self._buffer.append(packet)
        if self._model is None or len(self._buffer) < self._window_size:
            return None

        try:
            feature_row = self._build_feature_row(list(self._buffer))
            input_df = pd.DataFrame([
                {column: feature_row.get(column, 0.0) for column in self._feature_columns}
            ])

            predicted_label_id = int(self._model.predict(input_df)[0])
            top_labels = self._predict_top_labels(input_df, predicted_label_id)
            confidence = float(top_labels[0]["probability"]) if top_labels else 1.0

            now = _now_dict()
            self._latest_prediction = {
                "labelId": predicted_label_id,
                "label": self._label_id_to_name.get(predicted_label_id, str(predicted_label_id)),
                "confidence": confidence,
                "topLabels": top_labels,
                "windowSize": self._window_size,
                "bufferedPoints": len(self._buffer),
                "updatedAtMs": now["ms"],
                "updatedAtIso": now["iso"],
            }
            self._last_error = None
            return self._latest_prediction
        except Exception as exc:
            self._last_error = str(exc)
            return None

    def status_dict(self) -> dict[str, Any]:
        return {
            "modelLoaded": self._model is not None,
            "modelPath": str(self._model_path),
            "labelMapPath": str(self._label_map_path),
            "featureCount": len(self._feature_columns),
            "windowSize": self._window_size,
            "bufferedPoints": len(self._buffer),
            "ready": self._model is not None and len(self._buffer) >= self._window_size,
            "loadedAtMs": self._loaded_at_ms,
            "loadedAtIso": self._loaded_at_iso,
            "lastError": self._last_error,
            "latestPrediction": self._latest_prediction,
            "datasetMeta": self._dataset_meta,
        }

    def _default_feature_columns(self) -> list[str]:
        return [
            f"{feature_name}_{stat_name}"
            for feature_name in FEATURE_COLUMNS
            for stat_name in FEATURE_STATS
        ]

    def _load_label_map_from_file(self) -> dict[str, Any]:
        if not self._label_map_path.exists():
            raise FileNotFoundError(f"未找到标签映射文件：{self._label_map_path}")
        return json.loads(self._label_map_path.read_text(encoding="utf-8"))

    def _normalize_label_map(self, label_map: dict[str, Any]) -> dict[int, str]:
        normalized: dict[int, str] = {}
        for key, value in label_map.items():
            if isinstance(value, int):
                normalized[int(value)] = str(key)
            else:
                normalized[int(key)] = str(value)
        return normalized

    def _apply_window_size_from_meta(self, dataset_meta: dict[str, Any]) -> None:
        window_size = int(dataset_meta.get("window_size") or self._default_window_size)
        self._window_size = max(1, window_size)
        self._buffer = deque(maxlen=self._window_size)

    # 把窗口内每个信号转成均值、标准差、峰峰值、RMS 等统计量。
    def _build_feature_row(self, packets: list[SensorPacket]) -> dict[str, float]:
        frame = pd.DataFrame(
            [
                {
                    "ax": packet.ax,
                    "ay": packet.ay,
                    "az": packet.az,
                    "gx": packet.gx,
                    "gy": packet.gy,
                    "gz": packet.gz,
                    "flexIndex": packet.flex_index,
                }
                for packet in packets
            ]
        )

        feature_row: dict[str, float] = {}
        for feature_name in FEATURE_COLUMNS:
            signal = frame[feature_name].to_numpy(dtype=float)
            feature_row[f"{feature_name}_mean"] = float(np.mean(signal))
            feature_row[f"{feature_name}_std"] = float(np.std(signal))
            feature_row[f"{feature_name}_min"] = float(np.min(signal))
            feature_row[f"{feature_name}_max"] = float(np.max(signal))
            feature_row[f"{feature_name}_ptp"] = float(np.ptp(signal))
            feature_row[f"{feature_name}_rms"] = float(np.sqrt(np.mean(np.square(signal))))
        return feature_row

    # 如果模型支持概率输出，则返回置信度最高的若干标签。
    def _predict_top_labels(self, input_df: pd.DataFrame, predicted_label_id: int) -> list[dict[str, Any]]:
        if hasattr(self._model, "predict_proba"):
            probabilities = self._model.predict_proba(input_df)[0]
            classes = list(getattr(self._model, "classes_", []))
            ranked = sorted(
                zip(classes, probabilities),
                key=lambda item: float(item[1]),
                reverse=True,
            )
            return [
                {
                    "labelId": int(label_id),
                    "label": self._label_id_to_name.get(int(label_id), str(label_id)),
                    "probability": float(probability),
                }
                for label_id, probability in ranked[:3]
            ]

        return [
            {
                "labelId": predicted_label_id,
                "label": self._label_id_to_name.get(predicted_label_id, str(predicted_label_id)),
                "probability": 1.0,
            }
        ]
