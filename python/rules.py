# Shared helpers for sensible sensor ranges, fixed threshold rules, and ML-based risk.
# Loads the tuned probability cutoff from model_threshold.json after you run train_model.py.
# Import this from other scripts so all parts of the project agree on the same logic.
"""
Single source of truth for Normal vs At risk (Python).

- Threshold constants match `health_monitoring.ino` for LCD / diagnostics (`is_at_risk_rule`).
- **Final realtime status on plausible readings** uses ML probability vs `model_threshold.json`
  (written by `train_model.py`). Implausible sensor values => no Normal/At risk (None).
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Optional

import pandas as pd

# Thresholds — same meaning as health_monitoring.ino (LCD / rule diagnostics only)
BPM_AT_RISK_LOW = 59  
BPM_AT_RISK_HIGH = 101  
TEMP_AT_RISK_LOW = 35.9 
TEMP_AT_RISK_HIGH = 37.5  

TEMP_VALID_MIN = 20.0
TEMP_VALID_MAX = 45.0
BPM_VALID_MIN = 40.0
BPM_VALID_MAX = 220.0

# Default if train_model.py has not produced model_threshold.json yet (last tuned: 0.55)
ML_AT_RISK_PROBA_THRESHOLD = 0.55

_THRESHOLD_JSON = Path(__file__).resolve().parent / "model_threshold.json"


def _deployed_ml_threshold() -> float:
    if _THRESHOLD_JSON.is_file():
        try:
            data = json.loads(_THRESHOLD_JSON.read_text(encoding="utf-8"))
            return float(data.get("ml_at_risk_proba_threshold", ML_AT_RISK_PROBA_THRESHOLD))
        except (json.JSONDecodeError, ValueError, TypeError):
            pass
    return ML_AT_RISK_PROBA_THRESHOLD


def ml_at_risk_proba_cutoff() -> float:
    """Probability threshold written by train_model.py after OOF tuning."""
    return _deployed_ml_threshold()


def is_plausible(bpm: float, temp: float) -> bool:
    """Sensor ranges — matches Arduino TEMP_VALID and typical pulse range."""
    return (
        math.isfinite(bpm)
        and math.isfinite(temp)
        and TEMP_VALID_MIN < temp < TEMP_VALID_MAX
        and BPM_VALID_MIN <= bpm <= BPM_VALID_MAX
    )


def is_at_risk_rule(bpm: float, temp: float) -> bool:
    """True if (bpm, temp) would be flagged by hardware-style thresholds — only when plausible."""
    if not is_plausible(bpm, temp):
        return False
    if bpm <= BPM_AT_RISK_LOW:
        return True
    if bpm >= BPM_AT_RISK_HIGH:
        return True
    if temp <= TEMP_AT_RISK_LOW:
        return True
    if temp >= TEMP_AT_RISK_HIGH:
        return True
    return False


def _feature_row(bpm: float, temp: float) -> pd.DataFrame:
    return pd.DataFrame([{"bpm": bpm, "temperature": temp}])


def _ml_risk_proba_and_label(model: Any, bpm: float, temp: float) -> tuple[float, int]:
    """P(class=1), and binary label from deployed threshold."""
    cutoff = ml_at_risk_proba_cutoff()
    X = _feature_row(bpm, temp)
    try:
        proba = model.predict_proba(X)[0]
        p_risk = float(proba[1]) if len(proba) > 1 else float(proba[0])
    except (AttributeError, IndexError, ValueError):
        pred = int(model.predict(X)[0])
        p_risk = 1.0 if pred == 1 else 0.0
    ml_label = 1 if p_risk >= cutoff else 0
    return p_risk, ml_label


def combined_at_risk(
    bpm: float, temp: float, model: Any
) -> tuple[Optional[int], bool, int, float]:
    """
    Plausible readings: **final_label follows ML only** (rule is diagnostic only).

    Implausible readings: final_label=None (invalid sensor — do not call Normal/At risk).

    Returns:
        (final_label, rule_at_risk, ml_label, p_risk)
    """
    rule = is_at_risk_rule(bpm, temp)
    p_risk, ml_label = _ml_risk_proba_and_label(model, bpm, temp)

    if not is_plausible(bpm, temp):
        return None, rule, ml_label, p_risk

    # Plausible: decision = ML probability vs tuned threshold from model_threshold.json
    final = 1 if ml_label == 1 else 0
    return final, rule, ml_label, p_risk
