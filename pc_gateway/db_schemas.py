"""认证接口请求模型：校验注册与登录参数。"""

from __future__ import annotations

from pydantic import BaseModel, Field


# POST /api/auth/register 的请求体。
# 这里用 Pydantic 限制用户名和密码长度，避免空账号、过短密码直接进入数据库。
class RegisterUserRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=64)
    password: str = Field(..., min_length=8, max_length=128)


# POST /api/auth/login 的请求体。
# 登录成功后后端会返回 accessToken，网页和安卓端都靠这个令牌保持登录态。
class LoginRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=64)
    password: str = Field(..., min_length=8, max_length=128)
