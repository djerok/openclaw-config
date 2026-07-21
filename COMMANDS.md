# OpenClaw + Status Board — Command Reference

Quick operational commands for Eric's PC (djerok116). Run PowerShell ones in a
PowerShell window; `openclaw` ones work in PowerShell, cmd, or Git Bash.

There are **two independent Scheduled Tasks**:
- **`OpenClaw Gateway`** — the OpenClaw daemon (runs the AI agent + Discord bot).
- **`OpenClaw Status Board`** — the tiny model-free daemon that edits the
  `#status` Discord message every 5s. Runs on its own; does NOT need the gateway.

---

## Easiest: the Desktop launcher

**`C:\Users\ericc\Desktop\Clanker Control.cmd`** — double-click for a menu:
**START / STOP / STATUS / RESTART** the *entire* stack (gateway + stop-watcher +
voice-privacy sweep + status board) in one place. It drives
`~/.openclaw/clanker_control.py`, which launches the gateway **detached + hidden
with the Kimi env** (so ACP-claude authenticates and the bot outlives the window),
and on STOP disables the 5-min self-heal so it stays down.

Prefer this for everyday start/stop. The manual commands below are the fallback /
for individual pieces.

---

## OpenClaw Gateway (the bot / agent)

### Start / turn ON
```powershell
Enable-ScheduledTask -TaskName 'OpenClaw Gateway'; Start-ScheduledTask -TaskName 'OpenClaw Gateway'
```
(or simply `openclaw gateway start`)

### Stop / turn OFF (temporary — STAYS off)
```powershell
Disable-ScheduledTask -TaskName 'OpenClaw Gateway'; Stop-ScheduledTask -TaskName 'OpenClaw Gateway'
```
> The **Disable** part is required. There is a 5-minute self-heal that would
> otherwise restart the gateway within 5 min. `openclaw gateway stop` alone is
> NOT enough — it gets undone.

### Check status
```
openclaw gateway status
openclaw status                       (fuller overview)
```

### Restart (e.g. after a config change that needs it)
```
openclaw gateway start
```

### Dashboard (browser control UI)
```
openclaw dashboard
```
or open http://127.0.0.1:18789/ (loopback only, this PC).

### Is it reachable?
```powershell
(Test-NetConnection 127.0.0.1 -Port 18789).TcpTestSucceeded
```

---

## Status Board (the #status Discord channel)

The board updates every 5 seconds on its own. It keeps working even when the
gateway is OFF (it will just show "Gateway: DOWN").

### Start / turn ON
```powershell
Enable-ScheduledTask -TaskName 'OpenClaw Status Board'; Start-ScheduledTask -TaskName 'OpenClaw Status Board'
```

### Stop / pause (STAYS off)
```powershell
Disable-ScheduledTask -TaskName 'OpenClaw Status Board'; Stop-ScheduledTask -TaskName 'OpenClaw Status Board'
```

### Check status
```powershell
(Get-ScheduledTask -TaskName 'OpenClaw Status Board').State
Get-Process pythonw -ErrorAction SilentlyContinue    # the running daemon
```

### Change the refresh interval / edit behavior
The daemon is `C:\Users\ericc\.openclaw\workspace\tools\status_board.py`
(argument `5` = seconds). Its Discord target is in
`C:\Users\ericc\.openclaw\status-board.local.json` (webhook URL — do not share).

---

## Discord bot notes

- The bot's Discord presence is part of the **gateway** — start/stop the gateway
  to bring the bot online/offline. (The status board is separate and stays up.)
- Channel health (needs gateway up): `openclaw channels status --probe`
- Bot has **Administrator** in the server (can create channels, webhooks, voice).
- Still TODO in the Discord Developer Portal: enable **Message Content Intent**
  so the bot reads unmentioned messages in server channels.
- Discord requires the local proxy (UniClash / 127.0.0.1:7993) to be running —
  if UniClash is off, the bot can't connect.

---

## ACP Harness — drive Claude Code from Discord

The `@openclaw/acpx` plugin lets OpenClaw spawn a real **Claude Code** session
and steer it from a Discord chat. Your messages go to Claude Code; its output
streams back into the chat. (Requires the gateway to be running.)

> **⚠️ AUTH — READ BEFORE RUNNING ACP.** The ACP harness launches your **actual
> `claude` CLI**, which reads `~/.claude/settings.json` — so it uses whatever
> **`switch-claude` mode is active**. As of 2026-07-19 that mode is
> **`claude-oauth` (your Anthropic account)** — meaning if you run the ACP harness
> RIGHT NOW it would drive Claude Code on your Max subscription, which **violates
> Anthropic's ToS and risks your account** (third-party-harness ban, OpenClaw named,
> 2026-04-04). **Do `switch-claude kimi` first** (spawned claude → Kimi = free,
> clean), OR give the ACP sessions their own key (below).
>
> Your *interactive* Claude Code (you driving it in terminal/VS Code/desktop) on
> the Max plan is totally fine — only the OpenClaw-*spawned* one is the problem.
>
> **Cleaner long-term (for real Anthropic in Discord):** give the acpx adapter a
> **dedicated metered Anthropic API key** (from console.anthropic.com, pay-per-token,
> NOT the Max sub) separate from `settings.json`. Then Discord sessions run on the
> API key while your interactive Claude stays on Anthropic — no switch-claude
> juggling, no account risk. (Not set up yet — needs Eric's key.)

### Start a session (in a Discord chat with the bot)
```
/acp spawn claude --bind here
```
Binds a live Claude Code session to that chat. First spawn is slow once (fetches
the adapter). Optional: `--cwd C:\path\to\repo` to point it at a project,
`--thread auto` (in a server channel) to give each session its own thread.

### Controls
```
/acp status                          show backend, mode, state
/acp sessions                        list recent ACP sessions
/acp cancel                          interrupt the current turn
/acp close                           end the session + unbind the chat
/acp steer --session <label> ...     nudge an unbound session
/acp set-mode plan                   set runtime mode (plan/etc.)
/acp model <id>                      SWITCH THE MODEL (e.g. /acp model sonnet, /acp model claude-fable-5)
/acp set <key> <value>               set a session option (e.g. thinking)
/acp timeout <seconds>               set the per-turn timeout
/acp reset-options                   reset session OPTIONS (model/mode/etc.) to defaults — NOT the conversation
/acp install                         install/update the Claude Code ACP adapter
/acp help                            list every /acp action
/acp cwd C:\path                     change working directory
/acp permissions <profile>           change approval profile
/acp doctor                          backend health check
```

### Permission profile (how much the spawned Claude Code may do)
- Current: **`approve-reads`** — it can read/analyze freely; write/exec attempts
  are denied-and-continue (it tells you, doesn't stall).
- To let it actually edit a repo from Discord, bump to **`approve-all`**:
  ```
  openclaw config set plugins.entries.acpx.config.permissionMode approve-all
  openclaw gateway start
  ```
  (Back to safe: set it to `approve-reads`.)

### Setup state (already done)
- Plugin installed + allowlisted (`plugins.allow = ["kimi","acpx"]`),
  `plugins.entries.acpx.enabled = true`, `permissionMode = approve-reads`,
  `nonInteractivePermissions = deny`. Verify anytime with `/acp doctor`.

---

## Reset / compact a conversation

Two surfaces, two command sets — pick by which chat you're in.

**djerokbot (the Kimi bot) — its OWN chat, NO prefix:**
```
/reset       wipe the conversation, fresh start
/clear       clear the context
/compact     summarize the conversation to free space (keeps the gist)
/new         start a new conversation
```

**A Claude Code (ACP) session you spawned** — there is **NO** `/acp clear` / `/acp compact` / `/acp reset` / `/acp new` (those aren't real subcommands — see the real list in the ACP Controls block above). To reset the context you start fresh:
```
/acp close                       end the current Claude Code session
/acp spawn claude --bind here    start a clean one in the same chat
```
- `/acp reset-options` only resets config (model/mode/cwd/etc.) — **not** the conversation.
- Claude Code auto-compacts its own context as it fills; there's no manual `/acp compact`.

**Rule of thumb:** chatting with **djerokbot directly** → `/reset` or `/compact`.
In a chat **bound to a Claude Code session** → `/acp close` + `/acp spawn` to reset.

---

## Exec guardrails (how much the agent may run without asking)

```
openclaw exec-policy show                 (see current policy)
openclaw exec-policy preset cautious      (ask before risky commands — SAFE)
openclaw exec-policy preset yolo          (no prompts — CURRENT state)
```
Current: fully auto (no prompts); file-mutation tools (write/edit) still blocked.
Re-tighten to `cautious` before leaving the agent running unattended.

---

## Claude Code auth (separate from OpenClaw)

```
switch-claude status          (which mode)
switch-claude claude          (Anthropic OAuth)
switch-claude kimi            (Kimi K3)
```
Restart Claude Code / VS Code after switching.

---

## Full shutdown of everything (bot + board)

```powershell
Disable-ScheduledTask -TaskName 'OpenClaw Gateway';       Stop-ScheduledTask -TaskName 'OpenClaw Gateway'
Disable-ScheduledTask -TaskName 'OpenClaw Status Board';  Stop-ScheduledTask -TaskName 'OpenClaw Status Board'
```

## Bring everything back
```powershell
Enable-ScheduledTask -TaskName 'OpenClaw Gateway';        Start-ScheduledTask -TaskName 'OpenClaw Gateway'
Enable-ScheduledTask -TaskName 'OpenClaw Status Board';   Start-ScheduledTask -TaskName 'OpenClaw Status Board'
```

---

## Where OpenClaw lives on disk

**The installed program (CLI):**
- `C:\Users\ericc\AppData\Roaming\npm\node_modules\openclaw\` — the package
  (entry `openclaw.mjs`, version-matched `docs\` subfolder)
- `C:\Users\ericc\AppData\Roaming\npm\openclaw.cmd` — the launcher on PATH

**Your config, state & workspace — `C:\Users\ericc\.openclaw\`** (this is the
important folder; back THIS up):
- `openclaw.json` — main config (proxy, exec policy, plugins, discord, model…)
- `.env` — **Discord bot token** (secret)
- `status-board.local.json` — **status-board webhook URL** (secret)
- `exec-approvals.json` — exec allowlist / approval policy
- `state\openclaw.sqlite` — cron jobs + run logs
- `agents\main\sessions\` — the bot's conversation session store
- `workspace\` — `AGENTS.md` (bot instructions), `HEARTBEAT.md`, and
  `tools\` (our helpers: `status_board.py`, `list_claude_sessions.py`)
- `npm\projects\` — installed plugins (kimi-provider, acpx)
- `gateway.cmd` / `gateway.vbs` — how the Scheduled Task launches the gateway
- `logs\` — gateway restart log

**Logs (runtime):** `C:\Users\ericc\AppData\Local\Temp\openclaw\openclaw-<date>.log`

**PATH fix (so `openclaw` resolves in PowerShell):**
`C:\Users\ericc\Documents\WindowsPowerShell\profile.ps1`

**Claude Code's own files (separate from OpenClaw):**
- `C:\Users\ericc\.claude\settings.json` — Claude Code config (switch-claude edits this)
- `C:\Users\ericc\.claude\projects\<project>\*.jsonl` — all Claude Code session transcripts

---

## Re-enable the live health dot (if you want it back)

```
openclaw config set channels.discord.autoPresence.enabled true
openclaw gateway start
```
(Currently OFF — the bot shows steady green online instead.)

---

## Adaptive fast/smart router (Kimi)

The bot auto-routes each message: trivial chatter → fast Kimi model (thinking
off); real work / mid-task → `k3` with adaptive thinking. Runs in-process inside
the kimi provider — no proxy involved, Discord untouched.

### See routing decisions
```
type C:\Users\ericc\.openclaw\npm\projects\openclaw-kimi-provider-*\node_modules\@openclaw\kimi-provider\dist\kimi_router_inproc.log
```
Each line: `route=fast|smart  model=…  preview="…"`.

### Re-apply after `openclaw update` (REQUIRED — the patch is in node_modules)
```
python3 C:\Users\ericc\.openclaw\workspace\tools\apply_kimi_router_patch.py
openclaw gateway start
```
Idempotent (skips if already patched), backs up, validates with `node --check`.

### Tune it (keywords / models / thinking budgets)
Edit the consts at the top of the injected `// ===== adaptive fast/smart router`
block in `…/kimi-provider/dist/stream.js` — AND mirror the same edit in
`apply_kimi_router_patch.py`, or the next update's re-apply reverts your tuning.
Then `openclaw gateway start`.

### Disable / revert to plain k3
Restore the newest `stream.js.bak-*` next to the patched file, then
`openclaw gateway start`.

### Change the model / thinking from Discord (live)
The bot auto-routes by default and shows what it used in a footer under each reply
(`🤖 model · 🧠 thinking · route · OpenClaw`). Override per-chat with native commands:
```
/model Auto        # auto-route (default): trivial→fast, real→k3+thinking
/model K3          # force smart (k3 + adaptive thinking) on everything
/model KimiFast    # force fast (highspeed, thinking off)
/model Kimi        # kimi-for-coding (fast)
/think off|low|medium|high    # thinking depth (honored when pinned to k3)
```
The footer's `auto·fast` / `auto·smart` / `manual` tag shows which mode is active.
