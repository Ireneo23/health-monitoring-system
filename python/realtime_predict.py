# Read BPM and temperature from the Arduino over the serial port.
# Use the trained model and shared rules to decide normal vs at risk, then send that back to the board.
# Opens the dashboard by default; add --cli for console-only mode.

import argparse
import os
import sys
from pathlib import Path

import joblib
import serial
from serial.tools import list_ports
from typing import Any

from rules import combined_at_risk

# bpm, temp, final (0/1 or None=invalid) — final follows ML on plausible rows; rule is diagnostic
Payload = tuple[float, float, int | None, bool, int, float]

# Exact bytes the Arduino expects (lowercase, no leading/trailing spaces, LF only).
CMD_ARDUINO_NORMAL = b"normal\n"
CMD_ARDUINO_AT_RISK = b"at risk\n"


# This checks buzzer command bytes once at import time using asserts.
# It helps catch typos or wrong spacing before anything writes to the board.

def _assert_strict_arduino_cmds() -> None:
    for cmd in (CMD_ARDUINO_NORMAL, CMD_ARDUINO_AT_RISK):
        assert cmd.endswith(b"\n"), cmd
        line = cmd[:-1]
        assert line == line.lower(), cmd
        assert line == line.strip(), cmd
        assert not line.startswith(b" "), cmd
        assert not line.endswith(b" "), cmd


_assert_strict_arduino_cmds()


# This sends the short text line the Arduino expects for buzzer on or off.
# Normal or invalid readings map to the calm command; at-risk maps to alarm.

def send_arduino_buzzer_status(ser: serial.Serial, final: int | None) -> None:
    """Send Python's final verdict: ML-based on plausible readings (rules.py); invalid -> buzzer off."""
    if final is None or final == 0:
        ser.write(CMD_ARDUINO_NORMAL)
    else:
        ser.write(CMD_ARDUINO_AT_RISK)
    ser.flush()


# This asks the OS for every USB serial device name right now.
# Other helpers use it to print hints when picking or fixing the COM port.

def _list_ports() -> list[Any]:
    return list(list_ports.comports())


# This fixes older wires that sent temperature before BPM instead of BPM first.
# When values clearly look like temp then pulse, it swaps them for the model.

def coerce_bpm_temp(v1: float, v2: float) -> tuple[float, float]:
    """If line is temp,bpm (legacy), swap to bpm,temp for the model."""
    if 20.0 <= v1 <= 45.0 and 40.0 <= v2 <= 220.0:
        return v2, v1
    return v1, v2


# This picks which COM port to open when you did not pass --port.
# It exits with clear prints if no ports exist or several need a manual choice.

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


# This reads one comma-separated line and scores BPM plus temperature together.
# It tells the board the outcome and returns numbers for the UI or prints.

def read_and_classify(ser: serial.Serial, model: Any) -> Payload | None:
    """Read one line, parse ``bpm,temp``, classify, send buzzer command. Return None if unparseable."""
    line = ser.readline().decode(errors="replace").strip()
    try:
        a, b = map(float, line.split(","))
    except ValueError:
        return None
    bpm, temp = coerce_bpm_temp(a, b)
    final, rule_risk, ml_label, p_risk = combined_at_risk(bpm, temp, model)
    send_arduino_buzzer_status(ser, final)
    return (bpm, temp, final, rule_risk, ml_label, p_risk)


# This opens serial once and loops forever printing each classified sample.
# Errors opening the port show nearby ports so you can fix wiring or drivers.

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
            item = read_and_classify(ser, model)
            if item is None:
                continue
            bpm, temp, final, rule_risk, ml_risk, p_risk = item
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


# This parses command-line flags, loads the saved model, and starts work.
# You either get the dashboard window or the print-only loop from --cli.

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
