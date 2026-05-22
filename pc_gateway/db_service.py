from __future__ import annotations

import json
from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy import desc, func, or_, select, update

from . import config
from .db import db_manager
from .db_models import Device, EvaluationResult, ModelVersion, SensorSession, TrainingReport, User, UserToken
from .models import DeviceInfo, RecordingSession
from .security import hash_password, token_expiry, verify_password


class DatabaseService:
    def __init__(self) -> None:
        self._manager = db_manager

    def _build_local_email(self, username: str) -> str:
        return f"{username}@local.smart-fitness"

    def status(self) -> dict[str, Any]:
        return self._manager.health()

    def init_schema(self) -> dict[str, Any]:
        self._manager.create_all()
        return self.status()

    def register_user(
        self,
        *,
        username: str,
        password: str,
    ) -> dict[str, Any]:
        email = self._build_local_email(username)
        with self._manager.session_scope() as session:
            existing = session.execute(
                select(User).where(or_(User.username == username, User.email == email))
            ).scalars().first()
            if existing is not None:
                raise ValueError("Username already exists.")

            user = User(
                username=username,
                email=email,
                password_hash=hash_password(password),
                full_name=None,
                student_no=None,
                role="student",
            )
            session.add(user)
            session.flush()
            return self._user_to_dict(user)

    def login(self, *, username: str, password: str) -> dict[str, Any]:
        with self._manager.session_scope() as session:
            user = session.execute(select(User).where(User.username == username)).scalars().first()
            if user is None or not verify_password(password, user.password_hash):
                raise ValueError("Invalid username or password.")

            token_row = UserToken(
                user_id=user.id,
                token=self._generate_token(),
                expires_at=token_expiry(),
            )
            session.add(token_row)
            session.flush()
            return {
                "accessToken": token_row.token,
                "tokenType": "bearer",
                "expiresAt": token_row.expires_at.isoformat(),
                "user": self._user_to_dict(user),
            }

    def current_user(self, token_value: str) -> dict[str, Any]:
        with self._manager.session_scope() as session:
            token_row = session.execute(
                select(UserToken).where(
                    UserToken.token == token_value,
                    UserToken.expires_at >= datetime.now(timezone.utc),
                )
            ).scalars().first()
            if token_row is None:
                raise ValueError("Invalid or expired access token.")

            token_row.last_used_at = datetime.now(timezone.utc)
            session.add(token_row)
            return self._user_to_dict(token_row.user)

    def list_users(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._manager.session_scope() as session:
            rows = session.execute(select(User).order_by(desc(User.created_at)).limit(limit)).scalars().all()
            return [self._user_to_dict(row) for row in rows]

    def upsert_device(self, device_info: DeviceInfo, *, status: str = "online") -> dict[str, Any]:
        with self._manager.session_scope() as session:
            row = session.execute(select(Device).where(Device.ble_address == device_info.address)).scalars().first()
            if row is None:
                row = Device(
                    device_name=device_info.local_name or device_info.name,
                    ble_address=device_info.address,
                    status=status,
                )
                session.add(row)
            else:
                row.device_name = device_info.local_name or device_info.name
                row.status = status
            row.last_seen_at = datetime.now(timezone.utc)
            session.flush()
            return self._device_to_dict(row)

    def mark_device_offline(self, *, address: str | None) -> None:
        if not address:
            return
        with self._manager.session_scope() as session:
            row = session.execute(select(Device).where(Device.ble_address == address)).scalars().first()
            if row is None:
                return
            row.status = "offline"
            row.last_seen_at = datetime.now(timezone.utc)
            session.add(row)

    def create_sensor_session(
        self,
        *,
        local_session: RecordingSession,
        device_address: str | None,
    ) -> dict[str, Any]:
        with self._manager.session_scope() as session:
            device = self._find_device(session, device_address)
            user = self._find_user(session, local_session.subject_id)
            row = SensorSession(
                session_id=local_session.session_id,
                label=local_session.label,
                subject_id=local_session.subject_id,
                notes=local_session.notes,
                started_at=self._dt_from_ms(local_session.started_at_ms),
                csv_path=str(local_session.csv_path),
                meta_path=str(local_session.meta_path),
                source_type="pc_gateway",
                user_id=user.id if user else None,
                device_id=device.id if device else None,
            )
            session.add(row)
            session.flush()
            return self._sensor_session_to_dict(row)

    def finish_sensor_session(self, local_session: RecordingSession) -> dict[str, Any] | None:
        with self._manager.session_scope() as session:
            row = session.execute(
                select(SensorSession).where(SensorSession.session_id == local_session.session_id)
            ).scalars().first()
            if row is None:
                return None

            row.rows_written = local_session.rows_written
            row.stop_reason = local_session.stop_reason
            row.csv_path = str(local_session.csv_path)
            row.meta_path = str(local_session.meta_path)
            if local_session.stopped_at_ms:
                row.stopped_at = self._dt_from_ms(local_session.stopped_at_ms)
                row.duration_ms = max(0, local_session.stopped_at_ms - local_session.started_at_ms)
            session.add(row)
            session.flush()
            return self._sensor_session_to_dict(row)

    def save_evaluation_result(
        self,
        *,
        session_id: str,
        evaluation_status: dict[str, Any] | None,
    ) -> dict[str, Any] | None:
        if not evaluation_status or not evaluation_status.get("available"):
            return None

        with self._manager.session_scope() as session:
            sensor_session = session.execute(
                select(SensorSession).where(SensorSession.session_id == session_id)
            ).scalars().first()
            if sensor_session is None:
                return None

            row = session.execute(
                select(EvaluationResult).where(EvaluationResult.sensor_session_id == sensor_session.id)
            ).scalars().first()
            if row is None:
                row = EvaluationResult(sensor_session_id=sensor_session.id, user_id=sensor_session.user_id)
                session.add(row)

            row.action_label = str(evaluation_status.get("actionLabel") or "idle")
            row.standard_score = int(evaluation_status.get("standardScore") or 0)
            row.depth_score = int(evaluation_status.get("depthScore") or 0)
            row.stability_score = int(evaluation_status.get("stabilityScore") or 0)
            row.rhythm_score = int(evaluation_status.get("rhythmScore") or 0)
            row.compensation_risk = str(evaluation_status.get("compensationRisk") or "unknown")
            row.suggestions_json = list(evaluation_status.get("suggestions") or [])
            row.voice_feedback_text = str((evaluation_status.get("voiceFeedback") or {}).get("text") or "")
            row.source = str(evaluation_status.get("source") or "pc_gateway_rules")
            session.flush()
            return self._evaluation_to_dict(row)

    def sync_current_model_version(self) -> dict[str, Any] | None:
        model_path = config.MODEL_PATH
        metrics_path = config.MODELS_ROOT / "metrics.json"
        label_map_path = config.LABEL_MAP_PATH
        if not model_path.exists():
            return None

        metrics_payload: dict[str, Any] = {}
        if metrics_path.exists():
            metrics_payload = json.loads(metrics_path.read_text(encoding="utf-8"))
        label_payload: dict[str, Any] = {}
        if label_map_path.exists():
            label_payload = json.loads(label_map_path.read_text(encoding="utf-8"))

        version = f"rf-{model_path.stat().st_mtime_ns}"
        labels = sorted(label_payload.keys())

        with self._manager.session_scope() as session:
            session.execute(update(ModelVersion).values(is_active=False))
            row = session.execute(select(ModelVersion).where(ModelVersion.version == version)).scalars().first()
            if row is None:
                row = ModelVersion(
                    model_name="random_forest_baseline",
                    model_type="random_forest",
                    task_type="action_classification",
                    version=version,
                    model_path=str(model_path),
                )
                session.add(row)

            row.labels_json = labels
            row.feature_count = metrics_payload.get("feature_count")
            row.val_accuracy = metrics_payload.get("val_accuracy")
            row.test_accuracy = metrics_payload.get("test_accuracy")
            row.metrics_path = str(metrics_path) if metrics_path.exists() else None
            row.is_active = True
            session.flush()
            return self._model_to_dict(row)

    def create_report_snapshot(self, report_summary: dict[str, Any]) -> dict[str, Any]:
        label_breakdown = report_summary.get("labelBreakdown") or {}
        best_action = None
        weak_action = None
        if label_breakdown:
            sorted_items = sorted(label_breakdown.items(), key=lambda item: item[1], reverse=True)
            best_action = sorted_items[0][0]
            weak_action = sorted_items[-1][0]

        with self._manager.session_scope() as session:
            avg_score = session.execute(select(func.avg(EvaluationResult.standard_score))).scalar()
            row = TrainingReport(
                report_date=date.today(),
                total_sessions=int(report_summary.get("totalSessions") or 0),
                total_duration_minutes=float(report_summary.get("totalDurationMinutes") or 0.0),
                avg_score=float(avg_score) if avg_score is not None else None,
                best_action=best_action,
                weak_action=weak_action,
                summary_text=f"当前阶段：{report_summary.get('stage') or '基础采集阶段'}",
                report_json=report_summary,
            )
            session.add(row)
            session.flush()
            return self._report_to_dict(row)

    def list_sensor_sessions(self, limit: int = 100) -> list[dict[str, Any]]:
        with self._manager.session_scope() as session:
            rows = session.execute(
                select(SensorSession).order_by(desc(SensorSession.started_at)).limit(limit)
            ).scalars().all()
            return [self._sensor_session_to_dict(row) for row in rows]

    def delete_sensor_session(self, session_id: str) -> dict[str, Any] | None:
        with self._manager.session_scope() as session:
            row = session.execute(
                select(SensorSession).where(SensorSession.session_id == session_id)
            ).scalars().first()
            if row is None:
                return None

            evaluation = session.execute(
                select(EvaluationResult).where(EvaluationResult.sensor_session_id == row.id)
            ).scalars().first()
            if evaluation is not None:
                session.delete(evaluation)

            payload = self._sensor_session_to_dict(row)
            session.delete(row)
            return payload

    def delete_sensor_sessions_by_label(self, label: str) -> dict[str, Any]:
        with self._manager.session_scope() as session:
            rows = session.execute(
                select(SensorSession).where(SensorSession.label == label)
            ).scalars().all()
            session_ids = [row.session_id for row in rows]
            deleted_evaluations = 0

            for row in rows:
                evaluation = session.execute(
                    select(EvaluationResult).where(EvaluationResult.sensor_session_id == row.id)
                ).scalars().first()
                if evaluation is not None:
                    session.delete(evaluation)
                    deleted_evaluations += 1
                session.delete(row)

            return {
                "label": label,
                "sessions": len(rows),
                "evaluations": deleted_evaluations,
                "sessionIds": session_ids,
            }

    def safe_delete_sensor_session(self, session_id: str) -> bool:
        try:
            return self.delete_sensor_session(session_id) is not None
        except Exception:
            return False

    def list_evaluations(self, limit: int = 100) -> list[dict[str, Any]]:
        with self._manager.session_scope() as session:
            rows = session.execute(
                select(EvaluationResult).order_by(desc(EvaluationResult.created_at)).limit(limit)
            ).scalars().all()
            return [self._evaluation_to_dict(row) for row in rows]

    def list_models(self, limit: int = 20) -> list[dict[str, Any]]:
        with self._manager.session_scope() as session:
            rows = session.execute(
                select(ModelVersion).order_by(desc(ModelVersion.created_at)).limit(limit)
            ).scalars().all()
            return [self._model_to_dict(row) for row in rows]

    def list_reports(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._manager.session_scope() as session:
            rows = session.execute(
                select(TrainingReport)
                .order_by(desc(TrainingReport.report_date), desc(TrainingReport.created_at))
                .limit(limit)
            ).scalars().all()
            return [self._report_to_dict(row) for row in rows]

    def get_user_dashboard(self, token_value: str) -> dict[str, Any]:
        with self._manager.session_scope() as session:
            token_row = session.execute(
                select(UserToken).where(
                    UserToken.token == token_value,
                    UserToken.expires_at >= datetime.now(timezone.utc),
                )
            ).scalars().first()
            if token_row is None:
                raise ValueError("Invalid or expired access token.")

            user = token_row.user
            user_sessions = session.execute(
                select(SensorSession)
                .where(SensorSession.user_id == user.id)
                .order_by(desc(SensorSession.started_at))
            ).scalars().all()
            user_evaluations = session.execute(
                select(EvaluationResult)
                .where(EvaluationResult.user_id == user.id)
                .order_by(desc(EvaluationResult.created_at))
            ).scalars().all()

            total_sessions = len(user_sessions)
            total_duration_minutes = round(
                sum(float(row.duration_ms or 0) for row in user_sessions) / 60000.0,
                1,
            )
            avg_score = None
            if user_evaluations:
                avg_score = round(
                    sum(float(row.standard_score or 0) for row in user_evaluations) / len(user_evaluations),
                    1,
                )

            label_breakdown: dict[str, int] = {}
            for row in user_sessions:
                label_breakdown[row.label] = label_breakdown.get(row.label, 0) + 1

            score_trend: dict[str, list[int]] = {}
            for row in user_evaluations:
                day_key = row.created_at.astimezone().strftime("%m-%d") if row.created_at else "unknown"
                score_trend.setdefault(day_key, []).append(int(row.standard_score or 0))

            latest_evaluation = self._evaluation_to_dict(user_evaluations[0]) if user_evaluations else None
            latest_sessions = [self._sensor_session_to_dict(row) for row in user_sessions[:5]]

            return {
                "user": self._user_to_dict(user),
                "totalSessions": total_sessions,
                "totalDurationMinutes": total_duration_minutes,
                "averageScore": avg_score,
                "labelBreakdown": label_breakdown,
                "latestEvaluation": latest_evaluation,
                "recentSessions": latest_sessions,
                "scoreTrend": [
                    {
                        "day": day,
                        "averageScore": round(sum(scores) / len(scores), 1),
                        "count": len(scores),
                    }
                    for day, scores in sorted(score_trend.items())
                ][-7:],
            }

    def safe_upsert_device(self, device_info: DeviceInfo, *, status: str = "online") -> dict[str, Any] | None:
        return self._safe_call(lambda: self.upsert_device(device_info, status=status))

    def safe_mark_device_offline(self, *, address: str | None) -> None:
        self._safe_call(lambda: self.mark_device_offline(address=address))

    def safe_create_sensor_session(
        self,
        *,
        local_session: RecordingSession,
        device_address: str | None,
    ) -> dict[str, Any] | None:
        return self._safe_call(
            lambda: self.create_sensor_session(local_session=local_session, device_address=device_address)
        )

    def safe_finish_sensor_session(self, local_session: RecordingSession) -> dict[str, Any] | None:
        return self._safe_call(lambda: self.finish_sensor_session(local_session))

    def safe_delete_sensor_session(self, session_id: str) -> dict[str, Any] | None:
        return self._safe_call(lambda: self.delete_sensor_session(session_id))

    def safe_delete_sensor_sessions_by_label(self, label: str) -> dict[str, Any] | None:
        return self._safe_call(lambda: self.delete_sensor_sessions_by_label(label))

    def safe_save_evaluation_result(
        self,
        *,
        session_id: str,
        evaluation_status: dict[str, Any] | None,
    ) -> dict[str, Any] | None:
        return self._safe_call(
            lambda: self.save_evaluation_result(session_id=session_id, evaluation_status=evaluation_status)
        )

    def safe_sync_current_model_version(self) -> dict[str, Any] | None:
        return self._safe_call(self.sync_current_model_version)

    def safe_create_report_snapshot(self, report_summary: dict[str, Any]) -> dict[str, Any] | None:
        return self._safe_call(lambda: self.create_report_snapshot(report_summary))

    def _safe_call(self, func: Any) -> Any:
        if not self._manager.enabled:
            return None
        try:
            return func()
        except Exception:
            return None

    def _generate_token(self) -> str:
        from .security import generate_access_token

        return generate_access_token()

    def _find_device(self, session: Any, address: str | None) -> Device | None:
        if not address:
            return None
        return session.execute(select(Device).where(Device.ble_address == address)).scalars().first()

    def _find_user(self, session: Any, subject_id: str | None) -> User | None:
        if not subject_id:
            return None
        return session.execute(
            select(User).where(
                or_(User.username == subject_id, User.student_no == subject_id, User.email == subject_id)
            )
        ).scalars().first()

    def _dt_from_ms(self, value: int | None) -> datetime | None:
        if not value:
            return None
        return datetime.fromtimestamp(value / 1000.0, tz=timezone.utc)

    def _user_to_dict(self, user: User) -> dict[str, Any]:
        return {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "fullName": user.full_name,
            "studentNo": user.student_no,
            "role": user.role,
            "createdAt": user.created_at.isoformat(),
        }

    def _device_to_dict(self, row: Device) -> dict[str, Any]:
        return {
            "id": row.id,
            "deviceName": row.device_name,
            "bleAddress": row.ble_address,
            "firmwareVersion": row.firmware_version,
            "status": row.status,
            "lastSeenAt": row.last_seen_at.isoformat() if row.last_seen_at else None,
        }

    def _sensor_session_to_dict(self, row: SensorSession) -> dict[str, Any]:
        return {
            "id": row.id,
            "sessionId": row.session_id,
            "label": row.label,
            "subjectId": row.subject_id,
            "startedAt": row.started_at.isoformat() if row.started_at else None,
            "stoppedAt": row.stopped_at.isoformat() if row.stopped_at else None,
            "durationMs": row.duration_ms,
            "rowsWritten": row.rows_written,
            "csvPath": row.csv_path,
            "metaPath": row.meta_path,
            "stopReason": row.stop_reason,
            "deviceId": row.device_id,
            "userId": row.user_id,
        }

    def _evaluation_to_dict(self, row: EvaluationResult) -> dict[str, Any]:
        return {
            "id": row.id,
            "sensorSessionId": row.sensor_session_id,
            "userId": row.user_id,
            "actionLabel": row.action_label,
            "standardScore": row.standard_score,
            "depthScore": row.depth_score,
            "stabilityScore": row.stability_score,
            "rhythmScore": row.rhythm_score,
            "compensationRisk": row.compensation_risk,
            "suggestions": row.suggestions_json or [],
            "voiceFeedbackText": row.voice_feedback_text,
            "source": row.source,
            "createdAt": row.created_at.isoformat() if row.created_at else None,
        }

    def _model_to_dict(self, row: ModelVersion) -> dict[str, Any]:
        return {
            "id": row.id,
            "modelName": row.model_name,
            "modelType": row.model_type,
            "taskType": row.task_type,
            "version": row.version,
            "labels": row.labels_json or [],
            "featureCount": row.feature_count,
            "valAccuracy": row.val_accuracy,
            "testAccuracy": row.test_accuracy,
            "modelPath": row.model_path,
            "metricsPath": row.metrics_path,
            "isActive": row.is_active,
            "createdAt": row.created_at.isoformat() if row.created_at else None,
        }

    def _report_to_dict(self, row: TrainingReport) -> dict[str, Any]:
        return {
            "id": row.id,
            "userId": row.user_id,
            "reportDate": row.report_date.isoformat() if row.report_date else None,
            "totalSessions": row.total_sessions,
            "totalDurationMinutes": row.total_duration_minutes,
            "avgScore": row.avg_score,
            "bestAction": row.best_action,
            "weakAction": row.weak_action,
            "summaryText": row.summary_text,
            "report": row.report_json,
            "createdAt": row.created_at.isoformat() if row.created_at else None,
        }
