from __future__ import annotations

import json
import math
import time
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import config
from .models import SensorPacket


def _now_dict() -> dict[str, Any]:
    now_ms = int(time.time() * 1000)
    now_iso = datetime.fromtimestamp(now_ms / 1000.0, tz=timezone.utc).astimezone().isoformat()
    return {"ms": now_ms, "iso": now_iso}


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


class AdvancedEvaluationService:
    """Service-side evaluation scaffold for future complex assessment models.

    当前版本优先提供一个“可替换”的复杂评估框架：
    - 如果存在 advanced_evaluation_profile.json，则按配置阈值运行
    - 如果不存在，则使用默认阈值
    - 输出结构尽量稳定，后续可直接替换成真实服务端模型
    """

    def __init__(self, profile_path: Path | None = None, window_size: int = 20) -> None:
        self._profile_path = profile_path or config.ADVANCED_EVAL_PROFILE_PATH
        self._window_size = max(8, window_size)
        self._buffer: deque[SensorPacket] = deque(maxlen=self._window_size)
        self._profile = self._load_profile()
        self._latest = self._empty_status()

    def clear(self) -> None:
        self._buffer = deque(maxlen=self._window_size)
        self._latest = self._empty_status()

    def status_dict(self) -> dict[str, Any]:
        return self._latest

    def consume(
        self,
        packet: SensorPacket,
        *,
        inference_status: dict[str, Any] | None,
        evaluation_status: dict[str, Any] | None,
    ) -> dict[str, Any]:
        self._buffer.append(packet)
        action_label = str(((inference_status or {}).get("latestPrediction") or {}).get("label") or "idle")
        action_family = self._action_family(action_label)

        flex_values = [item.flex_index for item in self._buffer]
        acc_values = [self._acc_mag(item) for item in self._buffer]
        gyro_values = [self._gyro_mag(item) for item in self._buffer]

        base_score = int((evaluation_status or {}).get("standardScore") or 0)
        depth_score = int((evaluation_status or {}).get("depthScore") or 0)
        stability_score = int((evaluation_status or {}).get("stabilityScore") or 0)
        rhythm_score = int((evaluation_status or {}).get("rhythmScore") or 0)

        compensation_flags = self._compensation_flags(
            action_label=action_label,
            action_family=action_family,
            flex_values=flex_values,
            gyro_values=gyro_values,
            depth_score=depth_score,
            stability_score=stability_score,
            rhythm_score=rhythm_score,
        )
        posture_summary = self._posture_summary(action_label, action_family, base_score, compensation_flags)
        correction_focus = compensation_flags[0]["label"] if compensation_flags else "当前动作整体稳定"
        model_readiness = "profile_loaded" if self._profile["loaded"] else "default_rule_profile"
        band = self._score_band(base_score)

        now = _now_dict()
        self._latest = {
            "available": True,
            "source": "service_side_advanced_scaffold",
            "modelReady": True,
            "modelReadiness": model_readiness,
            "profilePath": str(self._profile_path),
            "profileLoaded": self._profile["loaded"],
            "profileVersion": self._profile["version"],
            "actionLabel": action_label,
            "actionFamily": action_family,
            "standardBand": band,
            "standardScore": base_score,
            "compensationFlags": compensation_flags,
            "postureSummary": posture_summary,
            "correctionFocus": correction_focus,
            "scoreBreakdown": {
                "depth": depth_score,
                "stability": stability_score,
                "rhythm": rhythm_score,
            },
            "windowSize": self._window_size,
            "bufferedPoints": len(self._buffer),
            "updatedAtMs": now["ms"],
            "updatedAtIso": now["iso"],
        }
        return self._latest

    def _load_profile(self) -> dict[str, Any]:
        if self._profile_path.exists():
            try:
                payload = json.loads(self._profile_path.read_text(encoding="utf-8"))
                return {
                    "loaded": True,
                    "version": str(payload.get("version") or "profile-v1"),
                    "thresholds": payload.get("thresholds") or {},
                }
            except Exception:
                pass

        return {
            "loaded": False,
            "version": "default-v1",
            "thresholds": {
                "squat_depth_good": 70,
                "stability_good": 75,
                "rhythm_good": 72,
                "gyro_peak_alert": 3500,
                "flex_peak_low": 18,
            },
        }

    def _empty_status(self) -> dict[str, Any]:
        return {
            "available": False,
            "source": "service_side_advanced_scaffold",
            "modelReady": False,
            "modelReadiness": "waiting_for_data",
            "profilePath": str(self._profile_path),
            "profileLoaded": self._profile["loaded"],
            "profileVersion": self._profile["version"],
            "actionLabel": "idle",
            "actionFamily": "idle",
            "standardBand": "unknown",
            "standardScore": 0,
            "compensationFlags": [],
            "postureSummary": "等待实时数据",
            "correctionFocus": "等待实时数据",
            "scoreBreakdown": {
                "depth": 0,
                "stability": 0,
                "rhythm": 0,
            },
            "windowSize": self._window_size,
            "bufferedPoints": 0,
            "updatedAtMs": None,
            "updatedAtIso": None,
        }

    def _action_family(self, label: str) -> str:
        if label.startswith("squat"):
            return "squat"
        if label.startswith("bench"):
            return "bench"
        if label == "idle":
            return "idle"
        return "general"

    def _score_band(self, score: int) -> str:
        if score >= 85:
            return "excellent"
        if score >= 70:
            return "good"
        if score >= 55:
            return "watch"
        return "risk"

    def _compensation_flags(
        self,
        *,
        action_label: str,
        action_family: str,
        flex_values: list[int],
        gyro_values: list[float],
        depth_score: int,
        stability_score: int,
        rhythm_score: int,
    ) -> list[dict[str, Any]]:
        thresholds = self._profile["thresholds"]
        flags: list[dict[str, Any]] = []
        max_flex = max(flex_values, default=0)
        max_gyro = max(gyro_values, default=0.0)

        if action_label == "squat_wrong":
            flags.append({
                "code": "knee_valgus_pattern",
                "label": "膝盖轨迹疑似内扣",
                "level": "high",
                "detail": "模型识别到深蹲错误样本，优先检查膝盖是否偏离脚尖方向。",
            })

        if action_family == "squat" and depth_score < int(thresholds.get("squat_depth_good", 70)):
            flags.append({
                "code": "depth_insufficient",
                "label": "深蹲深度不足",
                "level": "medium",
                "detail": "下蹲深度未达到预设目标区间。",
            })

        if stability_score < int(thresholds.get("stability_good", 75)):
            flags.append({
                "code": "stability_loss",
                "label": "动作稳定性偏弱",
                "level": "medium" if stability_score >= 55 else "high",
                "detail": "加速度与角速度波动偏大，可能存在晃动或控制不足。",
            })

        if rhythm_score < int(thresholds.get("rhythm_good", 72)):
            flags.append({
                "code": "rhythm_unsteady",
                "label": "动作节奏不均匀",
                "level": "medium",
                "detail": "动作下放或起身过程的节奏不够平滑。",
            })

        if max_gyro > float(thresholds.get("gyro_peak_alert", 3500)):
            flags.append({
                "code": "excessive_angular_velocity",
                "label": "角速度峰值过高",
                "level": "high",
                "detail": "可能出现突发摆动、惯性代偿或发力过急。",
            })

        if action_family != "idle" and max_flex < int(thresholds.get("flex_peak_low", 18)):
            flags.append({
                "code": "range_of_motion_small",
                "label": "有效活动幅度偏小",
                "level": "medium",
                "detail": "弯曲峰值偏低，动作幅度可能不足。",
            })

        return flags[:4]

    def _posture_summary(
        self,
        action_label: str,
        action_family: str,
        standard_score: int,
        flags: list[dict[str, Any]],
    ) -> str:
        if action_family == "idle":
            return "当前处于静止状态，姿态整体平稳。"

        if action_label == "squat_wrong":
            return "当前深蹲存在错误模式，建议优先纠正膝盖内扣和下肢轨迹稳定性。"

        if not flags and standard_score >= 80:
            if action_family == "squat":
                return "深蹲动作整体完成度较好，深度、稳定性与节奏控制较均衡。"
            if action_family == "bench":
                return "卧推动作整体完成度较好，控制较稳定。"
            return "当前动作整体质量较好。"

        if not flags:
            return "当前动作存在轻微优化空间，但整体仍保持可控。"

        primary = flags[0]["label"]
        return f"当前动作需要优先关注：{primary}。"

    def _acc_mag(self, packet: SensorPacket) -> float:
        return math.sqrt(packet.ax ** 2 + packet.ay ** 2 + packet.az ** 2)

    def _gyro_mag(self, packet: SensorPacket) -> float:
        return math.sqrt(packet.gx ** 2 + packet.gy ** 2 + packet.gz ** 2)
