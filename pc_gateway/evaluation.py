from __future__ import annotations

import math
import time
from collections import deque
from datetime import datetime, timezone
from typing import Any

from .models import SensorPacket


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


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


class EvaluationEngine:
    """Rule-based midterm scaffold for live action quality evaluation.

    This module intentionally uses heuristics so the UI and API can be
    demonstrated before the final server-side evaluation model is ready.
    """

    def __init__(self, window_size: int = 20, voice_cooldown_ms: int = 2500) -> None:
        self._window_size = max(5, window_size)
        self._buffer: deque[SensorPacket] = deque(maxlen=self._window_size)
        self._latest: dict[str, Any] = self._empty_status()
        self._voice_cooldown_ms = voice_cooldown_ms
        self._last_voice_text: str | None = None
        self._last_voice_ms = 0

    def clear(self) -> None:
        self._buffer = deque(maxlen=self._window_size)
        self._latest = self._empty_status()
        self._last_voice_text = None
        self._last_voice_ms = 0

    def consume(
        self,
        packet: SensorPacket,
        *,
        inference_status: dict[str, Any] | None,
    ) -> dict[str, Any]:
        self._buffer.append(packet)

        prediction = (inference_status or {}).get("latestPrediction") or {}
        action_label = str(prediction.get("label") or "idle")
        action_display = self._humanize_label(action_label)
        action_family = self._action_family(action_label)

        flex_values = [item.flex_index for item in self._buffer]
        acc_magnitudes = [self._acc_magnitude(item) for item in self._buffer]
        gyro_magnitudes = [self._gyro_magnitude(item) for item in self._buffer]

        phase = self._detect_phase(action_family, flex_values, gyro_magnitudes)
        depth_score = self._depth_score(action_family, flex_values[-1] if flex_values else 0, max(flex_values, default=0))
        stability_score = self._stability_score(acc_magnitudes, gyro_magnitudes, flex_values)
        rhythm_score = self._rhythm_score(flex_values, gyro_magnitudes)
        standard_score = round(
            _clamp(depth_score * 0.4 + stability_score * 0.35 + rhythm_score * 0.25, 0, 100)
        )
        if action_label == "squat_wrong":
            standard_score = min(standard_score, 62)
        elif action_label == "bench_wrong":
            standard_score = min(standard_score, 65)

        compensation_risk = self._compensation_risk(action_label, standard_score, stability_score, rhythm_score)
        suggestions = self._build_suggestions(
            action_label=action_label,
            action_family=action_family,
            standard_score=standard_score,
            depth_score=depth_score,
            stability_score=stability_score,
            rhythm_score=rhythm_score,
            phase=phase,
        )
        voice_feedback = self._build_voice_feedback(suggestions)

        now = _now_dict()
        self._latest = {
            "available": True,
            "source": "heuristic_midterm_scaffold",
            "modelMode": "rules_plus_inference",
            "actionLabel": action_label,
            "actionDisplay": action_display,
            "phase": phase,
            "standardScore": standard_score,
            "depthScore": depth_score,
            "stabilityScore": stability_score,
            "rhythmScore": rhythm_score,
            "compensationRisk": compensation_risk,
            "suggestions": suggestions,
            "voiceFeedback": voice_feedback,
            "bufferedPoints": len(self._buffer),
            "windowSize": self._window_size,
            "updatedAtMs": now["ms"],
            "updatedAtIso": now["iso"],
        }
        return self._latest

    def status_dict(self) -> dict[str, Any]:
        return self._latest

    def _empty_status(self) -> dict[str, Any]:
        return {
            "available": False,
            "source": "heuristic_midterm_scaffold",
            "modelMode": "rules_plus_inference",
            "actionLabel": "idle",
            "actionDisplay": "静止",
            "phase": "等待数据",
            "standardScore": 0,
            "depthScore": 0,
            "stabilityScore": 0,
            "rhythmScore": 0,
            "compensationRisk": "unknown",
            "suggestions": ["等待实时数据，用于生成动作评分和纠正建议。"],
            "voiceFeedback": {
                "enabled": True,
                "mode": "preview",
                "ttsReady": False,
                "text": "等待实时数据",
                "shouldSpeak": False,
                "lastTriggeredAtMs": None,
            },
            "bufferedPoints": 0,
            "windowSize": self._window_size,
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

    def _humanize_label(self, label: str) -> str:
        mapping = {
            "idle": "静止",
            "squat_standard": "深蹲-标准",
            "squat_wrong": "深蹲-错误",
            "bench_standard": "卧推-标准",
            "bench_wrong": "卧推-错误",
        }
        return mapping.get(label, label)

    def _detect_phase(
        self,
        action_family: str,
        flex_values: list[int],
        gyro_magnitudes: list[float],
    ) -> str:
        if len(flex_values) < 3:
            return "等待数据"

        latest = flex_values[-1]
        previous = flex_values[-3]
        delta = latest - previous
        gyro_latest = gyro_magnitudes[-1] if gyro_magnitudes else 0.0

        if action_family == "idle" and latest <= 5 and gyro_latest < 500:
            return "静止"

        if action_family == "squat":
            if delta >= 4:
                return "下蹲阶段"
            if delta <= -4:
                return "起身阶段"
            if latest >= 24:
                return "蹲底控制"
            return "动作过渡"

        if action_family == "bench":
            if delta >= 4:
                return "下放阶段"
            if delta <= -4:
                return "推起阶段"
            return "动作过渡"

        if abs(delta) <= 2:
            return "动作过渡"
        return "发力中"

    def _depth_score(self, action_family: str, latest_flex: int, peak_flex: int) -> int:
        if action_family == "idle":
            return 100

        target_peak = 30 if action_family == "squat" else 25
        raw_score = (max(latest_flex, peak_flex) / max(1, target_peak)) * 100
        return round(_clamp(raw_score, 0, 100))

    def _stability_score(
        self,
        acc_magnitudes: list[float],
        gyro_magnitudes: list[float],
        flex_values: list[int],
    ) -> int:
        if len(acc_magnitudes) < 4:
            return 0

        acc_delta = self._std_diff(acc_magnitudes)
        gyro_delta = self._std_diff(gyro_magnitudes)
        flex_delta = self._std_diff([float(value) for value in flex_values])
        penalty = min(55.0, acc_delta / 120.0) + min(30.0, gyro_delta / 70.0) + min(15.0, flex_delta * 1.4)
        return round(_clamp(100.0 - penalty, 0.0, 100.0))

    def _rhythm_score(self, flex_values: list[int], gyro_magnitudes: list[float]) -> int:
        if len(flex_values) < 4:
            return 0

        amplitude = max(flex_values) - min(flex_values)
        flex_delta = self._std_diff([float(value) for value in flex_values])
        gyro_delta = self._std_diff(gyro_magnitudes)
        reward = min(45.0, amplitude * 1.5)
        penalty = min(35.0, flex_delta * 1.8) + min(20.0, gyro_delta / 140.0)
        return round(_clamp(55.0 + reward - penalty, 0.0, 100.0))

    def _compensation_risk(
        self,
        action_label: str,
        standard_score: int,
        stability_score: int,
        rhythm_score: int,
    ) -> str:
        if action_label.endswith("_wrong"):
            return "high" if stability_score < 72 or standard_score < 58 else "medium"
        if standard_score < 55 or stability_score < 50:
            return "high"
        if standard_score < 75 or rhythm_score < 65:
            return "medium"
        return "low"

    def _build_suggestions(
        self,
        *,
        action_label: str,
        action_family: str,
        standard_score: int,
        depth_score: int,
        stability_score: int,
        rhythm_score: int,
        phase: str,
    ) -> list[str]:
        suggestions: list[str] = []

        if action_family == "idle":
            return ["保持自然站立和稳定佩戴，准备开始下一组动作采集。"]

        if action_family == "squat":
            if action_label == "squat_wrong":
                suggestions.append("检测到深蹲错误模式，优先检查膝盖是否向内扣，保持膝盖朝向脚尖。")
                if stability_score < 78:
                    suggestions.append("下蹲和起身时让髋、膝、脚尖保持同一方向，避免膝盖左右摆动。")
                if depth_score < 70:
                    suggestions.append("当前下蹲幅度偏小，先保证动作幅度稳定，再纠正膝盖轨迹。")
                if rhythm_score < 72:
                    suggestions.append("动作节奏偏急，建议放慢下蹲和起身速度。")
                return suggestions[:3]

            if depth_score < 70:
                suggestions.append("下蹲深度还不够，可以继续向后坐臀并稳定下蹲。")
            if stability_score < 72:
                suggestions.append("动作稳定性一般，注意收紧核心并保持膝盖朝向脚尖。")
            if rhythm_score < 72:
                suggestions.append("节奏有些急，建议下降和起身都尽量保持匀速。")
            if phase == "蹲底控制":
                suggestions.append("已经接近蹲底，起身时注意保持髋膝同步发力。")

        elif action_family == "bench":
            if depth_score < 70:
                suggestions.append("卧推动作幅度偏小，下放可以更充分一些。")
            if stability_score < 72:
                suggestions.append("上肢控制略有抖动，注意肩胛收紧和握距稳定。")
            if rhythm_score < 72:
                suggestions.append("发力节奏不够均匀，建议下放和推起都保持可控。")

        else:
            if standard_score < 70:
                suggestions.append("当前动作质量还有优化空间，建议先控制速度再提升幅度。")

        if not suggestions:
            suggestions.append("当前动作整体较稳定，可以继续保持当前节奏和姿态。")

        return suggestions[:3]

    def _build_voice_feedback(self, suggestions: list[str]) -> dict[str, Any]:
        cue = suggestions[0] if suggestions else "保持当前状态。"
        now_ms = int(time.time() * 1000)
        should_speak = False
        if cue != self._last_voice_text or (now_ms - self._last_voice_ms) >= self._voice_cooldown_ms:
            should_speak = True
            self._last_voice_text = cue
            self._last_voice_ms = now_ms

        return {
            "enabled": True,
            "mode": "preview",
            "ttsReady": False,
            "text": cue,
            "shouldSpeak": should_speak,
            "lastTriggeredAtMs": now_ms if should_speak else self._last_voice_ms or None,
        }

    def _acc_magnitude(self, packet: SensorPacket) -> float:
        return math.sqrt(packet.ax ** 2 + packet.ay ** 2 + packet.az ** 2)

    def _gyro_magnitude(self, packet: SensorPacket) -> float:
        return math.sqrt(packet.gx ** 2 + packet.gy ** 2 + packet.gz ** 2)

    def _std_diff(self, values: list[float]) -> float:
        if len(values) < 2:
            return 0.0
        deltas = [values[index] - values[index - 1] for index in range(1, len(values))]
        mean = sum(deltas) / len(deltas)
        variance = sum((delta - mean) ** 2 for delta in deltas) / len(deltas)
        return math.sqrt(variance)
