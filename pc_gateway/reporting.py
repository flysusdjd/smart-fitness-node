from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

from . import config


class ReportService:
    """Aggregate local recording and model files into a midterm report summary."""

    def __init__(
        self,
        *,
        data_root: Path | None = None,
        metrics_path: Path | None = None,
    ) -> None:
        self._data_root = data_root or config.RAW_DATA_ROOT
        self._metrics_path = metrics_path or (config.MODELS_ROOT / "metrics.json")

    def build_summary(self, recent_limit: int = 5) -> dict[str, Any]:
        sessions = self._load_sessions()
        label_counter = Counter(session.get("label") or "unknown" for session in sessions)
        total_rows = sum(int(session.get("rowsWritten") or 0) for session in sessions)
        total_duration_ms = sum(self._session_duration_ms(session) for session in sessions)
        recent_sessions = sessions[:recent_limit]
        model_metrics = self._load_model_metrics()
        trend = self._build_daily_trend(sessions)

        covered_labels = sorted(label_counter.keys())
        coverage_ratio = 0.0
        if config.RECOMMENDED_LABELS:
            coverage_ratio = len([label for label in config.RECOMMENDED_LABELS if label in covered_labels]) / len(config.RECOMMENDED_LABELS)

        return {
            "available": True,
            "stage": self._current_stage(covered_labels, model_metrics),
            "totalSessions": len(sessions),
            "coveredLabels": covered_labels,
            "coveredLabelCount": len(covered_labels),
            "coverageRatio": round(coverage_ratio * 100, 1),
            "totalRows": total_rows,
            "totalDurationMinutes": round(total_duration_ms / 60000.0, 1),
            "labelBreakdown": dict(sorted(label_counter.items())),
            "recentSessions": recent_sessions,
            "dailyTrend": trend,
            "modelMetrics": model_metrics,
        }

    def _load_sessions(self) -> list[dict[str, Any]]:
        if not self._data_root.exists():
            return []

        sessions: list[dict[str, Any]] = []
        for label_dir in sorted(self._data_root.iterdir(), reverse=True):
            if not label_dir.is_dir():
                continue
            for meta_path in sorted(label_dir.glob("*.json"), reverse=True):
                try:
                    payload = json.loads(meta_path.read_text(encoding="utf-8"))
                except json.JSONDecodeError:
                    continue
                sessions.append(payload)

        sessions.sort(key=lambda item: item.get("startedAtMs") or 0, reverse=True)
        return sessions

    def _load_model_metrics(self) -> dict[str, Any]:
        if not self._metrics_path.exists():
            return {
                "available": False,
                "summary": "尚未训练完整模型",
            }

        try:
            payload = json.loads(self._metrics_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {
                "available": False,
                "summary": "模型指标文件解析失败",
            }

        test_accuracy = payload.get("test_accuracy")
        val_accuracy = payload.get("val_accuracy")
        return {
            "available": True,
            "valAccuracy": val_accuracy,
            "testAccuracy": test_accuracy,
            "featureCount": payload.get("feature_count"),
            "summary": self._metrics_summary(val_accuracy, test_accuracy),
        }

    def _session_duration_ms(self, session: dict[str, Any]) -> int:
        started = int(session.get("startedAtMs") or 0)
        stopped = int(session.get("stoppedAtMs") or 0)
        if started > 0 and stopped >= started:
            return stopped - started
        return 0

    def _build_daily_trend(self, sessions: list[dict[str, Any]]) -> list[dict[str, Any]]:
        buckets: dict[str, int] = defaultdict(int)
        for session in sessions:
            started_ms = session.get("startedAtMs")
            if not started_ms:
                continue
            day_key = datetime.fromtimestamp(int(started_ms) / 1000.0).strftime("%m-%d")
            buckets[day_key] += 1

        return [
            {
                "day": day,
                "sessions": count,
            }
            for day, count in sorted(buckets.items())
        ][-7:]

    def _current_stage(self, covered_labels: list[str], model_metrics: dict[str, Any]) -> str:
        if {"idle", "squat_standard"}.issubset(set(covered_labels)) and not {"bench_standard", "bench_wrong", "squat_wrong"}.issubset(set(covered_labels)):
            return "二分类验证阶段"
        if {"idle", "squat_standard", "squat_wrong", "bench_standard", "bench_wrong"}.issubset(set(covered_labels)):
            return "多动作采集阶段"
        if model_metrics.get("available"):
            return "模型联调阶段"
        return "基础采集阶段"

    def _metrics_summary(self, val_accuracy: Any, test_accuracy: Any) -> str:
        if val_accuracy is None and test_accuracy is None:
            return "模型已经生成，但还没有完整指标。"
        if val_accuracy is None:
            return f"当前测试集准确率约为 {float(test_accuracy) * 100:.1f}%"
        if test_accuracy is None:
            return f"当前验证集准确率约为 {float(val_accuracy) * 100:.1f}%"
        return (
            f"当前验证集准确率约为 {float(val_accuracy) * 100:.1f}%，"
            f"测试集准确率约为 {float(test_accuracy) * 100:.1f}%"
        )
