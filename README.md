# Smart Fitness Node

智能健身动作识别项目，包含 ESP32-S3 采集端、Android 客户端、PC BLE 网关、网页控制台、机器学习训练流水线和最终检查文档。

## 项目结构

```text
ESPS3/             ESP32-S3 Arduino 固件
esp32s3/           Android 客户端工程
pc_gateway/        PC 侧 BLE 网关、后端 API 和网页控制台
ml_pipeline/       数据预处理、模型训练和当前模型文件
docs/technical_docs/  项目说明、答辩材料、演示脚本和配置文档
tools/             常用 PowerShell 启动、训练、编译脚本
```

## 快速启动

1. 复制 `.env.example` 为 `.env`，按本机 MySQL 配置修改密码和数据库名。
2. 安装 PC 网关依赖：

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\install-gateway-deps.ps1
```

3. 启动 PC 网关和网页控制台：

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\run-gateway.ps1
```

4. 训练或更新模型：

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\prepare-dataset.ps1
powershell -ExecutionPolicy Bypass -File .\tools\train-baseline.ps1
```

5. 编译 ESP32-S3 固件：

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\compile-esp32.ps1
```

## 成品说明

当前运行时模型位于 `ml_pipeline/data/models/random_forest_model.joblib`，标签映射位于 `ml_pipeline/data/processed/labels/label_map.json`。最终检查优先查看 `docs/technical_docs/DOCUMENT_INDEX.md`、`docs/technical_docs/FINAL_CHECK_DEMO_SCRIPT.md` 和 `docs/technical_docs/PROJECT_TECHNICAL_DEFENSE_GUIDE.md`。

本仓库不会提交本机虚拟环境、构建输出、IDE 配置、真实 `.env`、浏览器预览缓存和外部传感器资料包。
