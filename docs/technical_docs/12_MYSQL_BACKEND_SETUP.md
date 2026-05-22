# MySQL 后端接入说明

## 当前状态

项目已经完成以下接入：

- PC 网关支持读取项目根目录下的 `.env`
- MySQL 默认目标库为 `smart_fitness`
- 数据表结构已接入 SQLAlchemy ORM
- 网页已经支持数据库状态、初始化、注册、登录和用户中心展示

## 项目根目录下的数据库配置

当前项目会优先读取：

- `.env`
- `.env.local`

示例配置如下：

```env
MYSQL_ENABLED=true
MYSQL_HOST=127.0.0.1
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=你的密码
MYSQL_DATABASE=smart_fitness
DATABASE_ECHO=false
TOKEN_TTL_HOURS=168
```

## 已接入的数据表

初始化数据库后会自动创建这些表：

- `users`
- `user_tokens`
- `devices`
- `sensor_sessions`
- `model_versions`
- `evaluation_results`
- `training_reports`

## 已接入的 API

数据库状态：

- `GET /api/database/status`

初始化数据库：

- `POST /api/database/init`

用户注册：

- `POST /api/auth/register`

用户登录：

- `POST /api/auth/login`

获取当前用户：

- `GET /api/auth/me`

查看数据库中的用户：

- `GET /api/database/users`

查看数据库中的采集会话：

- `GET /api/database/sessions`

查看数据库中的评估结果：

- `GET /api/database/evaluations`

查看数据库中的模型版本：

- `GET /api/database/models`

查看数据库中的报告快照：

- `GET /api/database/reports`

## 自动入库逻辑

当你使用 PC 网关时，下面这些内容会自动尝试写入 MySQL：

- 设备连接成功时：写入或更新 `devices`
- 开始采集时：写入 `sensor_sessions`
- 停止采集时：更新 `sensor_sessions`
- 结束采集时：写入 `evaluation_results`
- 重载模型时：同步 `model_versions`
- 生成报告汇总时：写入 `training_reports`

## 当前建议

当前阶段建议继续保持：

- 原始高频传感器数据继续保存为 CSV
- 数据库先负责用户、设备、会话、评估、模型版本和报告摘要

这样后续继续接入：

- 用户系统
- 个性化训练报告
- 数据库查询页面
- 服务端复杂模型

时都不需要推翻现有结构。
