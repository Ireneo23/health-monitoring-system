# Train a machine learning model on health_data.csv using BPM and temperature.
# Tune a probability cutoff and save model.pkl plus model_threshold.json for live prediction.
# Run this when you change your dataset and want a fresh model.
"""
Train LogisticRegression on health_data.csv; tune ML probability threshold via OOF CV;
save model.pkl and model_threshold.json for rules.py.
"""
from __future__ import annotations

import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, confusion_matrix, f1_score
from sklearn.model_selection import StratifiedKFold, cross_val_predict

from rules import is_plausible

_DATA_DIR = Path(__file__).resolve().parent
_HEALTH_PATH = _DATA_DIR / "health_data.csv"
_MODEL_PATH = _DATA_DIR / "model.pkl"
_THRESHOLD_PATH = _DATA_DIR / "model_threshold.json"

# Fallback if JSON missing (development)
_DEFAULT_THRESHOLD = 0.5


def _load_health_frame() -> pd.DataFrame:
    if not _HEALTH_PATH.is_file():
        raise FileNotFoundError(_HEALTH_PATH)
    with _HEALTH_PATH.open("rb") as _f:
        is_excel = _f.read(2) == b"PK"
    if is_excel:
        return pd.read_excel(_HEALTH_PATH, engine="openpyxl")
    return pd.read_csv(_HEALTH_PATH, encoding="utf-8-sig")


def _target_column(df: pd.DataFrame) -> str:
    if "label_gt" in df.columns:
        return "label_gt"
    return "label"


def _training_mask(df: pd.DataFrame) -> pd.Series:
    """Prefer rows flagged plausible when quality_flag exists; else compute via rules.is_plausible."""
    if "quality_flag" in df.columns:
        return df["quality_flag"].astype(int) == 1
    return df.apply(lambda r: is_plausible(float(r["bpm"]), float(r["temperature"])), axis=1)


def _oof_best_threshold(model: LogisticRegression, X: pd.DataFrame, y: pd.Series, random_state: int) -> tuple[float, float]:
    """Return (best_threshold, best_oof_f1)."""
    n_splits = min(5, y.value_counts().min())
    n_splits = max(2, n_splits)
    skf = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=random_state)
    proba = cross_val_predict(model, X, y, cv=skf, method="predict_proba")
    p_risk = proba[:, 1] if proba.shape[1] > 1 else proba[:, 0]

    best_t = _DEFAULT_THRESHOLD
    best_f1 = -1.0
    for t in np.linspace(0.01, 0.99, 99):
        pred = (p_risk >= t).astype(int)
        f1 = f1_score(y, pred, average="binary", zero_division=0)
        if f1 > best_f1:
            best_f1 = f1
            best_t = float(t)
    return best_t, best_f1


def main() -> None:
    data = _load_health_frame()
    y_col = _target_column(data)
    mask = _training_mask(data)
    data = data.loc[mask].copy()
    if data.empty:
        raise ValueError("No training rows after quality filter.")

    X = data[["bpm", "temperature"]]
    y = data[y_col].astype(int)

    print(f"Training rows: {len(y)} (target={y_col}; features=bpm,temperature only; label_rule ignored)")
    print("Class counts:\n", y.value_counts().sort_index())

    model = LogisticRegression(max_iter=2000, class_weight="balanced", random_state=42)

    thr, oof_f1 = _oof_best_threshold(model, X, y, random_state=42)
    print(f"\nOOF F1-optimal probability threshold (rough): {thr:.4f}  (OOF F1 score: {oof_f1:.4f})")

    # Detailed CV reports
    n_splits = min(5, y.value_counts().min())
    n_splits = max(2, n_splits)
    skf = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=42)
    fold = 0
    for train_i, test_i in skf.split(X, y):
        fold += 1
        m = LogisticRegression(max_iter=2000, class_weight="balanced", random_state=42)
        X_tr, X_te = X.iloc[train_i], X.iloc[test_i]
        y_tr, y_te = y.iloc[train_i], y.iloc[test_i]
        m.fit(X_tr, y_tr)
        proba_te = m.predict_proba(X_te)
        p_te = proba_te[:, 1] if proba_te.shape[1] > 1 else proba_te[:, 0]
        y_hat = (p_te >= thr).astype(int)
        print(f"\n--- Fold {fold} (holdout {len(y_te)}) ---")
        print("Confusion [actual x pred]:\n", confusion_matrix(y_te, y_hat))
        print(classification_report(y_te, y_hat, digits=3, target_names=["Normal", "At risk"], zero_division=0))

    model.fit(X, y)
    joblib.dump(model, _MODEL_PATH)

    meta = {
        "ml_at_risk_proba_threshold": thr,
        "training_rows": int(len(y)),
        "target_column": y_col,
        "oof_f1_at_threshold": float(oof_f1),
    }
    _THRESHOLD_PATH.write_text(json.dumps(meta, indent=2), encoding="utf-8")

    print(f"\nSaved {_MODEL_PATH}")
    print(f"Saved {_THRESHOLD_PATH}")
    print(f"Deploy threshold: P(at risk) >= {thr:.4f}")


if __name__ == "__main__":
    main()
