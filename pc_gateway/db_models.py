from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        onupdate=utcnow,
        nullable=False,
    )


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(256), nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    student_no: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True, index=True)
    role: Mapped[str] = mapped_column(String(32), default="student", nullable=False)

    tokens: Mapped[list["UserToken"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    sessions: Mapped[list["SensorSession"]] = relationship(back_populates="user")


class UserToken(Base):
    __tablename__ = "user_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    token: Mapped[str] = mapped_column(String(256), unique=True, nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    user: Mapped[User] = relationship(back_populates="tokens")


class Device(TimestampMixin, Base):
    __tablename__ = "devices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    device_code: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True)
    device_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    ble_address: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    firmware_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="offline", nullable=False)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    sessions: Mapped[list["SensorSession"]] = relationship(back_populates="device")


class SensorSession(TimestampMixin, Base):
    __tablename__ = "sensor_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    label: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    subject_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    stopped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rows_written: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    csv_path: Mapped[str] = mapped_column(String(512), nullable=False)
    meta_path: Mapped[str] = mapped_column(String(512), nullable=False)
    source_type: Mapped[str] = mapped_column(String(32), default="pc_gateway", nullable=False)
    stop_reason: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    device_id: Mapped[int | None] = mapped_column(ForeignKey("devices.id", ondelete="SET NULL"), nullable=True, index=True)

    user: Mapped[User | None] = relationship(back_populates="sessions")
    device: Mapped[Device | None] = relationship(back_populates="sessions")
    evaluation: Mapped["EvaluationResult | None"] = relationship(back_populates="sensor_session", uselist=False)


class ModelVersion(TimestampMixin, Base):
    __tablename__ = "model_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    model_name: Mapped[str] = mapped_column(String(128), nullable=False)
    model_type: Mapped[str] = mapped_column(String(64), nullable=False)
    task_type: Mapped[str] = mapped_column(String(64), nullable=False)
    version: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)
    labels_json: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    feature_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    val_accuracy: Mapped[float | None] = mapped_column(Float, nullable=True)
    test_accuracy: Mapped[float | None] = mapped_column(Float, nullable=True)
    model_path: Mapped[str] = mapped_column(String(512), nullable=False)
    metrics_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class EvaluationResult(TimestampMixin, Base):
    __tablename__ = "evaluation_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sensor_session_id: Mapped[int | None] = mapped_column(
        ForeignKey("sensor_sessions.id", ondelete="SET NULL"),
        unique=True,
        nullable=True,
        index=True,
    )
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    action_label: Mapped[str] = mapped_column(String(64), nullable=False)
    standard_score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    depth_score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    stability_score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    rhythm_score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    compensation_risk: Mapped[str] = mapped_column(String(32), default="unknown", nullable=False)
    suggestions_json: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    voice_feedback_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(String(64), default="pc_gateway_rules", nullable=False)

    sensor_session: Mapped[SensorSession | None] = relationship(back_populates="evaluation")


class TrainingReport(TimestampMixin, Base):
    __tablename__ = "training_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    report_date: Mapped[date] = mapped_column(Date, default=date.today, nullable=False, index=True)
    total_sessions: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_duration_minutes: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    avg_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    best_action: Mapped[str | None] = mapped_column(String(64), nullable=True)
    weak_action: Mapped[str | None] = mapped_column(String(64), nullable=True)
    summary_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    report_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
