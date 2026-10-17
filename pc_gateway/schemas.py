"""FastAPI 请求与响应模型：统一前端调用网关接口时的字段校验规则。"""

from __future__ import annotations

from pydantic import BaseModel, Field

from .config import DEFAULT_SCAN_TIMEOUT_S, DEVICE_NAME, RECOMMENDED_LABELS


# POST /api/device/connect 的请求体。
# address 指定某个 BLE 地址时直接连接；为空时按 device_name 扫描默认设备。
class ConnectRequest(BaseModel):
    address: str | None = None
    device_name: str = DEVICE_NAME
    timeout_s: float = Field(default=DEFAULT_SCAN_TIMEOUT_S, ge=1.0, le=30.0)


# POST /api/recordings/start 的请求体。
# label 是这组数据的训练标签；subject_id 用来把采集数据关联到登录用户或被试编号。
class StartRecordingRequest(BaseModel):
    label: str = Field(..., min_length=1)
    subject_id: str | None = None
    notes: str | None = None


# POST /api/models/train 的请求体。
# labels 决定训练哪些动作类别，window_size/step_size 决定把连续传感器数据切成多少个窗口样本。
class StartModelTrainingRequest(BaseModel):
    labels: list[str] = Field(default_factory=list)
    window_size: int = Field(default=20, ge=5, le=200)
    step_size: int = Field(default=5, ge=1, le=100)
    auto_reload: bool = True


# POST /api/models/remove-label 的请求体。
# 删除模型中的某个类别不能直接改随机森林内部树结构，所以这里用“排除该标签后重新训练”实现。
class RemoveLabelFromModelRequest(BaseModel):
    label: str = Field(..., min_length=1, max_length=48)
    window_size: int = Field(default=20, ge=5, le=200)
    step_size: int = Field(default=5, ge=1, le=100)
    auto_reload: bool = True


# POST /api/labels 的请求体，用于新增开发者采集标签。
class CreateLabelRequest(BaseModel):
    label: str = Field(..., min_length=1, max_length=48)


# GET /api/devices/scan 的响应体，devices 是 Bleak 扫描到的设备列表。
class ScanResponse(BaseModel):
    devices: list[dict]


# GET /api/labels 的响应体。
# recommended 是系统内置推荐标签，available/counts 是当前数据目录里真实存在的标签及样本数。
class LabelsResponse(BaseModel):
    recommended: list[str] = RECOMMENDED_LABELS
    available: list[str]
    counts: dict[str, int] = Field(default_factory=dict)
