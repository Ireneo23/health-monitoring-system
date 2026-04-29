# Health dataset and ML

## `health_data.csv` columns

| Column | Role |
|--------|------|
| `sample_id`, `bpm`, `temperature` | Raw measurements and row id |
| `label_gt` | Ground-truth label (0 = Normal, 1 = At risk) — edit for real assessments |
| `label` | Mirrors `label_gt` after `tools/rebuild_health_data.py` (full schema only) |
| `label_rule` | **Derived** — threshold rule from [`rules.py`](rules.py); may disagree with `label_gt` |
| `quality_flag` | **Derived** — plausible sensor range per [`rules.py`](rules.py) |

Training uses **`bpm` and `temperature` only** as features; `label_rule` is not used as a target or feature in [`train_model.py`](train_model.py).

## Scripts

From the `python/` folder:

- `python tools/rebuild_health_data.py` — normalize CSV, recompute derived columns (default **full** schema).
- `python tools/rebuild_health_data.py --raw-only` — write only `sample_id,bpm,temperature,label_gt`.
- `python tools/audit_health_data.py` — QA: balance, duplicates, label vs rule disagreement.
- `python train_model.py` — train model, write `model.pkl` and `model_threshold.json`.
- `python realtime_predict.py` — serial classify + Arduino buzzer feedback (`--cli` for console-only; default opens GUI via `dashboard.py`).
