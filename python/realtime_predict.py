import argparse
import os
import sys
from pathlib import Path

import joblib
import serial
from serial.tools import list_ports


def _list_ports() -> list[list_ports.ListPortInfo]:
    return list(list_ports.comports())


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


def main() -> None:
    parser = argparse.ArgumentParser(description="Read BPM/temperature from serial and classify with the trained model.")
    parser.add_argument(
        "--port",
        default=os.environ.get("SERIAL_PORT"),
        help="Serial port (e.g. COM5). Default: SERIAL_PORT env, else auto if only one port exists.",
    )
    parser.add_argument("--baud", type=int, default=9600, help="Baud rate (default: 9600).")
    args = parser.parse_args()

    port = _resolve_port(args.port)
    model_path = Path(__file__).resolve().parent / "model.pkl"
    model = joblib.load(model_path)

    try:
        ser = serial.Serial(port, args.baud, timeout=1)
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

    while True:
        line = ser.readline().decode(errors="replace").strip()
        try:
            bpm, temp = map(float, line.split(","))
        except ValueError:
            continue

        prediction = model.predict([[bpm, temp]])[0]

        if prediction == 1:
            print(f"BPM:{bpm} Temp:{temp} → AT RISK")
        else:
            print(f"BPM:{bpm} Temp:{temp} → NORMAL")


if __name__ == "__main__":
    main()
