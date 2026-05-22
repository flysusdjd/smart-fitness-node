from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split


FEATURE_COLUMNS = ["ax", "ay", "az", "gx", "gy", "gz", "flexIndex"]
REQUIRED_COLUMNS = ["label", "seq", "timestampMs", *FEATURE_COLUMNS]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare fitness action dataset.")
    parser.add_argument("--data-root", type=Path, default=Path(__file__).resolve().parent / "data")
    parser.add_argument("--window-size", type=int, default=20)
    parser.add_argument("--step-size", type=int, default=5)
    parser.add_argument("--labels", nargs="*", default=None)
    parser.add_argument("--train-size", type=float, default=0.7)
    parser.add_argument("--val-size", type=float, default=0.15)
    parser.add_argument("--test-size", type=float, default=0.15)
    return parser.parse_args()


def ensure_dirs(data_root: Path) -> dict[str, Path]:
    paths = {
        "raw": data_root / "raw",
        "processed_windows": data_root / "processed" / "windows",
        "processed_features": data_root / "processed" / "features",
        "processed_labels": data_root / "processed" / "labels",
        "splits": data_root / "splits",
    }
    for path in paths.values():
        path.mkdir(parents=True, exist_ok=True)
    return paths


def load_csv_files(raw_root: Path, labels: set[str] | None = None) -> list[tuple[str, Path]]:
    files: list[tuple[str, Path]] = []
    for label_dir in sorted(raw_root.iterdir()):
        if not label_dir.is_dir():
            continue
        if labels is not None and label_dir.name not in labels:
            continue
        for csv_file in sorted(label_dir.glob("*.csv")):
            files.append((label_dir.name, csv_file))
    return files


def validate_columns(df: pd.DataFrame, csv_path: Path) -> None:
    missing = [column for column in REQUIRED_COLUMNS if column not in df.columns]
    if missing:
        raise ValueError(f"{csv_path} missing required columns: {missing}")


def build_window_records(
    label: str,
    csv_path: Path,
    df: pd.DataFrame,
    window_size: int,
    step_size: int,
) -> Iterable[dict]:
    data = df.reset_index(drop=True)
    if len(data) < window_size:
        return []

    records: list[dict] = []
    for start in range(0, len(data) - window_size + 1, step_size):
        end = start + window_size
        window = data.iloc[start:end]
        feature_values = window[FEATURE_COLUMNS].to_numpy(dtype=float)

        record = {
            "label": label,
            "source_file": csv_path.name,
            "source_path": str(csv_path),
            "window_index": len(records),
            "start_row": start,
            "end_row": end - 1,
            "start_seq": int(window["seq"].iloc[0]),
            "end_seq": int(window["seq"].iloc[-1]),
            "start_timestamp_ms": int(window["timestampMs"].iloc[0]),
            "end_timestamp_ms": int(window["timestampMs"].iloc[-1]),
        }

        for feature_index, feature_name in enumerate(FEATURE_COLUMNS):
            signal = feature_values[:, feature_index]
            record[f"{feature_name}_mean"] = float(np.mean(signal))
            record[f"{feature_name}_std"] = float(np.std(signal))
            record[f"{feature_name}_min"] = float(np.min(signal))
            record[f"{feature_name}_max"] = float(np.max(signal))
            record[f"{feature_name}_ptp"] = float(np.ptp(signal))
            record[f"{feature_name}_rms"] = float(np.sqrt(np.mean(np.square(signal))))

        records.append(record)

    return records


def split_by_file(features_df: pd.DataFrame, args: argparse.Namespace) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    files_df = features_df[["source_file", "label"]].drop_duplicates().reset_index(drop=True)

    if len(files_df) < 3:
        raise ValueError("At least 3 source files are required to split into train/val/test.")

    train_files, temp_files = train_test_split(
        files_df,
        train_size=args.train_size,
        stratify=files_df["label"],
        random_state=42,
    )

    temp_ratio = args.val_size + args.test_size
    val_fraction_of_temp = args.val_size / temp_ratio

    val_files, test_files = train_test_split(
        temp_files,
        train_size=val_fraction_of_temp,
        stratify=temp_files["label"],
        random_state=42,
    )

    train_df = features_df[features_df["source_file"].isin(train_files["source_file"])]
    val_df = features_df[features_df["source_file"].isin(val_files["source_file"])]
    test_df = features_df[features_df["source_file"].isin(test_files["source_file"])]
    return train_df, val_df, test_df


def main() -> None:
    args = parse_args()
    paths = ensure_dirs(args.data_root)
    selected_labels = {label for label in (args.labels or []) if label}
    csv_files = load_csv_files(paths["raw"], selected_labels or None)

    if not csv_files:
        raise SystemExit("No CSV files found under data/raw/. Please export and copy recordings first.")

    window_records: list[dict] = []
    label_names: set[str] = set()

    for label, csv_path in csv_files:
        df = pd.read_csv(csv_path)
        validate_columns(df, csv_path)
        label_names.add(label)
        window_records.extend(build_window_records(label, csv_path, df, args.window_size, args.step_size))

    if not window_records:
        raise SystemExit("No valid windows were generated. Check file duration and window size.")

    windows_df = pd.DataFrame(window_records)
    windows_path = paths["processed_windows"] / "windows.csv"
    windows_df.to_csv(windows_path, index=False)

    label_map = {label: index for index, label in enumerate(sorted(label_names))}
    label_map_path = paths["processed_labels"] / "label_map.json"
    label_map_path.write_text(json.dumps(label_map, indent=2, ensure_ascii=False), encoding="utf-8")

    features_df = windows_df.copy()
    features_df["label_id"] = features_df["label"].map(label_map)
    features_path = paths["processed_features"] / "features.csv"
    features_df.to_csv(features_path, index=False)

    train_df, val_df, test_df = split_by_file(features_df, args)
    train_df.to_csv(paths["splits"] / "train.csv", index=False)
    val_df.to_csv(paths["splits"] / "val.csv", index=False)
    test_df.to_csv(paths["splits"] / "test.csv", index=False)

    summary = {
        "source_files": len(csv_files),
        "labels": sorted(label_names),
        "selected_labels": sorted(selected_labels),
        "window_size": args.window_size,
        "step_size": args.step_size,
        "train_size": args.train_size,
        "val_size": args.val_size,
        "test_size": args.test_size,
        "windows_total": len(features_df),
        "train_windows": len(train_df),
        "val_windows": len(val_df),
        "test_windows": len(test_df),
    }
    dataset_meta_path = paths["processed_labels"] / "dataset_meta.json"
    dataset_meta_path.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
