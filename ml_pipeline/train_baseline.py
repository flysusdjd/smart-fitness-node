from __future__ import annotations

import argparse
import json
from pathlib import Path

import joblib
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix


NON_FEATURE_COLUMNS = {
    "label",
    "label_id",
    "source_file",
    "source_path",
    "window_index",
    "start_row",
    "end_row",
    "start_seq",
    "end_seq",
    "start_timestamp_ms",
    "end_timestamp_ms",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train the baseline fitness classifier.")
    parser.add_argument(
        "--n-jobs",
        type=int,
        default=1,
        help="Number of parallel jobs for RandomForest. Default 1 for Windows stability.",
    )
    return parser.parse_args()


def load_split(csv_path: Path) -> pd.DataFrame:
    if not csv_path.exists():
        raise FileNotFoundError(f"Split file not found: {csv_path}")
    return pd.read_csv(csv_path)


def select_feature_columns(df: pd.DataFrame) -> list[str]:
    return [column for column in df.columns if column not in NON_FEATURE_COLUMNS]


def main() -> None:
    args = parse_args()
    pipeline_root = Path(__file__).resolve().parent
    data_root = pipeline_root / "data"
    processed_labels_root = data_root / "processed" / "labels"
    splits_root = data_root / "splits"
    models_root = data_root / "models"
    models_root.mkdir(parents=True, exist_ok=True)

    train_df = load_split(splits_root / "train.csv")
    val_df = load_split(splits_root / "val.csv")
    test_df = load_split(splits_root / "test.csv")

    feature_columns = select_feature_columns(train_df)
    label_map_path = processed_labels_root / "label_map.json"
    dataset_meta_path = processed_labels_root / "dataset_meta.json"
    label_map = json.loads(label_map_path.read_text(encoding="utf-8")) if label_map_path.exists() else {}
    dataset_meta = json.loads(dataset_meta_path.read_text(encoding="utf-8")) if dataset_meta_path.exists() else {}
    x_train = train_df[feature_columns]
    y_train = train_df["label_id"]
    x_val = val_df[feature_columns]
    y_val = val_df["label_id"]
    x_test = test_df[feature_columns]
    y_test = test_df["label_id"]

    unique_labels = sorted(pd.concat([y_train, y_val, y_test], axis=0).dropna().unique().tolist())
    if len(unique_labels) < 2:
        raise ValueError(
            "Need at least two labels with samples to train a classifier. "
            f"Current labels: {unique_labels}"
        )

    model = RandomForestClassifier(
        n_estimators=300,
        max_depth=None,
        min_samples_split=2,
        min_samples_leaf=1,
        random_state=42,
        n_jobs=args.n_jobs,
        class_weight="balanced",
    )
    model.fit(x_train, y_train)

    val_pred = model.predict(x_val)
    test_pred = model.predict(x_test)

    metrics = {
        "feature_count": len(feature_columns),
        "n_jobs": args.n_jobs,
        "train_samples": int(len(train_df)),
        "val_samples": int(len(val_df)),
        "test_samples": int(len(test_df)),
        "val_accuracy": float(accuracy_score(y_val, val_pred)),
        "test_accuracy": float(accuracy_score(y_test, test_pred)),
        "classification_report": classification_report(y_test, test_pred, output_dict=True, zero_division=0),
        "confusion_matrix": confusion_matrix(y_test, test_pred).tolist(),
    }

    joblib.dump(
        {
            "model": model,
            "feature_columns": feature_columns,
            "label_map": label_map,
            "dataset_meta": dataset_meta,
        },
        models_root / "random_forest_model.joblib",
    )
    (models_root / "metrics.json").write_text(
        json.dumps(metrics, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print(json.dumps({
        "val_accuracy": metrics["val_accuracy"],
        "test_accuracy": metrics["test_accuracy"],
        "feature_count": metrics["feature_count"],
    }, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
