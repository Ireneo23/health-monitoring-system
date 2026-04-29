"""
Optional CSV cleanup: keep plausible rows (quality_flag == 1) and dedupe by sample_id.

Run (from `python/`):
     python tools/clean_health_data.py --dry-run
     python tools/clean_health_data.py --write

Does not regenerate synthetic samples; use `tools/rebuild_health_data.py` for full normalize.
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

_PYTHON_ROOT = Path(__file__).resolve().parent.parent
if str(_PYTHON_ROOT) not in sys.path:
    sys.path.insert(0, str(_PYTHON_ROOT))

import pandas as pd

from rules import is_plausible

CSV_PATH = _PYTHON_ROOT / "health_data.csv"


def load() -> pd.DataFrame:
    return pd.read_csv(CSV_PATH, encoding="utf-8-sig")


def clean(df: pd.DataFrame) -> pd.DataFrame:
    if "sample_id" not in df.columns:
        df = df.copy()
        df.insert(0, "sample_id", range(1, len(df) + 1))
    # Dedupe stable order: first wins
    before = len(df)
    df = df.drop_duplicates(subset=["sample_id"], keep="first")
    if "quality_flag" in df.columns:
        df = df[df["quality_flag"].astype(int) == 1]
    else:
        plausible = df.apply(lambda r: is_plausible(float(r["bpm"]), float(r["temperature"])), axis=1)
        df = df[plausible]
    after = len(df)
    print(f"Dedupe by sample_id: {before} -> {after} rows")
    return df.reset_index(drop=True)


def main() -> None:
    p = argparse.ArgumentParser(description="Dedupe/filter health_data.csv by sample_id + plausible quality.")
    p.add_argument(
        "--write",
        action="store_true",
        help="Persist deduped CSV (default prints dry-run counts only)",
    )
    args = p.parse_args()

    df = load()
    cleaned = clean(df)
    if args.write:
        shutil.copy(CSV_PATH, _PYTHON_ROOT / "health_data.csv.before_clean")
        cleaned.to_csv(CSV_PATH, index=False, encoding="utf-8-sig", lineterminator="\n")
        print(f"Wrote {CSV_PATH} ({len(cleaned)} rows).")
    else:
        print("(dry-run) No write.")


if __name__ == "__main__":
    main()
