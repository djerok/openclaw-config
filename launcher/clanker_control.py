#!/usr/bin/env python3
"""Start/stop/status for the whole clanker stack (gateway + watcher + sweep + status board).
Driven by the Desktop 'Clanker Control.cmd'. Launches the gateway DETACHED + HIDDEN with the
Kimi env (so it survives this window closing and ACP-claude authenticates)."""
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

def start():
    if pid_on_port(PORT_GW):
        print("  gateway already UP (pid %s)" % pid_on_port(PORT_GW))
    else:
        log = open(os.path.join(HOME, ".openclaw", "gateway_fast.log"), "w")
        subprocess.Popen([NODE, ENTRY, "gateway", "--port", str(PORT_GW)], env=kimi_env(),
                         stdout=log, stderr=log, cwd=os.path.join(HOME, ".openclaw"),
                         creationflags=DETACHED, close_fds=True)
        print("  gateway launching (detached + hidden, Kimi env)...")
    for t in AUX_TASKS:
        _task("/Run", "/TN", t)
    print("  watcher + voice-sweep + status board started")
    print("  waiting for the Discord bot to come online (~1-2 min)...", flush=True)
    for _ in range(90):
        if pid_on_port(PORT_GW):
            print("  ==> GATEWAY UP. Bot online. Dashboard: http://127.0.0.1:18789/")
            return
        time.sleep(2)
    print("  gateway still booting — check the #status channel or gateway_fast.log")

def stop():
    for name, port in (("gateway", PORT_GW), ("stop-watcher", PORT_WATCH)):
        pid = pid_on_port(port)
        if pid:
            subprocess.run(["taskkill", "/F", "/PID", pid], capture_output=True)
            print("  %s stopped (pid %s)" % (name, pid))
        else:
            print("  %s not running" % name)
    # prevent the 5-min self-heal + stop aux tasks from relaunching
    _task("/End", "/TN", "OpenClaw Gateway")
    subprocess.run(["powershell", "-NoProfile", "-Command",
                    "Disable-ScheduledTask -TaskName 'OpenClaw Gateway' -ErrorAction SilentlyContinue"],
                   capture_output=True, timeout=20)
    for t in AUX_TASKS:
        _task("/End", "/TN", t)
    print("  self-heal disabled + aux tasks ended. Everything down.")
    print("  (re-enable auto-heal later: schtasks /Change /TN \"OpenClaw Gateway\" /ENABLE)")

def status():
    gw = pid_on_port(PORT_GW); w = pid_on_port(PORT_WATCH)
    print("  Discord bot / gateway : %s" % ("UP  (pid %s)  http://127.0.0.1:18789/" % gw if gw else "DOWN"))
    print("  Stop watcher          : %s" % ("UP  (pid %s)" % w if w else "down"))
    for t in AUX_TASKS:
        r = subprocess.run(["schtasks", "/Query", "/TN", t, "/FO", "LIST"], capture_output=True, text=True)
        st = "registered" if r.returncode == 0 else "MISSING"
        print("  %-22s: %s" % (t, st))

if __name__ == "__main__":
    cmd = (sys.argv[1] if len(sys.argv) > 1 else "status").lower()
    {"start": start, "stop": stop, "status": status}.get(cmd, status)()
