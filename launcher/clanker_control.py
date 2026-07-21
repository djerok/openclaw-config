#!/usr/bin/env python3
"""Start/stop/status for the clanker stack. Two granularities:
  full stack : start | stop | restart   (gateway + watcher + voice-sweep + status board)
  gateway    : gw-start | gw-stop | gw-restart   (just the OpenClaw bot daemon)
Driven by the Desktop 'Clanker Control.cmd' / clanker_gui.py. The gateway is launched
DETACHED + HIDDEN with the Kimi env (so it survives the window closing and ACP-claude auths)."""
import json, os, subprocess, sys, time

HOME  = os.path.expanduser("~")
NODE  = r"C:\Program Files\nodejs\node.exe"
ENTRY = os.path.join(HOME, "AppData", "Roaming", "npm", "node_modules", "openclaw", "dist", "index.js")
PORT_GW, PORT_WATCH = 18789, 18790
AUX_TASKS = ["OpenClaw Stop Watcher", "OpenClaw Voice Privacy Sweep", "OpenClaw Status Board"]
DETACHED = 0x00000008 | 0x00000200 | 0x08000000  # DETACHED_PROCESS | NEW_PROCESS_GROUP | NO_WINDOW

def pid_on_port(port):
    try:
        out = subprocess.run(["netstat", "-ano"], capture_output=True, text=True, timeout=15).stdout
        for ln in out.splitlines():
            if (":%d " % port) in ln and "LISTENING" in ln:
                return ln.split()[-1]
    except Exception:
        pass
    return None

def kimi_env():
    env = dict(os.environ)
    try:
        d = json.load(open(os.path.join(HOME, ".claude", "settings.json"), encoding="utf-8"))
        for k, v in d.get("env", {}).items():
            if k.startswith("ANTHROPIC") or k.startswith("CLAUDE_CODE"):
                env[k] = str(v)
    except Exception:
        pass
    env.update({"OPENCLAW_SERVICE_MANAGED_ENV_KEYS": "DISCORD_BOT_TOKEN,KIMI_API_KEY",
                "TMPDIR": os.path.join(HOME, "AppData", "Local", "Temp"),
                "OPENCLAW_GATEWAY_PORT": str(PORT_GW), "OPENCLAW_SERVICE_KIND": "gateway",
                "OPENCLAW_SERVICE_MARKER": "openclaw"})
    return env

def _task(*args):
    subprocess.run(["schtasks", *args], capture_output=True, timeout=20)

# ---- gateway primitives ----
def _launch_gateway():
    if pid_on_port(PORT_GW):
        print("  gateway already UP (pid %s)" % pid_on_port(PORT_GW)); return
    log = open(os.path.join(HOME, ".openclaw", "gateway_fast.log"), "w")
    subprocess.Popen([NODE, ENTRY, "gateway", "--port", str(PORT_GW)], env=kimi_env(),
                     stdout=log, stderr=log, cwd=os.path.join(HOME, ".openclaw"),
                     creationflags=DETACHED, close_fds=True)
    print("  gateway launching (detached + hidden, Kimi env)...")

def _kill_gateway():
    pid = pid_on_port(PORT_GW)
    if pid:
        subprocess.run(["taskkill", "/F", "/PID", pid], capture_output=True)
        print("  gateway stopped (pid %s)" % pid)
    else:
        print("  gateway not running")

def _disable_selfheal():
    _task("/End", "/TN", "OpenClaw Gateway")
    subprocess.run(["powershell", "-NoProfile", "-Command",
                    "Disable-ScheduledTask -TaskName 'OpenClaw Gateway' -ErrorAction SilentlyContinue"],
                   capture_output=True, timeout=20)

def _wait_up(secs=180):
    print("  waiting for the bot to come online...", flush=True)
    for _ in range(secs // 2):
        if pid_on_port(PORT_GW):
            print("  ==> GATEWAY UP (pid %s)  http://127.0.0.1:18789/" % pid_on_port(PORT_GW)); return
        time.sleep(2)
    print("  gateway still booting — check #status or gateway_fast.log")

# ---- full stack ----
def start():
    _launch_gateway()
    for t in AUX_TASKS:
        _task("/Run", "/TN", t)
    print("  watcher + voice-sweep + status board started")
    _wait_up()

def stop():
    _kill_gateway()
    pid = pid_on_port(PORT_WATCH)
    if pid:
        subprocess.run(["taskkill", "/F", "/PID", pid], capture_output=True); print("  stop-watcher stopped (pid %s)" % pid)
    else:
        print("  stop-watcher not running")
    _disable_selfheal()
    for t in AUX_TASKS:
        _task("/End", "/TN", t)
    print("  self-heal disabled + aux tasks ended. Everything down.")
    print("  (re-enable auto-heal later: schtasks /Change /TN \"OpenClaw Gateway\" /ENABLE)")

def restart():
    stop(); time.sleep(1); start()

# ---- gateway only ----
def gw_start():
    _launch_gateway(); _wait_up()

def gw_stop():
    _kill_gateway(); _disable_selfheal()
    print("  gateway only — watcher / voice / status board left running.")

def gw_restart():
    _kill_gateway(); time.sleep(1); _launch_gateway(); _wait_up()

def status():
    gw = pid_on_port(PORT_GW); w = pid_on_port(PORT_WATCH)
    print("  Discord bot / gateway : %s" % ("UP  (pid %s)  http://127.0.0.1:18789/" % gw if gw else "DOWN"))
    print("  Stop watcher          : %s" % ("UP  (pid %s)" % w if w else "down"))
    for t in AUX_TASKS:
        r = subprocess.run(["schtasks", "/Query", "/TN", t, "/FO", "LIST"], capture_output=True, text=True)
        print("  %-22s: %s" % (t, "registered" if r.returncode == 0 else "MISSING"))

CMDS = {"start": start, "stop": stop, "restart": restart,
        "gw-start": gw_start, "gw-stop": gw_stop, "gw-restart": gw_restart,
        "status": status}

if __name__ == "__main__":
    cmd = (sys.argv[1] if len(sys.argv) > 1 else "status").lower()
    CMDS.get(cmd, status)()
