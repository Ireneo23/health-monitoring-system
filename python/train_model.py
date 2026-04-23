from pathlib import Path

import pandas as pd
from sklearn.linear_model import LogisticRegression
import joblib

_DATA_DIR = Path(__file__).resolve().parent
_health_path = _DATA_DIR / "health_data.csv"
# Excel workbooks are ZIP files starting with PK; plain CSV is text.
_is_excel = False
if _health_path.is_file():
    with _health_path.open("rb") as _f:
        _is_excel = _f.read(2) == b"PK"
if _is_excel:
    data = pd.read_excel(_health_path, engine="openpyxl")
else:
    data = pd.read_csv(_health_path, encoding="utf-8-sig")

X = data[['bpm', 'temperature']]
y = data['label']

model = LogisticRegression()
model.fit(X, y)

joblib.dump(model, _DATA_DIR / "model.pkl")

print("Model trained")