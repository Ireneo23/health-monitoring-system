# Print a quick quality report for health_data.csv: counts, duplicates, and label vs rule gaps.
# Run from the python folder to inspect data before training without changing the file.
# Helps catch messy labels or repeated samples early.
"""
Audit script for health_data.csv: distributions, duplicates, rule vs label disagreement.

Run (from `python/`): python tools/audit_health_data.py
"""
from __future__ import annotations

import sys
from pathlib import Path

_PYTHON_ROOT = Path(__file__).resolve().parent.parent
if str(_PYTHON_ROOT) not in sys.path:
    sys.path.insert(0, str(_PYTHON_ROOT))

import pandas as pd

from rules import is_at_risk_rule, is_plausible

_HEALTH_PATH = _PYTHON_ROOT / "health_data.csv"


def main() -> None:
    df = pd.read_csv(_HEALTH_PATH, encoding="utf-8-sig")
    n = len(df)

    label_col = "label_gt" if "label_gt" in df.columns else "label"
    df["label_rule"] = df.apply(
        lambda r: int(is_at_risk_rule(float(r["bpm"]), float(r["temperature"]))), axis=1
    )
    df["quality_flag"] = df.apply(
        lambda r: int(is_plausible(float(r["bpm"]), float(r["temperature"]))), axis=1
    )

    disagree = df[df[label_col] != df["label_rule"]]
    dup_mask = df.duplicated(subset=["bpm", "temperature"], keep=False)

    print(f"File: {_HEALTH_PATH}")
    print(f"Rows: {n}")
    print(f"Label column used: {label_col}")
    print()
    print("--- Class balance ---")
    print(df[label_col].value_counts().sort_index())
    print()
    print("--- Plausibility (quality_flag) ---")
    print(df["quality_flag"].value_counts().sort_index())
    print()
    print("--- label vs threshold rule (label_rule) disagreement ---")
    print(f"Count: {len(disagree)}")
    if len(disagree):
        print(disagree[["bpm", "temperature", label_col, "label_rule"]].to_string(index=False))
    print()
    print("--- Duplicate (bpm, temperature) pairs ---")
    print(f"Rows in duplicate pairs: {int(dup_mask.sum())}")
    if dup_mask.any():
        print(df[dup_mask].sort_values(["bpm", "temperature"]).to_string(index=False))
    print()
    print("--- BPM / temperature ranges ---")
    print(f"bpm: min={df['bpm'].min()} max={df['bpm'].max()}")
    print(f"temperature: min={df['temperature'].min()} max={df['temperature'].max()}")


if __name__ == "__main__":
    main()
