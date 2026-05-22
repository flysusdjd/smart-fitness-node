# Smart Fitness PC Gateway

这个目录提供电脑侧的 BLE 网关、录制服务和网页控制台。

## 当前功能

- 扫描并连接 `ESP32S3_Fitness_BLE`
- 接收 BLE 实时数据
- 保存带标签的 CSV 和 JSON 元数据
- 网页端显示实时波形和传感器数值
- 训练好模型后直接在网关里做在线动作识别

## BLE 数据格式

```text
seq,timestampMs,ax,ay,az,gx,gy,gz,flexRawAdc,flexRawMv,flexIndex
```

## 录制输出

录制文件保存在：

```text
ml_pipeline/data/raw/<label>/
```

CSV 字段如下：

```text
recordTimeIso,recordTimeMs,sessionId,label,seq,timestampMs,ax,ay,az,gx,gy,gz,flexRawAdc,flexRawMv,flexIndex,rawPacket
```

## 在线识别

网关会尝试读取：

- `ml_pipeline/data/models/random_forest_model.joblib`
- `ml_pipeline/data/processed/labels/label_map.json`

如果模型存在，就会在网页里显示：

- 当前动作类别
- 置信度
- Top 3 预测
- 滑动窗口填充进度

## 启动方式

推荐运行：

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\run-gateway.ps1
```

或者在 PyCharm 里直接运行 [main.py](/C:/Users/flysusdjd/Documents/New%20project%203/pc_gateway/main.py)。
