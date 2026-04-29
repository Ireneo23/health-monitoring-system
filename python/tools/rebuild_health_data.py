"""
Maintain health_data.csv: validate rows, compute label_rule / quality_flag, optional sort.

Columns `label_rule` and `quality_flag` are **derived** from `rules.py` (cached for QA).
They may disagree with `label_gt` by design (ML vs human vs threshold rule).

This script does NOT synthesize synthetic training rows or force 50/50 balance.
Ground-truth columns must reflect real assessments (edit label_gt manually if needed).

Run (from `python/`):
      python tools/rebuild_health_data.py
      python tools/rebuild_health_data.py --dry-run
      python tools/rebuild_health_data.py --raw-only   # write only sample_id,bpm,temperature,label_gt
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

_PYTHON_ROOT = Path(__file__).resolve().parent.parent
if str(_PYTHON_ROOT) not in sys.path:
    sys.path.insert(0, str(_PYTHON_ROOT))

from rules import is_at_risk_rule, is_plausible

ROOT = _PYTHON_ROOT
CSV_PATH = ROOT / "health_data.csv"


def _read_rows() -> list[dict[str, str]]:
    if not CSV_PATH.is_file():
        raise FileNotFoundError(CSV_PATH)
    with CSV_PATH.open(newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def _write_rows(rows: list[dict[str, str]], out_path: Path, *, raw_only: bool) -> None:
    if not rows:
        raise ValueError("No rows to write")
    if raw_only:
        fieldnames = ["sample_id", "bpm", "temperature", "label_gt"]
    else:
        fieldnames = [
            "sample_id",
            "bpm",
            "temperature",
            "label_gt",
            "label",
            "label_rule",
            "quality_flag",
        ]
    with out_path.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, lineterminator="\n", extrasaction="ignore")
        w.writeheader()
        for row in rows:
            w.writerow({k: row[k] for k in fieldnames})


def _ensure_int_sample_id(existing: dict[str, str], index_1_based: int) -> str:
    if existing.get("sample_id", "").strip().isdigit():
        return existing["sample_id"].strip()
    return str(index_1_based)


def normalize_and_validate(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    """Recompute label_rule and quality_flag; ensure label aligns with label_gt."""
    out: list[dict[str, str]] = []
    for i, raw in enumerate(rows, start=1):
        sid = _ensure_int_sample_id(raw, i)
        bpm = float(raw["bpm"])
        temp = float(raw["temperature"])
        if "label_gt" in raw:
            gt = str(int(raw["label_gt"]))
        else:
            gt = str(int(raw["label"]))
        lr = str(int(is_at_risk_rule(bpm, temp)))
        qf = str(int(is_plausible(bpm, temp)))
        out.append(
            {
                "sample_id": sid,
                "bpm": str(int(bpm)) if float(bpm) == int(float(bpm)) else str(bpm),
                "temperature": f"{float(temp):.1f}",
                "label_gt": gt,
                "label": gt,
                "label_rule": lr,
                "quality_flag": qf,
            }
        )
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate/normalize health_data.csv (real data only).")
    parser.add_argument("--dry-run", action="store_true", help="Print counts only; do not write CSV")
    parser.add_argument(
        "--raw-only",
        action="store_true",
        help="Write only sample_id,bpm,temperature,label_gt (omit derived label_rule/quality_flag/label)",
    )
    args = parser.parse_args()

    rows = _read_rows()
    normalized = normalize_and_validate(rows)

    if args.dry_run:
        mode = "raw-only" if args.raw_only else "full"
        print(f"Would write {len(normalized)} rows to {CSV_PATH} ({mode})")
        return

    backup = ROOT / "health_data.csv.bak"
    if CSV_PATH.is_file():
        backup.write_bytes(CSV_PATH.read_bytes())
    _write_rows(normalized, CSV_PATH, raw_only=args.raw_only)
    schema = "raw-only" if args.raw_only else "full"
    print(f"Wrote {CSV_PATH} ({len(normalized)} rows, schema={schema}). Backup at {backup}.")


if __name__ == "__main__":
    main()
