# Navicat 连接与初始化说明

## 1. 打开 Navicat，新建连接

连接类型选择：

- `MySQL`

## 2. 连接参数

按当前项目的本地配置填写：

- 连接名：`smart_fitness_local`
- 主机：`127.0.0.1`
- 端口：`3306`
- 用户名：`root`
- 密码：以你本机 MySQL 实际密码为准

如果你使用的是当前项目默认 `.env` 配置，那么数据库名是：

- `smart_fitness`

## 3. 测试连接

点击：

- `测试连接`

如果成功，说明 MySQL 服务已正常运行。

## 4. 查看数据库

连接成功后，在左侧连接树中查看：

- `smart_fitness`

如果库不存在，可以手动创建：

- 右键连接
- 选择“新建数据库”
- 名称填：`smart_fitness`
- 字符集选择：`utf8mb4`
- 排序规则选择：`utf8mb4_general_ci`

## 5. 初始化数据表

数据表不是在 Navicat 里手工创建，而是通过项目后端自动初始化。

做法：

1. 启动网关
2. 打开网页首页
3. 在“数据库状态”模块点击“初始化数据库”

或者直接请求：

- `POST /api/database/init`

完成后，Navicat 刷新数据库即可看到表结构。

## 6. 初始化后应看到的表

- `users`
- `user_tokens`
- `devices`
- `sensor_sessions`
- `model_versions`
- `evaluation_results`
- `training_reports`

## 7. 你在 Navicat 里主要做什么

后面你可以用 Navicat 做这些事：

- 查看用户是否注册成功
- 查看采集记录是否写入 `sensor_sessions`
- 查看评估结果是否写入 `evaluation_results`
- 查看模型版本是否写入 `model_versions`
- 查看报告快照是否写入 `training_reports`

## 8. 建议的使用分工

建议你这样分工：

- 项目代码负责：建表、入库、查询接口
- Navicat 负责：看数据、查表、验证结果

这样最稳，也最适合答辩展示。
