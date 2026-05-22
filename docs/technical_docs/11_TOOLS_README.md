# 项目工具脚本说明

## Arduino / ESP32

- `tools\compile-esp32.ps1`
  - 编译 [ESPS3.ino](/C:/Users/flysusdjd/Documents/New%20project%203/ESPS3/ESPS3.ino)
- `tools\list-boards.ps1`
  - 查看当前串口和开发板
- `tools\upload-esp32.ps1 -Port COMx`
  - 编译并上传到指定串口

## 电脑网关

- `tools\install-gateway-deps.ps1`
  - 安装电脑网关依赖
- `tools\run-gateway.ps1`
  - 启动本地网关服务

## 数据集与训练

- `tools\prepare-dataset.ps1`
  - 运行数据预处理，默认窗口长度 `20`，步长 `5`
- `tools\train-baseline.ps1`
  - 训练第一版随机森林基线模型

## 常用命令

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\compile-esp32.ps1
```

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\run-gateway.ps1
```

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\prepare-dataset.ps1
```

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\train-baseline.ps1
```
