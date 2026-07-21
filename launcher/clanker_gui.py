#!/usr/bin/env python3
"""Clickable control panel for the whole clanker / OpenClaw stack.
Buttons: START / STOP / RESTART / REFRESH. Live status dots for the bot + watcher.
Shells out to clanker_control.py (the tested logic) and streams its output."""
import os, sys, queue, threading, subprocess
import tkinter as tk
from tkinter import scrolledtext, font

HOME = os.path.expanduser("~")
PY = r"C:\Users\ericc\AppData\Local\Programs\Python\Python312\python.exe"
if not os.path.exists(PY):
    PY = "python3"
CTL = os.path.join(HOME, ".openclaw", "clanker_control.py")
CREATE_NO_WINDOW = 0x08000000

sys.path.insert(0, os.path.join(HOME, ".openclaw"))
import clanker_control as ctl  # for pid_on_port + port constants

BG, CARD, FG, MUTE = "#1e1f26", "#2a2c36", "#e8e8ee", "#8b8f9e"
GREEN, RED, AMBER = "#3fb950", "#f0553a", "#d0a020"

msgq = queue.Queue()
busy = False


def worker(action):
    """Run clanker_control.py <action> and stream stdout into the log."""
    global busy
    busy = True
    msgq.put(("buttons", False))
    msgq.put(("log", "\n$ clanker %s\n" % action))
    try:
        p = subprocess.Popen([PY, CTL, action], stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                             text=True, bufsize=1, creationflags=CREATE_NO_WINDOW,
                             cwd=os.path.join(HOME, ".openclaw"))
        for line in p.stdout:
            msgq.put(("log", line.rstrip("\n") + "\n"))
        p.wait()
    except Exception as e:
        msgq.put(("log", "  [error] %s\n" % e))
    busy = False
    msgq.put(("buttons", True))
    msgq.put(("status", None))


def run(action):
    if busy:
        return
    threading.Thread(target=worker, args=(action,), daemon=True).start()


def poll_status():
    """Background: check ports, push a status tuple to the queue."""
    gw = ctl.pid_on_port(ctl.PORT_GW)
    w = ctl.pid_on_port(ctl.PORT_WATCH)
    msgq.put(("dots", (gw, w)))


def kick_status():
    threading.Thread(target=poll_status, daemon=True).start()


# ---------- UI ----------
root = tk.Tk()
root.title("Clanker Control")
root.configure(bg=BG)
root.geometry("560x460")
root.minsize(480, 400)

big = font.Font(family="Segoe UI", size=20, weight="bold")
lbl = font.Font(family="Segoe UI", size=11)
mono = font.Font(family="Consolas", size=9)

tk.Label(root, text="CLANKER", font=big, bg=BG, fg=FG).pack(pady=(16, 2))
tk.Label(root, text="OpenClaw Discord bot + voice + watcher", font=lbl, bg=BG, fg=MUTE).pack()

# status card
card = tk.Frame(root, bg=CARD)
card.pack(fill="x", padx=18, pady=14)
dots = {}
labels = {}
for i, (key, name) in enumerate([("gw", "Discord bot (OpenClaw)"), ("w", "Stop-watcher")]):
    row = tk.Frame(card, bg=CARD)
    row.pack(fill="x", padx=14, pady=6)
    c = tk.Canvas(row, width=16, height=16, bg=CARD, highlightthickness=0)
    d = c.create_oval(3, 3, 13, 13, fill=AMBER, outline="")
    c.pack(side="left")
    dots[key] = (c, d)
    tk.Label(row, text=name, font=lbl, bg=CARD, fg=FG).pack(side="left", padx=(10, 0))
    st = tk.Label(row, text="checking…", font=lbl, bg=CARD, fg=MUTE)
    st.pack(side="right")
    labels[key] = st

# buttons
btnrow = tk.Frame(root, bg=BG)
btnrow.pack(pady=4)


def mkbtn(text, color, action):
    b = tk.Button(btnrow, text=text, width=10, font=lbl, bg=color, fg="#ffffff",
                  activebackground=color, relief="flat", bd=0, padx=6, pady=8,
                  command=lambda: run(action))
    b.pack(side="left", padx=6)
    return b


buttons = [
    mkbtn("▶  Start", GREEN, "start"),
    mkbtn("■  Stop", RED, "stop"),
    mkbtn("⟳  Restart", "#3a6ea5", "restart"),
]
refresh_btn = tk.Button(btnrow, text="↻ Refresh", width=9, font=lbl, bg=CARD, fg=FG,
                        relief="flat", bd=0, padx=6, pady=8, command=kick_status)
refresh_btn.pack(side="left", padx=6)

# log
log = scrolledtext.ScrolledText(root, height=10, bg="#141519", fg="#c8ccd4", font=mono,
                                relief="flat", bd=0, insertbackground=FG, state="disabled")
log.pack(fill="both", expand=True, padx=18, pady=(10, 16))


def set_dot(key, up, label_up, label_down):
    c, d = dots[key]
    c.itemconfig(d, fill=GREEN if up else RED)
    labels[key].config(text=label_up if up else label_down, fg=FG if up else MUTE)


def drain():
    try:
        while True:
            kind, val = msgq.get_nowait()
            if kind == "log":
                log.config(state="normal"); log.insert("end", val); log.see("end"); log.config(state="disabled")
            elif kind == "buttons":
                for b in buttons:
                    b.config(state="normal" if val else "disabled")
            elif kind == "status":
                kick_status()
            elif kind == "dots":
                gw, w = val
                set_dot("gw", bool(gw), "UP  (pid %s)" % gw if gw else "", "DOWN")
                set_dot("w", bool(w), "up  (pid %s)" % w if w else "", "down")
    except queue.Empty:
        pass
    root.after(150, drain)


def autopoll():
    if not busy:
        kick_status()
    root.after(4000, autopoll)


kick_status()
root.after(150, drain)
root.after(4000, autopoll)
root.mainloop()
