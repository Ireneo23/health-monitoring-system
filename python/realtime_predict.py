import argparse
import os
import sys
from pathlib import Path

import joblib
import serial
from serial.tools import list_ports
from typing import Any

from rules import combined_at_risk


def _send_arduino_buzzer_status(ser: serial.Serial, final: int | None) -> None:
    """Send Python's final verdict: ML-based on plausible readings (rules.py); invalid -> buzzer off."""
    if final is None or final == 0:
        ser.write(b"normal\n")
    else:
        ser.write(b"at risk\n")
    ser.flush()


def _list_ports() -> list[Any]:
    return list(list_ports.comports())


def _coerce_bpm_temp(v1: float, v2: float) -> tuple[float, float]:
    """If line is temp,bpm (legacy), swap to bpm,temp for the model."""
    if 20.0 <= v1 <= 45.0 and 40.0 <= v2 <= 220.0:
        return v2, v1
    return v1, v2


def _resolve_port(explicit: str | None) -> str:
    ports = _list_ports()
    devices = [p.device for p in ports]

    if explicit:
        return explicit

    if not devices:
        print("No serial (COM) ports detected. Connect the board, install its USB driver, then retry.")
        sys.exit(1)
    if len(devices) == 1:
        chosen = devices[0]
        print(f"Using serial port: {chosen}")
        return chosen

    print("More than one serial port is available. Choose one with --port (or set SERIAL_PORT):")
    for p in ports:
        print(f"  {p.device}  —  {p.description}")
    print("\nExample: python realtime_predict.py --port COM5")
    sys.exit(1)


def _cli_loop(port: str, baud: int, model: Any) -> None:
    try:
        ser = serial.Serial(port, baud, timeout=1)
    except serial.SerialException as exc:
        print(f"Could not open {port!r}: {exc}")
        ports = _list_ports()
        if ports:
            print("Ports the system reports right now:")
            for p in ports:
                print(f"  {p.device}  —  {p.description}")
        else:
            print("No COM ports are listed. Check the USB cable and driver in Device Manager.")
        sys.exit(1)

    try:
        while True:
            line = ser.readline().decode(errors="replace").strip()
            try:
                a, b = map(float, line.split(","))
            except ValueError:
                continue

            bpm, temp = _coerce_bpm_temp(a, b)
            final, rule_risk, ml_risk, p_risk = combined_at_risk(bpm, temp, model)
            _send_arduino_buzzer_status(ser, final)
            rule_s = "At risk" if rule_risk else "OK"
            ml_s = "At risk" if ml_risk == 1 else "Normal"
            if final is None:
                print(f"BPM:{bpm} Temp:{temp} → INVALID (P(risk)={p_risk:.2f} Rule:{rule_s} ML:{ml_s})")
            elif final == 0:
                print(f"BPM:{bpm} Temp:{temp} → NORMAL (P(risk)={p_risk:.2f} Rule:{rule_s} ML:{ml_s})")
            else:
                print(f"BPM:{bpm} Temp:{temp} → AT RISK (P(risk)={p_risk:.2f} Rule:{rule_s} ML:{ml_s})")
    finally:
        if ser.is_open:
            ser.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Read BPM/temperature from serial and classify with the trained model.")
    parser.add_argument(
        "--port",
        default=os.environ.get("SERIAL_PORT"),
        help="Serial port (e.g. COM5). Default: SERIAL_PORT env, else auto if only one port exists.",
    )
    parser.add_argument("--baud", type=int, default=9600, help="Baud rate (default: 9600).")
    parser.add_argument(
        "--cli",
        action="store_true",
        help="Console output only (no GUI). Default is the dashboard window.",
    )
    args = parser.parse_args()

    port = _resolve_port(args.port)
    model_path = Path(__file__).resolve().parent / "model.pkl"
    model = joblib.load(model_path)

    if args.cli:
        _cli_loop(port, args.baud, model)
        return

    try:
        from dashboard import run_dashboard
    except ImportError as exc:
        print(
            "Could not load the dashboard (is tkinter installed?). Run with --cli for console-only mode.\n"
            f"Import error: {exc}"
        )
        sys.exit(1)

    run_dashboard(port, args.baud, model)


if __name__ == "__main__":
    main()
