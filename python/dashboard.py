# Desktop window that shows live BPM, temperature, and risk status from serial data.
# Used together with realtime_predict.py while samples stream from the hardware.
# Built with Tkinter for a simple student-friendly UI.
"""
Tk health monitor UI for realtime_predict. (customtkinter could be swapped in later for
rounder native widgets if you add a requirements.txt.)
"""

from __future__ import annotations

import math
import queue
import random
import threading
from collections import deque
from typing import Any

import serial

from realtime_predict import _coerce_bpm_temp, _send_arduino_buzzer_status
from rules import combined_at_risk

# --- Serial worker ---------------------------------------------------------------------------

# bpm, temp, final (0/1 or None=invalid) — final follows ML on plausible rows; rule_* is diagnostic
Payload = tuple[float, float, int | None, bool, int, float]


def _serial_reader(
    port: str,
    baud: int,
    model: Any,
    out_q: "queue.Queue[Payload]",
    stop: threading.Event,
) -> None:
    ser: serial.Serial | None = None
    try:
        ser = serial.Serial(port, baud, timeout=1)
        while not stop.is_set():
            line = ser.readline().decode(errors="replace").strip()
            try:
                a, b = map(float, line.split(","))
            except ValueError:
                continue
            bpm, temp = _coerce_bpm_temp(a, b)
            final, rule_risk, ml_label, p_risk = combined_at_risk(bpm, temp, model)
            _send_arduino_buzzer_status(ser, final)
            try:
                out_q.put_nowait((bpm, temp, final, rule_risk, ml_label, p_risk))
            except queue.Full:
                try:
                    out_q.get_nowait()
                except queue.Empty:
                    pass
                try:
                    out_q.put_nowait((bpm, temp, final, rule_risk, ml_label, p_risk))
                except queue.Full:
                    pass
    finally:
        if ser is not None and ser.is_open:
            ser.close()


# --- Dashboard -------------------------------------------------------------------------------

POLL_MS = 40
TRACE_LEN = 240
CHART_H = 200


def run_dashboard(port: str, baud: int, model: Any) -> None:
    import tkinter as tk
    from tkinter import font as tkfont

    root = tk.Tk()
    root.title("Health monitor")
    root.geometry("420x560")
    root.resizable(False, False)
    root.configure(bg="#C8E8EC")

    card_bg = "#E6F4F6"
    fg_dark = "#1a1a1a"
    accent = "#0d0d0d"

    main = tk.Frame(root, bg="#C8E8EC")
    main.pack(fill=tk.BOTH, expand=True, padx=18, pady=18)

    card = tk.Frame(main, bg=card_bg, highlightbackground="#B0D8DE", highlightthickness=1)
    card.pack(fill=tk.BOTH, expand=True)

    head = tk.Frame(card, bg=card_bg)
    head.pack(fill=tk.X, padx=16, pady=(16, 8))

    title_font = tkfont.Font(family="Segoe UI", size=14, weight="bold")
    tk.Label(head, text="Health Monitoring System", bg=card_bg, fg=fg_dark, font=title_font).pack(side=tk.LEFT)

    metrics = tk.Frame(card, bg=card_bg)
    metrics.pack(fill=tk.X, padx=16, pady=(0, 6))

    num_font = tkfont.Font(family="Segoe UI", size=36, weight="bold")
    unit_font = tkfont.Font(family="Segoe UI", size=14)
    small_font = tkfont.Font(family="Segoe UI", size=12)

    row1 = tk.Frame(metrics, bg=card_bg)
    row1.pack(anchor=tk.W)

    bpm_num = tk.Label(row1, text="—", bg=card_bg, fg=fg_dark, font=num_font, width=3, anchor=tk.W)
    bpm_num.pack(side=tk.LEFT)
    tk.Label(row1, text="bpm", bg=card_bg, fg="#5c5c5c", font=unit_font).pack(side=tk.LEFT, padx=(4, 0), pady=(12, 0))

    temp_frame = tk.Frame(row1, bg=card_bg)
    temp_frame.pack(side=tk.LEFT, padx=(24, 0))
    thermo = tk.Label(temp_frame, text="T", bg=card_bg, fg=fg_dark, font=title_font, width=1)
    thermo.pack(side=tk.LEFT, padx=(0, 2))
    temp_num = tk.Label(temp_frame, text="— °C", bg=card_bg, fg=fg_dark, font=num_font, anchor=tk.W)
    temp_num.pack(side=tk.LEFT)

    badge = tk.Label(
        card,
        text="  Waiting for data  ",
        bg="#E8E8E8",
        fg="#444",
        font=small_font,
        padx=10,
        pady=4,
    )
    badge.pack(anchor=tk.W, padx=16, pady=(0, 4))

    detail_font = tkfont.Font(family="Segoe UI", size=9)
    detail = tk.Label(
        card,
        text="",
        bg=card_bg,
        fg="#5c5c5c",
        font=detail_font,
        anchor=tk.W,
        justify=tk.LEFT,
    )
    detail.pack(anchor=tk.W, padx=16, pady=(0, 8))

    chart_outer = tk.Frame(card, bg=card_bg)
    chart_outer.pack(fill=tk.BOTH, expand=True, padx=12, pady=(0, 16))

    c_w = 360
    c_h = CHART_H + 36
    cv = tk.Canvas(
        chart_outer,
        width=c_w,
        height=c_h,
        bg="#DCEEF0",
        highlightthickness=0,
    )
    cv.pack()

    out_q: queue.Queue[Payload] = queue.Queue(maxsize=4)
    stop = threading.Event()
    thread = threading.Thread(
        target=_serial_reader,
        args=(port, baud, model, out_q, stop),
        name="SerialReader",
        daemon=True,
    )
    thread.start()

    trace_a: deque[float] = deque([0.0] * TRACE_LEN, maxlen=TRACE_LEN)
    trace_b: deque[float] = deque([0.0] * TRACE_LEN, maxlen=TRACE_LEN)
    tick = [0]
    bpm_f = [70.0]
    smooth_b = [0.0]

    def on_close() -> None:
        stop.set()
        thread.join(timeout=2.0)
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_close)

    def poll() -> None:
        if not stop.is_set():
            root.after(POLL_MS, poll)

        while True:
            try:
                item = out_q.get_nowait()
            except queue.Empty:
                break
            b, t, p_final, rule_risk, ml_label, p_risk = item
            bpm_f[0] = b
            bpm_num.config(text=str(int(round(b))))
            temp_num.config(text=f"{t:.1f} °C")
            rule_txt = "At risk" if rule_risk else "OK"
            ml_txt = "At risk" if ml_label == 1 else "Normal"
            detail.config(text=f"Rule: {rule_txt}  |  ML: {ml_txt}  |  P(risk)={p_risk:.2f}")
            if p_final is None:
                badge.config(
                    text="  Invalid reading  ",
                    bg="#D8D8D8",
                    fg="#333",
                )
            elif p_final == 0:
                badge.config(text="  Normal  ", bg="#B8E6C8", fg="#0d4a1f")
            else:
                badge.config(text="  At risk  ", bg="#F5B8B8", fg="#5c0a0a")

        bpm = max(40.0, min(220.0, bpm_f[0]))
        tick[0] += 1
        t0 = tick[0]
        samples_per_min = 60000.0 / POLL_MS
        frames_per_beat = max(3.0, samples_per_min / bpm)
        spike = (t0 % int(frames_per_beat)) == 0
        noise = random.uniform(-0.06, 0.06)
        a_y = noise + (0.82 if spike else 0.0)
        smooth_b[0] = 0.75 * smooth_b[0] + 0.25 * a_y
        b_y = smooth_b[0] * 0.55 + 0.08 * math.sin(t0 * 0.11)
        trace_a.append(a_y)
        trace_b.append(b_y)

        cv.delete("all")
        w = c_w
        h = c_h
        x_scrub = int(w * 0.7)
        hl_w = 44
        cv.create_rectangle(
            x_scrub - hl_w // 2,
            4,
            x_scrub + hl_w // 2,
            h - 4,
            fill="white",
            outline="",
        )
        graph_top = 28
        graph_bot = h - 6
        mid_y = (graph_top + graph_bot) / 2
        h_span = (graph_bot - graph_top) / 2.0 - 4

        def line_from_deque(d: deque[float], y_offset: float, amp: float) -> None:
            pts: list[tuple[int, int]] = []
            n = len(d)
            if n < 2:
                return
            for i, v in enumerate(d):
                x = int(i * (w - 1) / (n - 1))
                yv = y_offset - v * amp * h_span
                yv = max(graph_top + 2, min(graph_bot - 2, yv))
                pts.append((x, int(yv)))
            for j in range(1, len(pts)):
                cv.create_line(pts[j - 1][0], pts[j - 1][1], pts[j][0], pts[j][1], fill=accent, width=2, capstyle=tk.ROUND, smooth=True)

        line_from_deque(trace_b, mid_y + 22, 0.5)
        line_from_deque(trace_a, mid_y - 18, 1.0)

        cv.create_line(x_scrub, graph_top, x_scrub, graph_bot, fill=fg_dark, width=1, dash=(4, 4))

        raw_bpm = bpm_f[0]
        if math.isfinite(raw_bpm):
            tip = f"{int(round(raw_bpm))} bpm"
        else:
            tip = "— bpm"
        tw = 56
        cv.create_rectangle(
            x_scrub - tw // 2,
            2,
            x_scrub + tw // 2,
            22,
            fill="white",
            outline="#d0d0d0",
        )
        cv.create_text(x_scrub, 12, text=tip, fill=fg_dark, font=(tkfont.nametofont("TkDefaultFont").actual()["family"], 8))

    root.after(POLL_MS, poll)
    root.mainloop()
