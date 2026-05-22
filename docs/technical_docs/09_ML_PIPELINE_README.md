# Fitness Dataset Pipeline

这个目录用于管理动作识别模型训练前的数据整理、窗口切分和第一版基线模型训练。

## 目录结构

```text
ml_pipeline/
├── data/
│   ├── raw/
│   ├── processed/
│   ├── splits/
│   └── models/
├── prepare_dataset.py
├── train_baseline.py
└── requirements.txt
```

## 原始数据要求

当前训练脚本至少需要这些字段：

```text
label,seq,timestampMs,ax,ay,az,gx,gy,gz,flexIndex
```

电脑网关生成的 CSV 已经包含这些字段，可以直接使用。

## 当前默认特征

训练使用的基础信号列是：

```text
ax, ay, az, gx, gy, gz, flexIndex
```

每个窗口会提取：

- `mean`
- `std`
- `min`
- `max`
- `ptp`
- `rms`

## 标签建议

- `idle`
- `squat_standard`
- `squat_wrong`
- `bench_standard`
- `bench_wrong`

## 使用流程

### 1. 预处理数据

```powershell
.\ml_pipeline\.venv\Scripts\python.exe .\ml_pipeline\prepare_dataset.py
```

或者：

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\prepare-dataset.ps1
```

### 2. 训练第一版基线模型

```powershell
.\ml_pipeline\.venv\Scripts\python.exe .\ml_pipeline\train_baseline.py
```

或者：

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\train-baseline.ps1
```

## 输出内容

运行 `prepare_dataset.py` 后会生成：

- `data/processed/windows/windows.csv`
- `data/processed/features/features.csv`
- `data/processed/labels/label_map.json`
- `data/processed/labels/dataset_meta.json`
- `data/splits/train.csv`
- `data/splits/val.csv`
- `data/splits/test.csv`

运行 `train_baseline.py` 后会生成：

- `data/models/random_forest_model.joblib`
- `data/models/metrics.json`

## 当前建议

- BLE 采样率先按当前约 `10Hz` 使用
- 默认窗口长度 `20`
- 默认步长 `5`
- 每个标签至少先录 `10~15` 个文件
- 每个文件建议 `20~30` 秒
