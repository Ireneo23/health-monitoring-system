# Python Folder Guide

This folder contains the Python side of the health monitoring project. It stores the training data, trained model, shared rules, live prediction script, and dashboard.

## Main Files

- `health_data.csv` - Dataset of BPM and temperature readings with labels for training and checking the model.
- `train_model.py` - Trains the machine learning model using `health_data.csv`, then saves `model.pkl` and `model_threshold.json`.
- `model.pkl` - Saved trained model used for live prediction.
- `model_threshold.json` - Saved risk probability threshold and model training summary.
- `rules.py` - Shared helper rules for valid sensor ranges, threshold checks, and final ML-based risk decisions.
- `realtime_predict.py` - Reads Arduino serial data, predicts Normal or At risk, and sends the result back to the Arduino.
- `dashboard.py` - Tkinter dashboard that shows live BPM, temperature, and risk status.
- `README.md` - This guide.

## Tool Scripts

- `tools/audit_health_data.py` - Prints a report about the dataset, including labels, duplicates, and rule disagreements.
- `tools/clean_health_data.py` - Optionally removes duplicate or invalid rows from `health_data.csv`.
- `tools/rebuild_health_data.py` - Recomputes helper columns such as `label_rule` and `quality_flag`.

## Typical Use

1. Update or check `health_data.csv`.
2. Run `python train_model.py` to refresh the model.
3. Run `python realtime_predict.py` to use the Arduino and dashboard.
