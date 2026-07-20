# OpenClaw + Kimi + Discord + ACP Harness — Full Setup Guide

This is the end-to-end guide to rebuild the "clanker" Discord bot from scratch: an
[OpenClaw](https://www.npmjs.com/package/openclaw) gateway whose chat brain is **Kimi K3**, reachable
from **Discord** (through a China-blocked network via a VPN + proxy bridge), and able to spawn real
**coding agents over ACP** (Claude Code and/or Codex).

Companion files in this folder:
- **`openclaw.template.json`** — a redacted copy of the live `openclaw.json` (all secrets → `<PLACEHOLDER>`). Use it as your starting config.
- **`COMMANDS.md`** — start/stop/restart cheat-sheet for the gateway + status board.
- **`CHANGELOG.md`** — the dated history of every change (how we actually got here).

> **Secrets rule:** never commit real tokens/keys. Everything below uses placeholders like
> `<DISCORD_BOT_TOKEN>`. The real values live only in `~/.openclaw/.env` and `~/.openclaw/openclaw.json`
> on the machine.

---

## 0. Architecture (the whole pipeline, one hop at a time)

```
You type in Discord
  → Discord servers
  → UniClash VPN            (HTTP/SOCKS proxy on 127.0.0.1:7993 — this network blocks Discord + OpenAI/Anthropic direct)
  → HTTP→SOCKS5h bridge     (127.0.0.1:7994 — because OpenClaw speaks ONLY HTTP proxy, not SOCKS)
  → OpenClaw gateway (node) (Windows Scheduled Task, loopback API on 127.0.0.1:18789)
       │
       ├─ default @clanker chat  → Kimi brain plugin → https://api.kimi.com/coding/   (Kimi K3)
       │
       └─ /acp (a coding agent)  → acpx plugin → an ACP wrapper → a coding-agent CLI:
              • agentId "claude" → @agentclientprotocol/claude-agent-acp → `claude` CLI → api.anthropic.com
              • agentId "codex"  → @zed-industries/codex-acp           → `codex` CLI → api.openai.com
  → response streams back up the same chain → bot posts in your channel
```

**Why two proxy hops for one proxy:** UniClash (`7993`) resolves + tunnels correctly as **SOCKS5h**
(proxy-side DNS beats this network's DNS poisoning). But OpenClaw only supports **HTTP** proxies
("SOCKS and PAC proxy URLs are not supported"). So a tiny local bridge (`7994`) accepts HTTP-proxy
`CONNECT` and forwards over SOCKS5h to UniClash. Discord traffic goes `OpenClaw → 7994 → 7993 → Discord`.
Codex/OpenAI traffic goes directly `→ 7993` via the `HTTPS_PROXY` env var.

---

## 1. Prerequisites

| Need | Notes |
|---|---|
| **Node.js** | v25.9.0 was used. `node -v` must work in a plain shell. |
| **Python 3** | On this PC **use `python3`, never bare `python`** (the bare `python` is a 0-byte WindowsApps stub that hangs). |
| **UniClash** (or any VPN) | Provides the `127.0.0.1:7993` proxy. Needed because Discord/OpenAI/Anthropic are blocked direct. |
| **A Discord bot** | Create at https://discord.com/developers → Bot → copy the token. Enable **Message Content Intent**. Invite it to your server. |
| **Kimi coding key** | From **kimi.com/code** (NOT moonshot.ai — that returns 401 against the coding endpoint). |
| **(optional) OpenAI API key** | `sk-proj-…` — only if you want the **Codex** ACP backend. |
| **(optional) Anthropic** | For the **Claude Code** ACP backend (OAuth via `claude` CLI login, or an API key). |

Config lives in two homes:
- **`C:\Users\ericc\.openclaw\`** — OpenClaw config, secrets, bridge, ACP wrappers, workspace.
- **`C:\Users\ericc\.claude\`** — the `claude` CLI's own config (only relevant for the Claude ACP backend).

---

## 2. Install OpenClaw

```powershell
npm install -g openclaw            # installs to %APPDATA%\npm\node_modules\openclaw
openclaw --version                 # confirm it runs
```

Run the first-time wizard (creates `~/.openclaw/openclaw.json` + `.env`):
```powershell
openclaw            # or: openclaw doctor
```

> **Known wall (important):** this install has a *stale-dist* bug — the long-running gateway executes
> **old compiled bytecode** for any hand-edited `dist/*.js` file, even though the file on disk is
> correct. **Config changes (openclaw.json / AGENTS.md) take effect; hand-patched code does not.** If a
> code-level feature "won't turn on," this is why. A clean `npm` reinstall is the only known reset.
> (Full detail in `CHANGELOG.md` under "stale Node compile cache DISPROVEN".)

---

## 3. Kimi K3 as the chat brain

1. Get your key from **kimi.com/code** (a coding-subscription key, e.g. tier "Allegretto" → 1M context).
2. Put it in `~/.openclaw/.env` (see Part 5) as `KIMI_API_KEY`.
3. In `openclaw.json` the Kimi plugin points at the coding endpoint and declares the models:
   ```jsonc
   "plugins": { "entries": { "kimi": { "enabled": true, "config": {} } } },
   "models": {
     "...": "baseUrl -> https://api.kimi.com/coding/  (NOT moonshot; moonshot 401s)",
     "model": "kimi/kimi-for-coding-highspeed"        // the default brain model
   }
   ```
   Real model IDs served: `kimi-for-coding` (K2.7 Coding) and `kimi-for-coding-highspeed`.

> **Gotcha:** the Kimi endpoint **echoes any model id** — asking for "fable" or "opus" still serves
> Kimi. So a `/model fable` that "works" is Kimi wearing a label, not real Fable. (This is separate
> from the ACP agents, which really do run Claude/Codex — see Part 6.)

---

## 4. Discord + the proxy bridge (the part that makes Discord reachable)

Because this network blocks Discord directly, all Discord traffic is proxied. OpenClaw only speaks
HTTP-proxy, so we run a small bridge in front of UniClash's SOCKS5h port.

### 4a. The bridge

`~/.openclaw/discord_socks_bridge.py` — an HTTP-proxy → SOCKS5h bridge. Listens on `127.0.0.1:7994`,
forwards every `CONNECT` over SOCKS5h to UniClash on `127.0.0.1:7993` (so hostnames resolve at
UniClash, beating the local DNS poisoning). Key hardening it carries:
- `SO_EXCLUSIVEADDRUSE` singleton (Windows lets multiple procs share a port otherwise).
- `pythonw`-safe (redirects stderr to `bridge.log`, since `pythonw` has no console).
- **`TCP_NODELAY` + `SO_KEEPALIVE`** on both tunnel sockets — without `TCP_NODELAY`, Nagle delays
  Discord's tiny websocket heartbeats and Discord drops the gateway ("heartbeat ACK timeout").

Launcher `~/.openclaw/start_bridge.ps1` kills any old bridge and starts a fresh hidden `pythonw`
instance, then verifies `Test-NetConnection 127.0.0.1 -Port 7994`.

Autostart at logon: a shortcut/VBS in the Startup folder (`openclaw-discord-bridge.vbs`) launches it
hidden. **The bridge must be up BEFORE the gateway**, or the gateway flaps in reconnect backoff.

### 4b. Point OpenClaw at the bridge

In `openclaw.json`:
```jsonc
"proxy": { "proxyUrl": "http://127.0.0.1:7994" },
"channels": { "discord": {
    "enabled": true,
    "token": "<DISCORD_BOT_TOKEN>",          // or via .env; see Part 5
    "proxy": "http://127.0.0.1:7994",         // Discord REST + gateway websocket both use the bridge
    "allowFrom": ["<YOUR_DISCORD_USER_ID>"],  // who may command the bot
    "execApprovals": { ... },                 // see Part 7
    "threadBindings": { ... },
    "groupPolicy": { ... }
}}
```

### 4c. Codex/OpenAI proxy (separate path)

The Codex ACP backend reaches OpenAI directly through UniClash (not the bridge), via env vars set in
the gateway environment:
```
HTTPS_PROXY=http://127.0.0.1:7993
HTTP_PROXY=http://127.0.0.1:7993
NO_PROXY=localhost,127.0.0.1,::1
```
UniClash's rule group `CATEGORY-AI-!CN` routes the OpenAI/Anthropic/Google-AI domains out through the
VPN so they resolve and connect.

### 4d. Sanity check the bridge
```powershell
(Test-NetConnection 127.0.0.1 -Port 7994).TcpTestSucceeded   # bridge up?
# through the bridge, discord.com should answer:
curl.exe -x http://127.0.0.1:7994 -s -o NUL -w "%{http_code}" https://discord.com
```

---

## 5. `~/.openclaw/.env` (secrets)

This file holds the two secrets OpenClaw injects as managed env keys. **Never commit it.**

```dotenv
# ~/.openclaw/.env
DISCORD_BOT_TOKEN=<your Discord bot token from the Developer Portal>
KIMI_API_KEY=<your kimi.com/code key — sk-...>
```

`gateway.cmd` declares these as managed keys so the service picks them up:
```
set "OPENCLAW_SERVICE_MANAGED_ENV_KEYS=DISCORD_BOT_TOKEN,KIMI_API_KEY"
```

Other secrets that live **outside** `.env` (each in its own home — see the file map at the end):
- Gateway control token → `openclaw.json` (`gateway.auth.token`)
- Exec-approvals socket token → `~/.openclaw/exec-approvals.json`
- OpenAI key (Codex backend) → `~/.openclaw/acpx/codex-home/auth.json` (`OPENAI_API_KEY`)
- Anthropic OAuth (Claude backend) → `~/.claude/.credentials.json`

## 6. `openclaw.json` — section by section

Start from `openclaw.template.json` in this folder (it's the live config with secrets stripped). The
top-level keys and what they do:

| Key | What it controls |
|---|---|
| `env` | Managed env passed to the gateway (proxy vars, model defaults). |
| `models` | Model registry — the Kimi coding models + the default brain `model`. |
| `agents` | Agent defaults (system prompt roots, tool policy). |
| `plugins` | **Which plugins load** — `allow: ["kimi","acpx","discord","memory-core"]` + per-plugin `entries`. This is where ACP is turned on (Part 7). |
| `gateway` | `mode: local`, bind `127.0.0.1:18789`, and `gateway.auth.token` (control-API secret). |
| `session` | Session store location + policy. |
| `tools` | Tool allow/deny profiles (e.g. `tools.deny: [write, edit, apply_patch]` as a guardrail). |
| `skills` | The 51 bundled skills' on/off flags (`skills.entries.<name>.enabled`). |
| `channels` | **Discord** config (Part 4b) — token, proxy, allowFrom, execApprovals, threadBindings. |
| `proxy` | `proxyUrl: http://127.0.0.1:7994` — the bridge, used for all proxied HTTP. |
| `messages` | Chat behaviour — `groupChat.mentionPatterns` (wake-words like `clanker`/`claw`), status reactions, queue mode. |

Edit this file live — **config changes are re-read by the gateway** (unlike code patches). Validate
before restarting: `openclaw doctor` catches schema errors (a bad value silently kills the gateway).

---

## 7. The ACP harness (acpx) — real coding agents over Discord

ACP = **Agent Client Protocol**, a standard JSON-RPC-over-stdio protocol. OpenClaw's **acpx** plugin is
an ACP *client*; it spawns a coding-agent CLI wrapped as an ACP *server* and talks to it. Two backends
are wired: **Claude Code** and **Codex** — both installed, interchangeable, chosen by `agentId`.

### 7a. Turn the plugin on (`openclaw.json`)
```jsonc
"plugins": { "allow": ["kimi","acpx","discord","memory-core"],
  "entries": {
    "acpx": {
      "enabled": true,
      "config": {
        "permissionMode": "approve-reads",        // auto-allow reads, prompt for writes/exec
        "nonInteractivePermissions": "deny",       // if no human to approve → deny
        "timeoutSeconds": 120
      }
    }
}}
```

### 7b. Install the two ACP adapters
acpx keeps its own npm project under `~/.openclaw/npm/projects/openclaw-acpx-<hash>/`. The adapters
land there automatically on first spawn (or `openclaw` installs them):
- `@agentclientprotocol/claude-agent-acp` (Claude backend) — spawns the `claude` CLI.
- `@zed-industries/codex-acp` (Codex backend) — spawns the `codex` CLI.

Both CLIs must be installed globally and runnable: `claude --version`, `codex --version`.

### 7c. The wrappers (`~/.openclaw/acpx/`)
acpx generates one wrapper per backend; you don't hand-write these, but know they exist:
- `claude-agent-acp-wrapper.mjs` — launches the Claude adapter. (Note: it writes **no** stderr log.)
- `codex-acp-wrapper.mjs` — launches the Codex adapter; logs to `codex-acp-wrapper.stderr.*`.

Each spawn gets a **process lease** (`process-leases` store, cap 4096) tagging it with a `leaseId`,
`sessionKey`, and `rootPid` so OpenClaw can supervise + clean it up.

### 7d. Claude Code backend — config + auth
The Claude backend runs the `claude` CLI, which uses **its own** config home `~/.claude/`:
- **Model** → `~/.claude/settings.json` → `"model": "fable"` (this is what makes it Claude Fable 5).
- **Auth** → `~/.claude/.credentials.json` (Anthropic OAuth — set up by `claude` login / `switch-claude`).
- **Endpoint** → `ANTHROPIC_BASE_URL` env. Unset/`https://api.anthropic.com` = real Anthropic.
- Instructions → `~/.claude/CLAUDE.md` + the workspace `AGENTS.md`.

> **ToS note:** running the `claude` CLI on an Anthropic **subscription** inside a third-party harness
> (acpx) is a gray area. To be clean, point `ANTHROPIC_BASE_URL` at Kimi/an API key instead of the sub.

### 7e. Codex backend — config + auth
The Codex backend runs the `codex` CLI with a dedicated home `~/.openclaw/acpx/codex-home/`:
- `config.toml` → `model = "gpt-5.6-terra"`, `model_reasoning_effort = "xhigh"`, trusted project list.
- `auth.json` → `OPENAI_API_KEY = "sk-proj-…"` (this is what's billed — a **pay-per-token API key**, not a ChatGPT sub).
- Reaches OpenAI via the `HTTPS_PROXY=127.0.0.1:7993` env (Part 4c).

### 7f. How a session is created + which backend
- Spawn from Discord / AGENTS.md: `sessions_spawn({ runtime: "acp", agentId: "claude", ... })`
  (or `agentId: "codex"`). The `agentId` picks the wrapper.
- Each session gets key **`agent:<agentId>:acp:<uuid>`** (random UUID, **not** the channel id) stored
  in `~/.openclaw/workspace/state/sessions/*.json`.
- **Multiple sessions are supported** (up to the 4096 lease cap) — a channel/thread binds to one
  ongoing session, but you can spawn more; each is a separate CLI process with its own context.
- Claude session transcripts land in `~/.claude/projects/C--Users-ericc--openclaw-workspace/<id>.jsonl`;
  Codex sessions in `~/.openclaw/acpx/codex-home/sessions/…`.

### 7g. Verify a backend end-to-end (no Discord needed)
Drive the wrapper directly with a minimal ACP client (`initialize → session/new → session/prompt`).
A throwaway probe is enough — if you get a `stopReason: end_turn` with model text back, the backend
works. (This is how Codex was confirmed hitting real OpenAI, and Claude confirmed as the live bot.)

---

## 8. Exec approvals (human-in-the-loop for risky actions)

When an agent wants to do something guarded (run a shell command, write a file), OpenClaw posts an
**approval card** and waits for a human to Allow/Deny.

`openclaw.json → channels.discord.execApprovals`:
```jsonc
"execApprovals": {
  "enabled": true,
  "approvers": ["<YOUR_DISCORD_USER_ID>"],   // who may approve
  "cleanupAfterResolve": true,
  "target": "channel"                         // where the card posts: "dm" | "channel" | "both"
}
```
> **Gotcha:** `target` accepts only `dm` / `channel` / `both`. Setting `"origin"` (an internal name)
> **crashes the gateway** with a schema error → bot goes offline. Always `openclaw doctor` after editing.

The socket token for the approvals channel lives in **`~/.openclaw/exec-approvals.json`** (secret).

Belt-and-suspenders guardrails (in `openclaw.json → tools`):
- `tools.deny: ["write","edit","apply_patch"]` — hard-blocks direct file mutation tools.
- Run `exec-policy preset cautious` before any unattended session (otherwise shell `del`/`Remove-Item`
  can run unprompted when exec is set to full-auto).

---

## 9. Voice (speech-to-text)

Discord voice notes → local Whisper transcription → the brain. Pieces:
- **whisper.cpp** built with GPU (cuBLAS) support; model `large-v3-turbo-q8_0`, `-l en`.
- A **load-aware router** (`whisper-cli.cmd` + `router.py`) picks GPU vs CPU model by current load.
- Wired as the **primary** transcriber (Discord's native transcript is the last-resort fallback).
- Wake-word gate: only acts on `openclaw`/`claw`/`clanker`/… ; reacts 👂 (heard keyword) / 👄 (heard, no keyword).

> **Status:** the ffmpeg-resolution fix voice needs is a **code** patch, so it's caught by the
> stale-dist wall (Part 2). Voice transcription may not be fully live until a clean reinstall. See
> `CHANGELOG.md` for the exact ffmpeg + earmouth details.

---

## 10. Running it (Windows Scheduled Tasks)

The gateway is **not** run by hand — it's a Scheduled Task so it survives logon and self-heals.

- **`~/.openclaw/gateway.cmd`** — sets env (managed keys, `TMPDIR`, port 18789, `NODE_DISABLE_COMPILE_CACHE=1`)
  then runs `node …\openclaw\dist\index.js gateway --port 18789`.
- **`~/.openclaw/gateway.vbs`** — hidden launcher the task invokes.
- Task **"OpenClaw Gateway"** runs the vbs at logon.
- Task **"OpenClaw Status Board"** runs `status_board.py` — a model-free daemon that edits a `#status`
  Discord webhook every 5s (live gateway up/down, Claude/Kimi usage via `usage_status.py`). It keeps
  working even when the gateway is down.

Start / stop / restart — see **`COMMANDS.md`**. The essentials:
```powershell
# start bridge FIRST, then the gateway
powershell -File ~\.openclaw\start_bridge.ps1
Enable-ScheduledTask -TaskName 'OpenClaw Gateway'; Start-ScheduledTask -TaskName 'OpenClaw Gateway'
# reachable?
(Test-NetConnection 127.0.0.1 -Port 18789).TcpTestSucceeded
```

> **Two hard-won operational rules:**
> 1. **Do NOT rapid-restart the gateway.** The node process is launched *detached* (a watchdog respawns
>    it instantly when killed), so `Stop-ScheduledTask` alone won't stop it — kill the node PID for a
>    real restart. And several fast restarts trip Discord's one-login-at-a-time limit, making the bot
>    look permanently stuck at "awaiting gateway readiness" (it self-recovers once you stop).
> 2. **Bridge up before gateway**, always.

---

## 11. Personality + memory (`~/.openclaw/workspace/`)

The bot's behaviour is plain Markdown the brain reads live (so edits take effect immediately):
- `AGENTS.md` — agent instructions, the `sessions_spawn` ACP spawn recipes, and the `/claw` command
  helper (maps "set permission to bypass" → the exact `/acp set-mode bypassPermissions`, etc.).
- `IDENTITY.md` / `SOUL.md` / `USER.md` — who clanker is, tone, who you are.
- `HEARTBEAT.md` — autonomous-tick instructions (**disabled** by default so Kimi only runs when prompted).
- `MEMORY.md` + the `memory-core` plugin — persistent notes.
- `skills/` — your own skills; `skill-workshop/` — drafts.

---

## 12. Known issues / gotchas (read before debugging)

| Symptom | Cause / fix |
|---|---|
| A **code** feature won't turn on (voice ffmpeg, a Discord button, `/acp` help values) | **Stale-dist wall** — gateway runs old bytecode for hand-patched `dist/*.js`. Config works, code patches don't. Fix = clean `npm` reinstall of openclaw. |
| Bot stuck at "awaiting gateway readiness", flaky | You rapid-restarted → Discord IDENTIFY limit. Stop restarting; it self-recovers. Also check the bridge is up + has `TCP_NODELAY`. |
| Gateway "won't stop" via `Stop-ScheduledTask` | Node is detached + self-healed. Kill the node PID directly, then start the task. |
| `/model fable` "works" but isn't Fable | Kimi endpoint echoes any model id → serves Kimi. Real Fable/Claude is only via the **ACP claude** backend. |
| Editing `openclaw.json` took the bot offline | A schema error (e.g. `execApprovals.target:"origin"`) silently kills it. Always `openclaw doctor` before restart. |
| `python` hangs | Use **`python3`** (bare `python` is a 0-byte stub on this PC). |
| Discord dies whenever the VPN changes | Discord needs *all* its traffic proxied through the bridge → UniClash. Keep the bridge + UniClash up. |

---

## 13. File map (where every piece lives)

| Path | Purpose | Secret? |
|---|---|---|
| `~/.openclaw/.env` | `DISCORD_BOT_TOKEN`, `KIMI_API_KEY` | **YES** |
| `~/.openclaw/openclaw.json` | main config (+ `gateway.auth.token`) | **YES** (token) |
| `~/.openclaw/discord_socks_bridge.py` | HTTP→SOCKS5h bridge (7994→7993) | no |
| `~/.openclaw/start_bridge.ps1` | bridge launcher | no |
| `~/.openclaw/gateway.cmd` / `gateway.vbs` | gateway service launcher | no |
| `~/.openclaw/exec-approvals.json` | approvals socket token | **YES** |
| `~/.openclaw/acpx/*-wrapper.mjs` | ACP backend wrappers (claude, codex) | no |
| `~/.openclaw/acpx/codex-home/config.toml` | Codex model/settings | no |
| `~/.openclaw/acpx/codex-home/auth.json` | `OPENAI_API_KEY` | **YES** |
| `~/.openclaw/npm/projects/openclaw-acpx-*/` | installed acpx + ACP adapters | no |
| `~/.openclaw/workspace/AGENTS.md` + `*.md` | personality + spawn recipes | no |
| `~/.openclaw/workspace/state/sessions/*.json` | live ACP session state | no |
| `~/.openclaw/workspace/tools/*.py` | patch/helper scripts (bridge, status board, patches) | no |
| `~/.claude/settings.json` | Claude backend model (`"fable"`) | no |
| `~/.claude/.credentials.json` | Anthropic OAuth | **YES** |
| `%APPDATA%/npm/node_modules/openclaw/dist/` | the OpenClaw program (the stale-dist part) | no |
| `%LOCALAPPDATA%/Temp/openclaw/openclaw-YYYY-MM-DD.log` | gateway runtime log | no |

**If you version this for backup:** commit `openclaw.template.json` (redacted), the bridge + launchers,
the wrappers, the `workspace/*.md`, and the tools scripts. **Never commit** `.env`, `openclaw.json`
(real), `auth.json`, `exec-approvals.json`, `.credentials.json`, `state/`, logs, or `node_modules`.

---

## 14. From-zero reproduction order (checklist)

1. Install Node + Python3; install & log in to `claude` and/or `codex` CLIs.
2. `npm install -g openclaw`; run `openclaw` once to scaffold `~/.openclaw/`.
3. Put secrets in `~/.openclaw/.env` (Discord + Kimi keys).
4. Drop in `openclaw.json` from `openclaw.template.json`, fill the placeholders.
5. Install UniClash; copy `discord_socks_bridge.py` + `start_bridge.ps1`; start the bridge; verify 7994.
6. Enable the `discord`, `kimi`, `acpx`, `memory-core` plugins; set `channels.discord.proxy` + `proxy.proxyUrl` to `http://127.0.0.1:7994`.
7. Set `execApprovals` + `allowFrom` to your Discord user id.
8. For ACP: confirm `claude`/`codex` CLIs run; set `~/.claude/settings.json` model (Claude) and/or `codex-home/config.toml` + `auth.json` (Codex).
9. Copy `workspace/AGENTS.md` + personality files.
10. Register the **OpenClaw Gateway** (and optionally **Status Board**) Scheduled Tasks.
11. `openclaw doctor` → start bridge → start gateway → `@clanker hi` in Discord.
12. Test ACP: `/acp` a coding prompt; confirm a Claude/Codex session spawns.

Everything above is reconstructed from the live machine as of 2026-07-20. For the blow-by-blow history
and every fix's rationale, read `CHANGELOG.md` in this folder.
