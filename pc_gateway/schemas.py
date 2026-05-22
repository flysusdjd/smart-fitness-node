from __future__ import annotations

from pydantic import BaseModel, Field

from .config import DEFAULT_SCAN_TIMEOUT_S, DEVICE_NAME, RECOMMENDED_LABELS


class ConnectRequest(BaseModel):
    address: str | None = None
    device_name: str = DEVICE_NAME
    timeout_s: float = Field(default=DEFAULT_SCAN_TIMEOUT_S, ge=1.0, le=30.0)


class StartRecordingRequest(BaseModel):
    label: str = Field(..., min_length=1)
    subject_id: str | None = None
    notes: str | None = None


class StartModelTrainingRequest(BaseModel):
    labels: list[str] = Field(default_factory=list)
    window_size: int = Field(default=20, ge=5, le=200)
    step_size: int = Field(default=5, ge=1, le=100)
    auto_reload: bool = True


class RemoveLabelFromModelRequest(BaseModel):
    label: str = Field(..., min_length=1, max_length=48)
    window_size: int = Field(default=20, ge=5, le=200)
    step_size: int = Field(default=5, ge=1, le=100)
    auto_reload: bool = True


class CreateLabelRequest(BaseModel):
    label: str = Field(..., min_length=1, max_length=48)


class ScanResponse(BaseModel):
    devices: list[dict]


class LabelsResponse(BaseModel):
    recommended: list[str] = RECOMMENDED_LABELS
    available: list[str]
    counts: dict[str, int] = Field(default_factory=dict)
