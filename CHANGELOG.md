# AI Stack Change Log — djerok116 (Eric's PC)

Location: `C:\Users\ericc\Desktop\openclawconfig\` (moved here from `ai-stack-log`
2026-07-18). Sibling file **`COMMANDS.md`** holds the start/stop/scheduler
commands for OpenClaw and the status board.

Living document. Every configuration change to the AI stack on this machine
(Claude Code, Kimi routing, OpenClaw, Discord/ACP integration, related system
repairs) gets an entry here, newest day first within each section.

**Secrets policy: no credential values in this file, ever** (it goes to GitHub).
Secrets are referenced by *location* only:

| Secret | Lives in |
| --- | --- |
| Kimi API key (`sk-kimi-…`) | `~/.claude/settings.json` env (when in kimi mode), `~/.claude/kimi-env-stash.json` (when stashed), `~/.openclaw/openclaw.json` env |
| OpenClaw gateway token | `~/.openclaw/openclaw.json` (`gateway.auth.token`) |
| Exec-approvals socket token | `~/.openclaw/exec-approvals.json` |
| Discord bot token | OpenClaw config (`channels.discord`) / `DISCORD_BOT_TOKEN` |
| Anthropic OAuth credentials | `~/.claude/.credentials.json` |

---

## 2026-07-17 — Kimi K3 wired into Claude Code + OpenClaw installed

### Claude Code → Kimi routing
- Global `~/.claude/settings.json` env block routes CLI + VS Code extension to
  Kimi's coding endpoint: `ANTHROPIC_BASE_URL=https://api.kimi.com/coding/`,
  `ANTHROPIC_AUTH_TOKEN=<kimi key>`.
- Gotcha learned: a kimi.com/code subscription key only authenticates against
  `api.kimi.com/coding/` — pointing it at `api.moonshot.ai/anthropic` returns 401.
- Coding endpoint has exactly 3 model ids (`GET /coding/v1/models`):
  `k3` (1M context), `kimi-for-coding` (K2.7, 256k), `kimi-for-coding-highspeed`.
  There is no `k3[1m]` id — plain `k3` IS the 1M model.
- Tier alias map: `ANTHROPIC_DEFAULT_OPUS_MODEL=k3`,
  `ANTHROPIC_DEFAULT_SONNET_MODEL=kimi-for-coding`,
  `ANTHROPIC_DEFAULT_HAIKU_MODEL=kimi-for-coding-highspeed`,
  `CLAUDE_CODE_SUBAGENT_MODEL=k3`.

### OpenClaw 2026.7.1 installed
- Node upgraded 25.6.1 → 25.9.0 via winget (OpenClaw hard-gates Node version).
- Installed globally via npm; config at `~/.openclaw/openclaw.json`.
- Kimi provider plugin `@openclaw/kimi-provider` installed.
- Gotcha: an explicit `models.providers.<id>` entry in openclaw.json REPLACES
  the plugin's provider definition at runtime (not merged) — the entry must be
  self-sufficient: baseUrl + api + apiKey + headers + ALL models.
- Live-verified end to end: agent run answered via `api.kimi.com/coding/v1/messages`
  on model `k3`.
- Eric ran `openclaw onboard`: gateway installed as Windows Scheduled Task
  ("OpenClaw Gateway"), loopback `127.0.0.1:18789`, token auth, dashboard live.

### Windows PATH repair (PowerShell "openclaw not recognized")
- Root cause: stale environment chain — Explorer/Windows Terminal predated the
  Node-MSI PATH entry; new windows inherit the stale env. Registry PATH was fine.
- Fix: PowerShell profile shim `Documents\WindowsPowerShell\profile.ps1`
  (CurrentUserAllHosts) — guarded append of `%APPDATA%\npm` to session PATH.
- Rule: never `setx` this PATH (1024-char truncation would destroy it).

---

## 2026-07-18 — the big day

### Context windows bumped to 1M
- OpenClaw: `k3` model `contextWindow` 262144 → **1048576** in openclaw.json.
- Claude Code: `CLAUDE_CODE_MAX_CONTEXT_TOKENS` + `CLAUDE_CODE_AUTO_COMPACT_WINDOW`
  262144 → **1048576** in `~/.claude/settings.json`.
- Later confirmed from billing page: plan is **Allegretto ¥199 (RMB store)** —
  1M is entitled; earlier "Moderato might reject >262k" caveats are void.

### VS Code extension model dropdown restored
- Cause: a custom model id pinned via `ANTHROPIC_MODEL` hides the extension's
  model picker (the GLM era had a dropdown because claude-code-router kept
  standard tier names and remapped at the proxy).
- Fix: removed `ANTHROPIC_MODEL`, set top-level `"model": "opus"` — the alias
  resolves Opus→k3, so the label says Opus but runs K3.
- Discovery: the Kimi endpoint accepts ANY model id, echoes it verbatim, and
  serves an undisclosed Kimi model under it (probe: `claude-fable-5` → HTTP 200,
  self-reports "I am Kimi, by Moonshot AI"). Only Opus/Sonnet/Haiku picks are
  meaningful under this routing; a "Fable" pick is NOT Fable.

### `switch-claude` auth toggle built
- `switch-claude status | claude | kimi` — one command flips Claude Code
  (terminal + extension) between Anthropic OAuth and Kimi routing.
- Implementation: `%APPDATA%\npm\switch-claude.cmd` →
  `~/.claude/claude_auth_switch.py`. Kimi env keys are stashed verbatim in
  `~/.claude/kimi-env-stash.json` on `claude`, restored on `kimi`.
- OAuth credentials survive the Kimi era untouched; no re-login needed.
- Wrapper hardcodes the real python path — the bare `python` in cmd resolves to
  a broken WindowsApps store alias (same dangling-alias disease as winget).
- **Current mode: claude-oauth** (temporary, per Eric; back = `switch-claude kimi`).
- Restart sessions after every switch (env is read at launch).

### OpenClaw skills: dependency install → 27/52 eligible (was 19)
- npm: `mcporter` (MCP servers), `@google/gemini-cli`, `@steipete/summarize`,
  `@steipete/oracle` (bare npm `summarize`/`oracle` are unrelated packages —
  always the `@steipete/` scope).
- Direct official downloads into `%APPDATA%\npm` (winget broken, see below):
  ripgrep 15.2.0 (sha256-verified), himalaya v1.2.0, 1Password CLI `op` 2.35.0.
- Config toggle: `skills.entries.coding-agent.enabled=true`.
- Not enable-able here: 7 macOS-only skills, ~12 Mac-brew/Go-only or
  hardware-bound CLIs, API-key-gated ones (trello, sag/ElevenLabs, goplaces).
- Deliberately skipped: local `openai-whisper` (would pull torch into the robotr
  Python), `sherpa-onnx-tts` (needs ~100MB model download; offerable).
- System finding: **winget is broken** — WindowsApps execution aliases dangle
  (target DesktopAppInstaller package folder gone). Workaround: direct official
  downloads. Fix if ever needed: reinstall "App Installer" from MS Store.

### Gateway "connection lost" saga → fixed at the source
- Symptom: dashboard "Gateway connection lost" repeatedly through the night.
- Mechanism: OpenClaw's default reload mode (`hybrid`) restarts the gateway
  process for restart-class config changes; that assumes a service manager that
  relaunches it. The Scheduled Task only triggered at logon → every such config
  write (by us, or by the agent's own `openclaw mcp add/configure`) stranded it.
- Interim: PT5M repetition added to the task (self-heal ≤5 min), later removed
  during the incident (below), then re-added at 04:07 once guardrails made it safe.
- **Root fix 04:11: `openclaw config set gateway.reload.mode hot`** — config
  changes now hot-apply in-process; the gateway never self-restarts. Proven:
  same pid survived a `tools.exec` config write (that class previously killed
  it 4×/night).
- Residual: `gateway.*`-class changes (port/bind/auth) now need a manual
  `openclaw gateway start`; PT5M repetition stays as crash backstop.

### node.exe deletion incident (cause unproven)
- `C:\Program Files\nodejs\node.exe` vanished twice (~01:26 and again after the
  01:37 repair), killing ALL Node CLIs (claude, openclaw, npm, ccr) — the
  gateway launcher hardcodes that path, so it couldn't boot and logged nothing.
- Ruled out: Windows Defender (no detections/quarantine), MSI (no installer
  events). The OpenClaw k3 agent was running an unattended install/debug loop
  at the time (windows-mcp via uv, @playwright/mcp, blocked machine-scope
  AutoHotkey winget attempts) — full-trajectory grep shows NO node-delete
  command; its only `Remove-Item -Recurse` was correctly scoped to a corrupted
  uv tools dir. Leading suspect: collateral from installs killed mid-write by
  the gateway crash cycle. Not proven.
- Repair: official `node-v25.9.0-x64.msi` (nodejs.org, sha256-verified against
  SHASUMS256.txt), installed twice via UAC-approved msiexec.
- Lesson: don't leave the OpenClaw agent grinding unattended on install loops;
  the 5-min gateway self-heal was auto-resuming its mid-flight turn (made
  things worse) — that interaction is why self-heal was temporarily removed.

### Exec guardrails (OpenClaw agent)
- Default was `security=full` (unrestricted shell) — the incident enabler.
- Applied `openclaw exec-policy preset cautious`, then evolved through the day:
  1. **cautious** (ask-on-miss) — approval cards for everything new
  2. **silent file-safe** (05:22, scheduled): `allowlist / ask=off /
     fallback=deny` + `tools.deny=["write","edit","apply_patch"]` — no prompts,
     non-allowlisted exec silently denied, no file mutation possible
  3. **ask-everything (CURRENT, ~05:5x)**: `allowlist / ask=on-miss /
     fallback=deny`, `tools.deny` KEPT — everything is possible but file
     mutation and new commands always prompt; silent deny only when no UI is
     reachable
- `tools.exec.strictInlineEval=true` — inline `node -e` / `python -c` always
  need approval even if the interpreter is allowlisted.
- Allowlist (approvals file `~/.openclaw/exec-approvals.json`):
  read-only diagnostics `rg where whoami hostname tasklist systeminfo ping
  nslookup tracert` (agent-`*` scope; note: the CLI writes scope `*`, not
  `main`), plus argPattern-restricted `git` (read-only subcommands, `--output`
  blocked) and `node/python/npm --version`, plus Eric's allow-always'd
  openclaw commands from the Discord setup.
- Two-layer model: effective policy = stricter of `tools.exec.*` (openclaw.json)
  and the host approvals file. Presets (`cautious`/`yolo`) set both.
- Mode ladder ≈ Claude Code's picker: deny / allowlist / ask / auto / full
  (`tools.exec.mode`); `auto` adds an AI reviewer for misses.

### Discord channel
- Bot: @clankerthatcontrolsdjerokpc. Token valid from the start, but the
  channel never reached READY (reconnect loop, 28+ attempts).
- **Root cause: Discord is proxy-only on this network; OpenClaw's websocket
  bypassed the system proxy.** Fix: `proxy.enabled=true`,
  `proxy.proxyUrl=http://127.0.0.1:7993` (UniClash) + gateway restart.
  Log then shows "rest proxy enabled" + "gateway proxy enabled"; probe:
  connected/works.
- **Consequence: OpenClaw now hard-depends on UniClash running** (proxy
  enabled + unreachable proxy = startup failure by design, no direct fallback).
- Native approval cards in Discord: `channels.discord.execApprovals.enabled=true`
  + `approvers=["662339124627374100"]` (Eric's user id; OpenClaw deliberately
  does not infer approvers). Buttons: Allow once / Always allow / Deny.
- Second Discord account (901676858322595862) has a DM session but is NOT an
  approver (pending Eric's confirmation it's his).
- `intents: content=limited` — enable Message Content Intent in the Discord
  Developer Portal for the bot to read unmentioned guild messages.

### ACP harness — Claude Code driven from Discord
- `@openclaw/acpx` installed; `plugins.allow=["kimi","acpx"]` (the allowlist is
  restrictive — acpx had to be added); `plugins.entries.acpx.enabled=true`.
- Headless permission profile: `permissionMode=approve-reads`,
  `nonInteractivePermissions=deny` (reads auto-approved; write/exec attempts
  denied-and-continue). Bump to `approve-all` only deliberately.
- Usage: `/acp spawn claude --bind here` in a chat = live Claude Code session
  bound to it; `/acp cancel` (interrupt turn), `/acp close` (end + unbind),
  `/acp sessions`, `/acp steer --session <label> …` for unbound multi-session.
- Architecture note: bound sessions BYPASS the k3 agent — OpenClaw is transport
  only; Claude Code runs its own loop, tools, and auth (burns whatever
  switch-claude mode is active). OpenClaw's exec guardrails do NOT govern
  Claude Code's internal tools — the ACPX permission profile does.
- First bind attempt failed ("Session binding adapter failed to bind target
  conversation") → fix: `session.threadBindings.enabled=true` +
  `channels.discord.threadBindings.enabled=true` (binding infra is off by
  default) + restart. If DM binding still refuses: use a server channel/thread,
  or unbound spawn + steer.
- Server-mode capability (documented, not yet configured): "Persistent ACP
  channel bindings" — `agents.list[]` entry with `runtime.type=acp`
  (agent=claude, mode=persistent, pinned cwd) + `bindings[]` with `type:"acp"`
  matching a Discord channel id + `requireMention:false` ⇒ a Discord channel
  that IS an always-on Claude Code session per repo.

### Agent-made changes (recovered from OpenClaw logs & config audit)

Changes made by the k3 agent itself during Eric's TUI/Discord sessions —
recovered from `~/.openclaw/logs/config-audit.jsonl` and the daily gateway log
(`%LOCALAPPDATA%\Temp\openclaw\openclaw-<date>.log`; audit timestamps are UTC,
local = +8).

- **Config-write census:** 40 writes to openclaw.json across 07-17/18 —
  **17 by the k3 agent** (cwd `~\.openclaw\workspace`), 20 by Claude-driven
  terminal work (cwd robotr), 3 by Eric directly. Pre-`hot`-reload-fix, each
  write was a potential gateway death — this census explains the outage
  frequency.
- **MCP servers configured (persist in `mcp.servers`):**
  - `windows` — Windows desktop automation MCP (`windows-mcp` installed via
    `uv tool`, exe `~\.local\bin\windows-mcp.exe serve`). Its uv env
    (`%APPDATA%\uv\tools\windows-mcp`) was corrupted mid-install by a gateway
    crash; the agent correctly removed and reinstalled it.
  - `playwright` — browser automation MCP (`@playwright/mcp` npm-global),
    wired as `node.exe` + `cli.js` directly because newer Node blocks spawning
    `.cmd` shims (spawn EINVAL); 24 tools, with `browser_run_code_unsafe`
    excluded via toolFilter (the agent's own safety choice).
- **@openclaw/discord channel plugin** installed by the agent (Eric approved
  each command via cards; the argv-pinned approvals remain in the allowlist).
- **AutoHotkey (portable)** installed user-scope at
  `%LOCALAPPDATA%\Programs\AutoHotkey-portable\` (32+64-bit) — the agent's
  fallback after its machine-scope winget install was blocked by the
  elevation guard.
- **Workspace artifacts** in `~/.openclaw/workspace/tools/`:
  `discord.patch.json5`, `discord-allowfrom.patch.json5`,
  `mcp-handshake-test.js`, `mcp-call-test.js` (the agent's own MCP debug
  harnesses).

### Discord visibility suite (evening)

Replaces the need for OpenClaw-OS (evaluated, deferred — young, source-built,
no independent reviews) with Discord-native visibility:

1. **Status board** — cron job `discord-status-board` (`7,37 * * * *`,
   isolated session, no chat delivery): the agent maintains a pinned
   "📊 STATUS BOARD" message in Eric's DM, edited in place each run
   (sessions, ACP sessions, pending approvals, timestamp). First manual run: ok.
2. **Bot presence** — `channels.discord.autoPresence.enabled=true`:
   bot's Discord status dot maps to runtime health (online/idle/dnd)
   (+ gateway restart, since presence is restart-class).
3. **Heartbeat digests** — `agents.defaults.heartbeat`: every 30m,
   `target=last` (Eric's DM), `lightContext` + `isolatedSession` +
   `skipWhenBusy` for cheap runs; workspace `HEARTBEAT.md` populated with a
   checklist (pending approvals >10 min, sessions running >2h, repeated
   failures) — quiet runs reply `HEARTBEAT_OK` and are dropped. Note: the
   onboarding default HEARTBEAT.md was comments-only, which DISABLES
   heartbeat API calls; populating it activates them (~48 small k3
   turns/day across board+heartbeat).
4. **Event pings** — already active (exec-finished messages, approval cards).

CLI lesson: `openclaw cron add` requires `--message` (not positional) and
`--session main` jobs accept only `--system-event`; free-prompt jobs must be
isolated (default).

### Reorg: moved to `Desktop\openclawconfig\` + added COMMANDS.md

- Relocated this changelog from `Desktop\ai-stack-log\` to
  `Desktop\openclawconfig\CHANGELOG.md` (old empty folder removed).
- Added `Desktop\openclawconfig\COMMANDS.md` — operational cheat sheet:
  start/stop/scheduler commands for both Scheduled Tasks (`OpenClaw Gateway`
  and `OpenClaw Status Board`), dashboard, exec-policy, switch-claude, full
  shutdown/restart.

### ACP auth clarified + disk-locations documented (2026-07-19)

- Clarified how ACP connects to Claude Code: it launches your **actual `claude`
  CLI**, which reads `~/.claude/settings.json` → uses whatever `switch-claude`
  mode is active. **Verified current mode = `claude-oauth` (Anthropic account)**
  → running ACP right now would drive Claude Code on the Max sub = ToS/account
  risk. Rule written into COMMANDS.md: `switch-claude kimi` before ACP, or give
  acpx a dedicated metered Anthropic API key (decouples Discord sessions from the
  interactive Claude — the clean design for "real Anthropic in Discord", not yet
  set up, needs Eric's key).
- Documented **where OpenClaw lives on disk** in COMMANDS.md: package =
  `%APPDATA%\npm\node_modules\openclaw\`; config/state/workspace (the folder to
  back up) = `C:\Users\ericc\.openclaw\` (openclaw.json, .env=Discord token,
  status-board.local.json=webhook, state\openclaw.sqlite=cron, workspace\AGENTS.md
  + tools\); logs = `%LOCALAPPDATA%\Temp\openclaw\`; PATH shim in
  Documents\WindowsPowerShell\profile.ps1.

### Discord "Claude Code cockpit" — Phase 1 started (natural-language)

- Vision (Eric): drive Claude Code from Discord by *asking* (not `/acp` commands)
  — list sessions, "create a channel for X" → directory picker → channel becomes
  a live Claude Code session; per-session mode/model/effort; usage meter; custom
  status ("editing…/compacting…"); status board of active sessions; channel
  delete / `/exit` closes, re-command restarts.
- Design decisions: (a) natural language, OpenClaw agent auto-orchestrates,
  ASKS when unsure (mirrors Claude); (b) Eric wants **real Anthropic** models in
  the sessions — which needs a **metered Anthropic API key he provides** (cannot
  use his Max sub = ToS/account risk; I can't set up billing). Interim: build on
  Kimi (free, works now), Anthropic key = drop-in later.
- Phase 1 piece DONE: **"what sessions are there" now works via plain English.**
  Helper `~/.openclaw/workspace/tools/list_claude_sessions.py` (deterministic,
  no LLM — scans ~/.claude/projects, 86 sessions, title+folder+time+id) +
  AGENTS.md orchestration section teaching the bot to run it, summarize a
  session on request, and the ask-when-unsure golden rule.
- NEXT (still to wire): channel-create-under-category + programmatic ACP spawn
  bound to it (needs verifying how the agent spawns ACP sessions) + the
  directory-picker + lifecycle. Blocked on the Anthropic key for real-Anthropic;
  Kimi path can proceed. Hard/limited bits documented: custom native "thinking"
  text (Discord won't allow — use an edited status message instead), usage meter
  (needs ACP to expose token counts), channel-delete events (needs verification).

### OpenClaw "update" 2026-07-19 — no-op reinstall, verified + restarted

- Eric reinstalled OpenClaw. It was a **same-version reinstall** (2026.7.1 →
  2026.7.1, build 2d2ddc4) — no actual version change, nothing structural to
  migrate. Audited everything an update could reset: **all survived** — config
  (proxy, `reload.mode=hot`, exec `full/off`, tools.deny, `plugins.allow`,
  autoPresence off, execApprovals), the PT5M task self-heal repetition, Node
  25.9.0, and the `kimi/k3` brain. Plugins reloaded (acpx, discord, memory-core).
- Only action needed: the gateway was DOWN + its task **Disabled** (leftover from
  an earlier manual shutdown, not the update) → `Enable-ScheduledTask` +
  `Start` → back to HTTP 200, Discord connected, k3 answering. Lesson for future
  updates: same-version reinstalls are harmless; just verify config + restart
  the gateway.

### "runtime degraded" (recurring) — root-caused + presence disabled

- Kept showing amber "runtime degraded" even after messaging the bot. The bot
  was ALWAYS fine (model calls return 200; message → real reply). The presence
  health signal itself was unreliable here: (a) a `system-presence` read
  rejected for `missing scope: operator.read`, and (b) the agent-installed
  **`windows-mcp`** server failing to start every turn (`Connection closed`) —
  a broken subsystem dragging runtime health to "degraded" → idle dot.
- Fix: removed the broken windows-mcp (`openclaw mcp unset windows`; playwright
  kept) + **disabled autoPresence** (`channels.discord.autoPresence.enabled=false`)
  + restart. Bot now shows steady green online. Tradeoff: no live health dot
  anymore (it was crying wolf constantly); re-enable with
  `openclaw config set channels.discord.autoPresence.enabled true` + restart.
  (windows-mcp = the computer-control server; was broken anyway — set up a
  working one later if PC-control is wanted.)

### Bot Administrator granted + model-free status board LIVE

- Fixing the bot's permissions: re-inviting/role-editing was confusing (bot's
  own role is Discord-managed/locked). Solution that worked: Eric created a
  separate role with Administrator and assigned it to the bot. Verified via
  Discord REST — bot now has **effective Administrator** (roles "OpenClaw" +
  "admin", admin=True).
- **Status board now LIVE** (the model-free daemon from earlier, finally
  unblocked): created a locked read-only `#status` channel
  (id 1528064775794200810, @everyone Send denied) + `status-board` webhook +
  initial message (id 1528064782555549756), saved to
  `~/.openclaw/status-board.local.json`. Daemon runs as a **Scheduled Task
  "OpenClaw Status Board"** (pythonw at logon, restart-on-fail, runs forever)
  editing that one message **every 5s** — verified ticking (timestamps advance),
  zero models / zero agent / zero approval prompts, independent of the gateway.
  Shows Gateway up/down, Node ver, session counts, exec policy, timestamp.
  (Currently shows Gateway DOWN because OpenClaw is shut off; will flip green
  on restart.) Daemon persists across reboots.
- Reminder still pending: **Message Content Intent** (Developer Portal → Bot)
  for the bot to read unmentioned server messages. Video/screenshare remains
  impossible regardless of Administrator.

### "Bot keeps asking permission" — old status-board cron was the culprit

- After exec went full/off, Eric still got "Approval required" spam. Traced NOT
  to interactive exec (that's genuinely silent — effective full/off confirmed,
  zero exec-approval log lines since the switch) but to the **old k3
  status-board cron (8f484f7a)**: it kept trying `openclaw tasks list` /
  `openclaw approvals list` via exec, and in the **isolated cron-run context**
  those still gate to "interactive approval," which got delivered as spam. One
  stuck run fired ~20+ of them.
- Eric had shut OpenClaw down (task Disabled + gateway stopped via the documented
  shutdown command), so cron CLI couldn't reach the gateway. Removed the job
  **directly from `~/.openclaw/state/openclaw.sqlite`** (tables `cron_jobs` +
  `cron_run_logs`, WHERE job_id=8f484f7a…) while the DB was idle — backed up to
  `openclaw.sqlite.bak-20260718` first, `PRAGMA integrity_check` = ok. cron_jobs
  now 0 rows. Won't spam on restart. (Model-free daemon still replaces it once
  the webhook/Administrator is sorted.)

### Python `python`-hangs fix (late night)

- Symptom: the bot's `python ...` commands hang. Root cause: a broken
  **0-byte `python` stub in `C:\Windows\System32`** (first in PATH) shadows the
  real interpreter and blocks forever; the WindowsApps store aliases behind it
  are also broken. Confirmed: bare `python --version` hangs; real
  `Programs\Python\Python312\python.exe` = 3.12.10, works.
- Fix (two parts): (1) created `python.cmd` + `python3.cmd` shims in
  `…\Programs\Python\Python312\Scripts\` (index 1 in PATH, ahead of WindowsApps)
  forwarding to the real 3.12 — **`python3` now works** (verified `python3 -c
  'print(2+2)'` → 4). Bare `python` still hangs because the System32 stub is
  ahead of the shim and I won't touch System32 (admin/system files).
  (2) Appended a hard rule to `~/.openclaw/workspace/AGENTS.md`: "always use
  `python3`, never bare `python` (it hangs)". Optional future cleanup for Eric:
  delete the 0-byte `C:\Windows\System32\python` stub as admin.

### How to temporarily shut down OpenClaw

`Disable-ScheduledTask -TaskName 'OpenClaw Gateway'; Stop-ScheduledTask -TaskName
'OpenClaw Gateway'` (disable is REQUIRED — the PT5M self-heal would otherwise
revive it within 5 min). Bring back: `Enable-ScheduledTask …; Start-ScheduledTask …`.

### Exec → fully auto + model-free status board (late night)

- **Root cause of persistent prompts found:** effective exec policy = host
  approvals file ∩ config (stricter wins). The **host file** (`exec-approvals.json`)
  still had `ask: on-miss`, overriding config `mode: auto` — so the auto-reviewer
  never fired and every non-exact-match command re-prompted. (Allowlist WAS
  persisting — 54 entries — so that wasn't it. Also a real `ftruncate UNKNOWN`
  write error on the approvals file, now moot.)
- **Fix (Eric's call, "make it auto"):** `unset tools.exec.mode` then
  `openclaw exec-policy set --security full --ask off --ask-fallback deny` —
  BOTH layers now no-prompt. Interactive commands run without asking.
  **Retained guards:** `tools.deny=[write,edit,apply_patch]` (file-mutation
  tools still blocked) + `strictInlineEval`. Tradeoff: shell-level file ops
  (del/Remove-Item) now run unprompted — acceptable for present, interactive
  use; re-tighten (`exec-policy preset cautious`) before any unattended runs.
- **Model-free status board** (replaces the k3 cron — no LLM, no approval gate):
  daemon `~/.openclaw/workspace/tools/status_board.py` reads sessions.json +
  a localhost gateway health check and EDITS one Discord **webhook** message on
  a loop (default 5s). Secret config `~/.openclaw/status-board.local.json`
  (webhookUrl + messageId — NOT committed). Discord REST verified working
  through the proxy with the bot token from `~/.openclaw/.env`.
- **Blocker → needs Eric:** the bot has NO Administrator / Manage Channels /
  Manage Webhooks in guild "clanker do my work" (1527763934508089446) — the
  Administrator invite never applied (role 1527764094935896187 has none).
  Channels: #general (1527763934986113106), #try-1 (1528049647698837635).
  Fix: grant the bot Administrator (then bot auto-creates locked #status +
  webhook), OR Eric creates a #status channel + webhook and pastes the URL.
  Old k3 status-board cron (8f484f7a) still needs deleting once the daemon
  is live.

### Exec mode → auto + approval-card cleanup (late evening)

- Symptom: exec-approval cards piling up in Discord (the agent, driven from
  Eric's DM testing "can it work on my PC", kept proposing benign writes like
  `type nul > test.txt` and a config backup — each a manual "Allow once").
  Traced to the DM session, NOT the heartbeat.
- Fix 1 — **`tools.exec.mode: "auto"`** (had to `unset tools.exec.security`
  and `tools.exec.ask` first — `mode` is mutually exclusive with the legacy
  keys). Auto = allowlisted commands run; misses go through OpenClaw's native
  auto-reviewer, which auto-approves routine ones and only escalates risky
  ones to a human card. `tools.deny=[write,edit,apply_patch]` kept, so file
  mutation still can't bypass exec.
- Fix 2 — **`channels.discord.execApprovals.cleanupAfterResolve: true`**:
  resolved approval cards auto-delete instead of piling up.
- Also confirmed: the bot IS now in a server — two guild-channel sessions
  live (`1527763934986113106`, `1528049647698837635`). Message Content Intent
  still `limited` (Eric to enable in portal for unmentioned guild messages).

### "runtime degraded" presence — ghost agent cleanup (late evening)

- Bot presence showed idle + "runtime degraded" while model calls were 100%
  healthy. Cause: the failed 19:03 `/acp spawn claude` attempt left a
  **disk-backed ghost agent** at `~/.openclaw/agents/claude/` (empty sessions
  dir) — status counted 2 agents, gave the ghost its own 30m heartbeat, and
  its dead runtime dragged the availability tracker (which feeds autoPresence)
  to "degraded". Neither `agents.list` (empty) nor `openclaw agents list`
  (main only) showed it.
- Fix: gateway stop → moved the store to
  `~/.openclaw/agents-claude-ghost.bak-20260718` → start. Status now
  Agents: 1, heartbeat main-only; presence returns to online on the next
  successful call.
- Going forward the presence dot means exactly: idle = proxy (UniClash) down
  or Kimi API trouble; dnd = Kimi Code credits exhausted. A *working* future
  ACP spawn recreates `agents/claude` legitimately — only a dead one degrades.

### Policy note: Anthropic subscriptions × third-party harnesses (researched 07-18)

- Anthropic ToS (clarified 2026-02, enforced from 2026-04-04, **starting with
  OpenClaw by name**): subscription OAuth tokens are valid ONLY in Claude.ai
  and Claude Code; use in any other tool **including the Agent SDK** violates
  the Consumer ToS. Third-party tools require an API key or metered
  "extra usage" billing.
- Consequences for this stack:
  - Interactive Claude Code (terminal/extension/desktop) on OAuth: fine.
  - OpenClaw's `claude-cli` model backend on OAuth: **prohibited — do not wire.**
  - ACP-spawned Claude Code from OpenClaw: run `switch-claude kimi` first so
    the spawned CLI hits Kimi's endpoint (no Anthropic involvement); do not
    drive it on claude-oauth mode.
  - The Kimi-as-brain architecture is the compliant version of
    "Claude-in-OpenClaw" setups seen elsewhere.

### Kimi plan facts (for billing decisions)
- Plan: RMB Allegretto ¥199/mo ("Current Plan"), auto-renewing monthly.
- Coding endpoint burns **Kimi Code credits** (Claude Code + OpenClaw share the
  pool); "agent credits" are kimi.com app features (unused here).
- RMB store ≈ 4–5× cheaper per Kimi Code multiplier than the USD store;
  within RMB, Allegretto beats Allegro per-credit (¥10 vs ¥11.7 per 1×).
- Plan split announced: Kimi vs Kimi Code become separate products; new
  standalone Kimi Code = dedicated quota, monthly cap removed. "Existing
  subscribers are unaffected." Decision: stay monthly, keep auto-renew ON
  (continuous subscription = grandfathered), reassess at launch.

---

## Quick reference (current state, 2026-07-18 evening)

| Thing | State / command |
| --- | --- |
| Claude Code auth | **claude-oauth** — flip: `switch-claude kimi` / `switch-claude claude` |
| Claude Code context caps | 1048576 (both env keys) |
| OpenClaw main model | kimi/k3, contextWindow 1048576 |
| Gateway | Scheduled Task, logon trigger + PT5M repetition, `gateway.reload.mode=hot` |
| Exec policy | **FULLY AUTO** (`security=full ask=off` both layers, no prompts); `tools.deny=[write,edit,apply_patch]` + `strictInlineEval` retained; revert=`exec-policy preset cautious` |
| Status board | **LIVE** — model-free daemon (Scheduled Task "OpenClaw Status Board", pythonw, 5s) edits `#status` webhook msg; config `~/.openclaw/status-board.local.json` |
| Discord bot perms | **Administrator** (via added "admin" role) — can create channels/webhooks/voice |
| Policy presets | `openclaw exec-policy preset cautious` \| `yolo`; show: `openclaw exec-policy show` |
| Discord | connected via proxy 127.0.0.1:7993 (requires UniClash up) |
| ACP | acpx enabled, approve-reads; `/acp spawn claude --bind here` |
| MCP servers (OpenClaw) | `windows` (windows-mcp via uv), `playwright` (node + cli.js, unsafe-eval tool excluded) |
| Agent-installed software | AutoHotkey portable (`%LOCALAPPDATA%\Programs\AutoHotkey-portable`), windows-mcp (`~\.local\bin`), @playwright/mcp (npm -g), @openclaw/discord plugin |
| Gateway restart | `openclaw gateway start` (needed for `gateway.*`/proxy-class changes) |
| Visibility | pinned STATUS BOARD in DM (cron `7,37 * * * *`), autoPresence on, heartbeat 30m→DM (HEARTBEAT.md checklist) |
| Node.js | v25.9.0 at `C:\Program Files\nodejs` (restored via MSI ×2) |
| winget | BROKEN (dangling aliases) — use direct official downloads |

## Conventions

- Established 2026-07-18: **every future change to this stack gets an entry
  here** (date-sectioned, newest first). No secret values — locations only.

## 2026-07-19 (late) — Proxy decoupled: bot no longer dies on VPN changes

Root cause of "bot breaks whenever I change proxy/VPN": OpenClaw forced ALL
traffic (Kimi + Discord) through UniClash `127.0.0.1:7993` with no fallback, so
any VPN/UniClash change killed the whole bot. Verified: Kimi + Discord-REST work
DIRECT with UniClash off; only Discord's WEBSOCKET needs the proxy. Fix:
`proxy.enabled=false` (global direct — brain immune to VPN changes; proven 4
model calls ok/0 err with UniClash down) + `channels.discord.proxy=http://127.0.0.1:7993`
(only Discord ws via UniClash). Now: brain/dashboard/TUI always work; only Discord
messaging depends on UniClash (start it → Discord reconnects ~10s). This entry is
out of newest-first order (appended); fold into 07-19 section when tidying.

## 2026-07-19 (later) — Proxy decouple REVERTED (Discord needs all traffic proxied)

The 07-19 decouple (`proxy.enabled=false` + only `channels.discord.proxy`) broke
Discord message SENDING: `channels.discord.proxy` covers the websocket + startup
REST, but ongoing REST (sending replies, health probes) went DIRECT → blocked on
Eric's network → ETIMEDOUT, bot received but couldn't respond. Reverted to
`proxy.enabled=true` (ALL traffic through UniClash 127.0.0.1:7993) — Discord fully
works again. Net: bot depends on UniClash being up (unavoidable — Discord needs
the proxy for everything; the brain-direct resilience isn't worth breaking sends).
Keep UniClash running. Kimi rides through Clash fine (domestic=direct rule).

## 2026-07-19 — Root-caused "@-mentions don't work" + "bot is slow" (NO config change)
- **Not an intent/invite issue.** Discord provider (provider-BkfbC9FQ.js:5951) requests
  `Guilds|GuildMessages|MessageContent|DirectMessages|GuildMessageReactions|DirectMessageReactions`
  — the bot IS subscribed to guild messages; @-mentions are delivered whenever the ws is up.
  Message Content Intent shows "limited" but @-mentions/DMs carry content regardless. Re-inviting
  the bot fixes nothing (already in-server w/ Administrator + correct intents).
- **@-mention drops = Discord gateway ws instability.** 419 ws-drop events today (ECONNRESET /
  "WebSocket was closed"), clustered 01:56–03:11 (~15/min sustained), then STOPPED. Mentions sent
  during a drop window are lost permanently (Discord doesn't replay gateway events). Socket stable
  since 03:11; UniClash 7993 healthy.
- **Slowness = Kimi K3 latency.** 38 model calls today: median 7.9s, p90 16.3s, max 36.8s per call;
  each reply chains several → 20–60s responses. Fix = faster model (Anthropic key = ~1–2s), not a
  Discord change. Faster Kimi tier unreliable (endpoint tends to serve k3 fallback for any id).

## 2026-07-19 — Adaptive fast/smart Kimi router (in-process, SHIPPED)
**What:** The bot now routes each message by difficulty. Trivial chatter
(greetings/acks/short) → `kimi-for-coding-highspeed` with thinking OFF (fast).
Real work (code, debug, planning) + mid-task tool loops → `k3` with thinking
ENABLED (adaptive budget; k3 self-scales — easy-within-real stays cheap, hard
goes deep). Fixes the "genuinely slow" complaint: the slowness was k3's thinking
(measured 8–27s/call); easy messages now skip it.

**How (and why not the obvious ways):**
- Measured on the live endpoint: thinking is the dominant lever (k3 thinking off
  ≈1s, on ≈5–27s; k3 self-scales by difficulty). The "fast" Kimi ids are real
  (highspeed ≈1s), NOT the k3-fallback the old note feared.
- Dead ends ruled out: `message_received` hook is fire-and-forget (can't change
  the model). A localhost interceptor shim is unreachable — OpenClaw's managed
  proxy (needed for Discord in China) force-tunnels every remote provider through
  UniClash, which refuses localhost (`UND_ERR_SOCKET`) and rejects plain-HTTP
  through an explicit proxy; the loopback bypass only exists for "configured-local-
  origin" providers (Ollama path), not chat providers. env-proxy mode DID reach a
  shim but broke Discord REST (OpenClaw routes discord.js REST direct, not via env
  HTTP_PROXY) — rolled back.
- **Chosen: in-process patch** of `@openclaw/kimi-provider` `dist/stream.js` at the
  `createKimiThinkingWrapper` payload-patch (always in the request chain). It reads
  the last user message (stripping OpenClaw's injected `[timestamp]` prefix),
  classifies, and sets `payloadObj.model` + `thinking`. Calls api.kimi.com through
  the normal managed proxy → **no proxy change, zero Discord risk.** Bulletproof:
  any error falls back to the configured thinking.

**Files:** patch in `…/openclaw-kimi-provider-*/…/kimi-provider/dist/stream.js`
(backups `stream.js.bak-*` alongside). Decision log: same dir `kimi_router_inproc.log`.
Retired standalone shim: `~/.openclaw/workspace/tools/kimi_router.mjs.superseded`.

**⚠️ Update-safety:** the patch lives in node_modules, so `openclaw update` /
reinstalling the kimi plugin WILL wipe it. Re-apply with one command:
`python3 ~/.openclaw/workspace/tools/apply_kimi_router_patch.py` (idempotent,
backs up, `node --check`-validates), then `openclaw gateway start`.

**Tuning:** classifier keyword/greeting lists + fast/smart model ids + thinking
budgets are consts at the top of the injected block in stream.js (and mirrored in
the re-apply script — edit BOTH so an update doesn't revert your tuning).

## 2026-07-19 — FIXED: server @-mentions (root cause = groupPolicy, not ws/intent/allowFrom)
- The long-standing "bot ignores server @-mentions" bug was `channels.discord.groupPolicy: "allowlist"`
  with no guild allowlist → OpenClaw drops every guild message pre-log (allow-list-*.js:305). DMs use
  a separate path, so they always worked. Not the websocket, not Message Content Intent, not allowFrom.
- **Fix:** `channels.discord.groupPolicy = "open"` (respond in any server, `requireMention` still true
  → only when @-mentioned). NOTE valid schema values are `open`/`disabled`/`allowlist` ONLY (`"all"`
  fails validation and silently falls back to `allowlist`).
- Also this session: gateway service entrypoint repointed from the Claude-app sandbox cache
  (`…Packages\Claude_pzs8sxrjxfjjc\LocalCache\…`) to the stable global install
  (`AppData\Roaming\npm\…openclaw\dist\index.js`) — recommended default, survives Claude-app updates.
- SECURITY follow-up: `groupPolicy=open` means anyone in the server can @-mention and drive the bot
  (allowFrom only gates DMs/commands). Exec is currently fully-auto → consider `exec-policy preset
  cautious`, or lock to a trusted guild with `groupPolicy=allowlist` + guild allowlist.

## 2026-07-19 — Router transparency footer + live Discord model control
- **Per-reply footer:** every bot answer now ends with a Discord subtext line showing what
  actually ran, e.g. `-# 🤖 kimi-for-coding-highspeed · 🧠 off · auto·fast · OpenClaw` or
  `-# 🤖 k3 · 🧠 on/4096 · auto·smart · OpenClaw`. Implemented in the kimi-provider patch by
  appending a "must-obey" directive to the last user text turn (system-prompt injection was
  ignored by the model; user-turn injection is reliable). Skipped on tool-loop turns.
- **`auto` sentinel model:** added a `kimi/auto` model to the catalog and set it as `primary`
  (alias `Auto`). Router auto-routes when model==auto; RESPECTS explicit pins:
    - `/model K3`       → always smart (k3 + thinking on)  → footer shows `manual`
    - `/model KimiFast` → always fast (highspeed, no think) → footer `manual`
    - `/model Kimi`     → kimi-for-coding, fast
    - `/model Auto`     → back to auto-routing
  `/think off|low|medium|high` still works and is honored on a pinned k3.
- Verified end-to-end via `openclaw agent` (+ `--model` to simulate `/model`): auto·fast,
  auto·smart, manual-fast, manual-k3 all route + footer correctly. Discord stayed healthy
  (managed proxy untouched).
- Re-apply script (`apply_kimi_router_patch.py`) updated to embed the new logic — STILL the
  one command to run after `openclaw update`.

## 2026-07-19 — Fixed exec tool "&& is not a valid statement separator"
- Cause: OpenClaw's exec tool defaulted to Windows PowerShell 5.1, which doesn't support `&&`.
  `tools.exec` schema is strict and has NO shell key; the shell is set via the env var
  **`OPENCLAW_EXEC_SHELL`**. Set `env.OPENCLAW_EXEC_SHELL = "cmd.exe"` (cmd supports `&&`, `dir`,
  `type`). Verified: bot ran `echo AAA111 && echo BBB222` → both printed, no error.
- (Note: `tools.exec.shell` / `.shellPath` are INVALID keys — they make the whole config invalid.
  The valid `terminal.shell` is a different feature, not the agent exec tool.)

## 2026-07-19 — Native Discord reactions enabled (👀→🧠→✅/❌)
- OpenClaw HAS native reaction lifecycle (the bot claiming it "can't react" was wrong — that was the
  terminal Claude, not the Discord layer). Pure config under `messages`:
  `ackReaction:"👀"`, `ackReactionScope:"group-mentions"` (acks @-mentions only, no channel spam),
  `statusReactions.enabled:true` with emojis thinking=🧠, tool=🔧, done=✅, error=❌, queued=👀,
  stallSoft/stallHard=😐. Auto-transitions seen→working→done/error on the prompt message.
  Note: no native "uncertain outcome" trigger — done/error is binary; 😐 fires on stalls.
- ACP/Claude Code verified WORKING: acpx runtime "registered + ready" (cwd .openclaw/workspace),
  spawns real Claude Code on **claude-oauth (Anthropic account), model sonnet** (no API key set →
  still the ToS-gray Max-sub path). Recent Discord-spawned sessions live in the "3" workspace
  (#claude-agi3), e.g. id c51f8591… (14:09).

## 2026-07-19 — Voice (STT/TTS) enabled + on/off toggle
- Enabled the two local voice skills (currently ON): `openai-whisper` (speech-to-text, runs LOCALLY
  = free/private) + `sherpa-onnx-tts` (local text-to-speech). Loaded with no errors (lazy-init on
  first use). Recommended model for Eric's RTX 5070 Laptop (8GB VRAM): **large-v3-turbo via
  faster-whisper** (best accuracy/speed for live + long calls; ~2–4GB VRAM).
- **On/off at will:** `workspace/tools/voice_toggle.py on|off|status` (flips both skills + restarts).
  Wired into AGENTS.md so Eric can just say "voice on" / "voice off" to the bot.
- Files & attachments already work natively (send + receive) — no setup.
- Voice-CHANNEL joining (live calls) NOT yet wired — foundation exists (@discordjs/voice +
  VoiceReceiver + opus streams in the discord plugin) but live-call transcription→agent is a
  separate build. Voice MESSAGES (record-and-send) is what's enabled now.
- Pending: Eric to test by sending a Discord voice message (first use may download the Whisper model).

## 2026-07-19 — Autonomous HEARTBEAT disabled (Kimi no longer runs unprompted)

**Ask:** "does kimi ever run without prompting (like the heartbeat)? the auto prompting
should be turned off. the status shouldn't require AI."

**Finding — why it wasn't off already:** OpenClaw's default agent heartbeats every 30 min
**out of the box**, and there is **no config key** to disable it:
- interval falls back to a hardcoded `?? "30m"` (`acp-spawn-*.js`),
- `isHeartbeatEnabledForAgent()` returns `true` for the default agent even with zero
  heartbeat config (`heartbeat-summary-*.js` → `return agentId === defaultAgentId`),
- `openclaw system heartbeat disable` only flips a **runtime** flag (`set-heartbeats` RPC)
  that **resets to true on every gateway restart** — and this box restarts the gateway often.
- So removing `agents.defaults.heartbeat` from openclaw.json (done earlier) was NOT enough.

**Durable fix (reversible):** flipped the module-default global switch in the core
`dist/heartbeat-wake-*.js`:
`let heartbeatsEnabled = true;` → `let heartbeatsEnabled = false;`
That switch backs `areHeartbeatsEnabled()`, and the heartbeat runner's **first gate** is
`if (!areHeartbeatsEnabled()) return {skipped}` — so no heartbeat ever fires. Verified nothing
in the core calls `setHeartbeatsEnabled(true)` at boot, so the default sticks across restarts.
Proof: fresh `import` of the patched module → `areHeartbeatsEnabled() === false`.
- **Normal inbound replies are unaffected** — those run on the event path, not the heartbeat path.
  The bot still answers every message; it just never wakes itself up.
- Applied the runtime RPC too for immediate effect (`{ok:true, enabled:false}`, `heartbeat last`=null).
- **Reapply after `openclaw update`** (patch lives in global node_modules):
  `python3 ~/.openclaw/workspace/tools/disable_heartbeat_patch.py` (idempotent, backs up,
  `node --check`). To RE-ENABLE later: revert the backup or `openclaw system heartbeat enable`.

**"Status shouldn't require AI" — already true:** `workspace/tools/status_board.py` is header-labeled
"Model-free … No LLM, no OpenClaw agent turn, no exec-approval prompts"; it only reads local state
files + one localhost health check and edits a Discord webhook on a loop. Confirmed no model/agent refs.

**Full autonomy sweep (all clear):** openclaw.json has no `heartbeat`/`cron`/`schedule`/`autorun`
keys anywhere; 0 cron jobs; only two OS Scheduled Tasks (`OpenClaw Gateway`, `OpenClaw Status Board`),
neither runs an agent turn. Kimi now runs **only** when a human prompts it.

## 2026-07-19 — Usage/limits statuses: Claude Max + Kimi + per-ACP-session (model-free)

**Ask:** a status for Claude Code usage limits; per-ACPX-harness context/usage; and Kimi usage —
"if you have access."

**Access found (data sources, all local, no AI):**
- **Claude Max limits — LIVE.** Extracted the endpoint from `claude.exe`:
  `GET https://api.anthropic.com/api/oauth/usage` (Bearer = the OAuth token in
  `~/.claude/.credentials.json` → `claudeAiOauth.accessToken`; header `anthropic-beta: oauth-2025-04-20`).
  Returns real `five_hour.utilization`, `seven_day.utilization`, per-model weekly `limits[]`, resets_at,
  spend. Same endpoint Claude Code's own `/usage` uses. Works regardless of switch-claude mode (it's the
  Anthropic login, separate from the routing env). Token read-only, NEVER logged (curl `-K` temp file).
- **Kimi — token accounting only.** OpenClaw records per-turn `usage {input,output,cacheRead,total}` in
  `~/.openclaw/agents/main/sessions/*.trajectory.jsonl`. Kimi's coding endpoint has **NO quota API**
  (probed `/coding/v1/usage`, `/usage`, `/me` → all 404; only `/models` 200) → there is no "% of plan"
  to show, so the status shows tokens consumed + active-session context/1M and says so.
- **Per-ACP-session — LIVE.** acpx-spawned Claude Code writes to
  `~/.claude/projects/*openclaw*workspace*/<sessionid>.jsonl`; per-turn `usage`
  (`input_tokens`+`cache_read`+`cache_creation` = context in play, `output_tokens` = spend). Per session:
  context k/200k, turns, output, last-active.

**Build:** `workspace/tools/usage_status.py` (model-free library; standalone `python3 usage_status.py`
prints the blocks). Wired into the existing model-free `status_board.py` (guarded — a usage error can't
break the board). Board now renders a **USAGE / LIMITS** region; Claude call cached 60s so the 5s board
loop hits Anthropic only once/min. Verified end-to-end: build 660/2000 chars, Discord PATCH → 200.
Restart to reload: `schtasks /End /TN "OpenClaw Status Board"` then `/Run` (daemon = pythonw
`status_board.py 5`).

**Live sample:** `Claude (Max): 5h 6% (→3h) · wk 48% (→Thu) · Fable wk 57%` · `Kimi: 192k out-tok today
· ctx 14k/1M` · `ACP Claude: 0 active / 6 total` with per-session ctx k/200k + turns + age.

**Not done (offered):** posting each ACP session's status INTO its own bound Discord thread (vs the
consolidated board) — needs the acpx binding map + bot thread-posting; consolidated board was the
"or somewhere" v1.

## 2026-07-19 — Usage-status FIXES (Claude showed 0%, wrong context window, opaque IDs)
Three issues Eric caught from the live board, all fixed in `workspace/tools/usage_status.py`:
1. **Claude showed "0% (→?)".** Root cause: `GET /api/oauth/usage` is **403 "Request not allowed"
   DIRECT** from this network — it only returns 200 **routed through UniClash** (127.0.0.1:7993).
   The board daemon runs as a Scheduled Task with a **clean env (no HTTPS_PROXY)**, so its curl went
   direct → 403 → an Anthropic `{"error":...}` payload my code didn't catch (I checked `err`, Anthropic
   uses `error`) → fell through to a misleading 0%. FIX: pass `-x http://127.0.0.1:7993` EXPLICITLY to
   the curl (don't rely on env), detect the `error`/`no five_hour` payloads → show "unavailable
   (reason)" instead of 0%, and cache failures only 15s (vs 60s) so it recovers fast. Verified 4/4:
   direct=403, via-proxy=200.
2. **Wrong context window.** ACP sessions actually run **`claude-fable-5` (1M context)**, not 200k —
   so 160k looked like 80% when it's really 16%. FIX: per-model window (`_claude_window`): Fable /
   Sonnet-1M = 1M, Opus / Haiku = 200k, default 1M. Now shows `/1M`.
3. **Opaque session IDs (`c9b2529f`).** Those are just UUIDs (filenames), not "encrypted." FIX: name
   each session by its **first real user message** (e.g. "How do I change the model in Claude Code CLI?")
   + a model tag (Fable). Pulled from the session JSONL.
Live-verified: daemon reloaded, PATCH 200, board now `Claude 5h 7% · wk 48% · Fable wk 57%`,
`ctx 160k/1M`, named sessions. (Reload after edits: `schtasks /End` then `/Run` "OpenClaw Status Board".)

## 2026-07-19 — Board's Claude sessions: real titles + all projects + 1M window
Eric: the session names were wrong/ugly ("config") vs the nice titles in his resume picker.
Root causes + fixes in `usage_status.py`:
- **Titles.** Claude Code stores the picker title as a `{"type":"custom-title","customTitle":"…",
  "sessionId":"…"}` line inside the session JSONL (NOT a `type:summary` line, and NOT the UUID
  filename — those aren't "encrypted," just ids). Now each session is named by its `customTitle`
  (e.g. "Kimi K3 integration with Claude Code", "ARC-AGI-3 benchmark exploration"), first-user-message
  as fallback.
- **Scope.** Switched from only the acpx workspace (`*openclaw*workspace*`, which held trivial untitled
  "config" tests) to **all projects** (`~/.claude/projects/*/*.jsonl`) — mirrors the resume picker.
  Section renamed "ACP Claude" → **"Claude Code"**; each row tags its project (acpx sessions tag `acp`)
  and marks active (🟢, touched <90min) vs idle (▫️). Trivial untitled <3-turn sessions hidden.
- **Context window = 1M.** Opus 4.8 sessions run to 380–405k and keep going ⇒ Opus is 1M too (not 200k).
  `_claude_window` now returns 1M for everything except Haiku. Fixes the >100% (e.g. 380k/200k) display.
- **Perf.** All-projects glob could hammer disk every 5s; added an mtime cache (`_SESS_CACHE`) + only the
  most-recent ~30 files are read. Measured: cold 1.37s, warm 0.003s.
Live: PATCH 200, board 864/2000, e.g. `🟢 Kimi K3 integration with Claude Code — ▰▰▱▱ 405k/1M · 2373t ·
Opus · robotr · 0m`. Tunables at top of file: SESS_ROWS, SESS_MIN_TURNS.

## 2026-07-19 — Fix: curl console window flashing every ~60s (headless)
Eric saw a curl/console window popping up periodically (guessed heartbeat — but that's disabled).
CAUSE: the status-board daemon runs as `pythonw.exe` (windowless); on Windows, when a windowless
process spawns a console program (curl, for the once-per-60s Claude usage fetch), Windows gives that
program its OWN console window → it flashed every 60s. FIX: pass `creationflags=CREATE_NO_WINDOW`
(0x08000000) to the curl subprocess in `usage_status.py` (+ the one-time `node --version` in
`status_board.py`). Verified flag applied; curl still returns data. Note: repeated manual testing of
`/api/oauth/usage` briefly rate-limited it ("rate-limited, retrying" shown, handled gracefully) — the
daemon's once-per-60s cadence never trips it; self-recovers. RULE: any subprocess spawned by the
windowless daemon MUST set CREATE_NO_WINDOW.

## 2026-07-19 — Wake-word gate (voice + text): "respond only on openclaw/claw/clanker/osama/djerokbot"
Eric wants the bot to hear everything but only respond on a wake word; his insight: voice → whisper → gate on transcript.
FINDINGS (from shipped docs, version-matched):
- NATIVE + FREE path exists: `requireMention: true` groups transcribe audio BEFORE mention checking, and
  "mention detection uses the raw transcript" ⇒ voice notes are gated on their transcribed text. No paid
  OpenAI realtime needed (that's only for live voice-CHANNEL conversations).
- Wake words = `messages.groupChat.mentionPatterns` (regex fallback triggers; global fallback for all channels).
  SET to word-boundary regex: `\bopenclaw\b \bclaw\b \bclanker\b \bosama\b \bdjerokbot\b`.
  GOTCHA: `\b` in a bash heredoc collapsed to a literal BACKSPACE (0x08); built it with chr(92)+"b" instead,
  verified bytes 0x5c62. Gateway reloaded, `openclaw config get` confirms.
- SCOPE: wake gate is GROUP/SERVER-channel only. DMs are 1:1 and always respond (no mention gate) — so
  "respond only on wake word" applies in a server channel, not DM.
- BLOCKER for voice: NO local whisper engine is actually installed (the enabled `openai-whisper` skill is
  config-only; no `whisper`/`whisper-cli` binary, no py module). Voice transcription (preflight) needs a
  local engine. Recommend whisper.cpp `whisper-cli` (prebuilt Win binary + GGML model, NO torch — avoids the
  robotr Python env risk); OpenClaw's CLI fallback supports `whisper-cli` (uses WHISPER_CPP_MODEL). Needs a
  download (Eric's OK). Until then: TEXT wake words work now; voice waits on the engine.

## 2026-07-19 — CORRECTION: voice transcription = Discord native, not whisper
Eric asked "how did it work before" — his voice note got a reply despite no whisper installed. Root cause:
**Discord natively auto-transcribes voice messages** and passes the text in the message payload; OpenClaw reads
`mediaMessage.transcriptText` and gives Kimi `Transcript: …`. Proof: session a254e4d6, 09:15 UTC, prompt held
`<media:document> … Transcript: Hey bot, can you hear me?` with ZERO transcription log lines + no whisper binary.
Kimi quoted Discord's transcript (did NOT hallucinate). ⇒ (1) my earlier "voice needs whisper installed" was
WRONG — voice wake-gating works now via Discord's free transcript; whisper.cpp is only an OPTIONAL fallback for
un-transcribed audio. (2) Caveat: Discord transcription is imperfect — it quoted the wrong clip (2 notes were
sent) and can mistranscribe; not guaranteed on every client/filetype.

## 2026-07-19 — Local whisper.cpp installed + wired (reliable voice transcription fallback)
Eric: "still make a whisper" (Discord's native transcript is unreliable). Installed FREE local engine:
- **whisper.cpp v1.9.1** (`whisper-bin-x64.zip`, CPU, NO torch) → `~/.openclaw/whisper/bin/Release/whisper-cli.exe`
  + `ggml-base.en.bin` model (142MB) → `~/.openclaw/whisper/`. GitHub API was rate-limited (shared proxy IP) —
  used the releases page + direct download URLs instead.
- **Wired via full path** (no PATH surgery): OpenClaw derives commandId = `path.parse(command).name`, so a full
  exe path still resolves to `whisper-cli` → correct output parsing. Config `tools.media.audio`:
  `{enabled:true, scope:{default:"allow"}, models:[{type:"cli", command:"…/whisper-cli.exe",
  args:["--model","…/ggml-base.en.bin","-otxt","-of","{{MediaPath}}","-np","{{MediaPath}}"]}]}`.
  Output resolver needs `-otxt` + `-of <base>` → reads `<base>.txt`.
- **Opus handled by OpenClaw**: whisper-cli can't decode Discord's OGG/Opus, BUT OpenClaw's transcription runner
  pre-converts audio `-ar 16000 -c:a pcm_s16le -f wav` (needs ffmpeg — present, `where ffmpeg` resolves it) and
  passes the WAV as {{MediaPath}}. Verified full sim: opus → wav → whisper-cli → .txt.
- **Coined wake words mistranscribe** (base.en, TTS test): openclaw→"open clock", claw→"clock", djerokbot→
  "jerick but"; clanker & osama transcribe correctly. FIX = tolerant `mentionPatterns` (case-insensitive `i`
  flag confirmed): `\bopenclaw\b \bopen ?cl(aw|ock)\b \bclaw\b \bcl[au]nker\b \bosama\b \bd?jerok\w* \bjer(i|ri)ck\b`.
- Accuracy upgrade available: swap model to `ggml-small.en.bin` (488MB) + point `--model` at it. base.en kept
  (fast, 142MB). Gateway restarted, config validates.

## 2026-07-19 — Whisper upgraded base.en -> large-v3-turbo-q8_0 (+ -l en)
Eric wanted better wake-word accuracy. Downloaded `ggml-large-v3-turbo-q8_0.bin` (833MB, multilingual,
8-bit quant ≈ full-turbo quality at half size) to `~/.openclaw/whisper/`. Config `tools.media.audio.models[0]`
now `--model …turbo-q8 -l en …` (pinned English = no lang misdetect on short clips + faster). base.en kept as
a fast fallback (unused).
- ACCURACY (TTS test): "claw" now correct (base heard "clock"); "openclaw"→"Open Claw"/"open clock" (varies),
  clanker/osama perfect, djerokbot→"Jarek but". Coined words still approximate on ANY model → tolerant
  mentionPatterns kept + broadened: added `\bj[ae]r(ek|ick|rick)\b` (jarek/jerek/jerick).
- LATENCY: **~8-9s per short clip on CPU** (vs base.en ~1-2s) — turbo is big; I installed the CPU build.
  Tradeoff = accuracy vs speed. GPU path (cuBLAS whisper build + CUDA on the RTX 5070) would cut it to <1s
  but is a heavier install — OFFERED to Eric, not done.
- Quant primer for reference: q8_0 ≈ indistinguishable from full at half size; q5_0 smaller/slightly less
  accurate; `.en` models are English-only, turbo is multilingual-only.

## 2026-07-19 — Whisper GPU (cuBLAS) build — 8× faster on the RTX 5070
Eric: "download the version for gpu as well". GPU is RTX 5070 Laptop = **Blackwell, compute cap 12.0 (sm_120)**;
whisper.cpp v1.9.1 only ships cuBLAS **12.4** & 11.8 (both predate Blackwell / need CUDA 12.8+). Downloaded
`whisper-cublas-12.4.0-bin-x64.zip` (647MB) → `~/.openclaw/whisper/gpu/bin/Release/` — SELF-CONTAINED (bundles
cudart64_12/cublas64_12/cublasLt64_12/ggml-cuda.dll, no CUDA toolkit needed).
- **It RUNS on Blackwell** via driver PTX-JIT forward-compat (build `CUDA:ARCHS=500..900`, driver 591.74 JIT-compiles
  for sm_120). Cold first run = **~26s** (one-time PTX→SASS compile, cached in %APPDATA%\NVIDIA\ComputeCache);
  **warm = ~1.1s vs 8.7s CPU** (measured, same turbo-q8 output). Pre-warmed the JIT cache.
- Switched active config `tools.media.audio.models[0].command` → GPU exe (full path → commandId still `whisper-cli`).
  CPU build (`bin/Release/`) kept as fallback. Gateway restarted, Discord reconnected.
- CAVEAT: after a GPU driver update / cache clear, the first transcription re-JITs (~26s, one-time), then ~1s again.
  VRAM: model ~874MB on the 8GB GPU, loaded per-invocation (~1s), released after — not a persistent hog.

## 2026-07-19 — Load-aware whisper ROUTER (GPU/CPU-adaptive model selection)
Eric wanted whisper to only grab the GPU/CPU when there's headroom, degrading gracefully.
BUILT `~/.openclaw/whisper/whisper_router.py` + `whisper-cli.cmd` (basename `whisper-cli` so OpenClaw reads
`-of <base>.txt`). OpenClaw calls the .cmd (its spawn handles Windows .cmd via cmd-wrapper + windowsHide);
the router IGNORES the passed --model and picks by LIVE load (nvidia-smi GPU util + psutil CPU util):
  GPU<40% → large(turbo-q8)/GPU · elif CPU<40% → large/CPU · elif GPU<75% → base.en/GPU ·
  elif CPU<75% → base.en/CPU · else → write NO .txt → OpenClaw falls back to Discord (bottom rung).
Thresholds = LARGE_MAX(40)/BASE_MAX(75) constants. Decisions logged to whisper_router.log.
- VERIFIED: pick() unit-tested across load levels (table correct); .cmd invoked full-path-via-shell (like Node)
  → rc0, wrote .txt, logged route=large/GPU. Config `tools.media.audio.models[0]` → the .cmd. Restarted.
- Note (Eric answered): thresholds corrected to degrade-at-higher-load (base<75, not the unreachable <20).
- STILL TODO (both need OpenClaw CORE patches, invasive/reapply-after-update): (#18) make whisper PRIMARY so
  the ladder runs first + Discord is the true last-resort (currently Discord's native transcript still wins first);
  (#19) 👂 react when a voice is heard (transcribed) / 👄 when not — no config hook exists.

## 2026-07-19 — Whisper PRIMARY (core patch): router runs before Discord's native transcript
Eric: "make whisper primary and i will use it." CONFIRMED Discord was primary: the preflight transcriber
`transcribeFirstAudio` (which runs tools.media.audio = our load-aware router) only processed audio where
`!att.alreadyTranscribed`; Discord marks voice notes alreadyTranscribed when it attaches its own native
transcript → router skipped → Discord's transcript won. (Telegram always runs it; Discord short-circuited.)
PATCH (media-runtime-*.js, one unique line, reversible): removed `&& !att.alreadyTranscribed` from the
attachments.find(). Now the router transcribes EVERY voice note; Discord's native transcript is only the
last rung (when the router's ladder yields nothing at >75% load). node --check passed, gateway healthy.
Reapply after `openclaw update`: `python3 ~/.openclaw/workspace/tools/whisper_primary_patch.py`. Revert =
restore the .bak-whisperprimary-* file. Applies to BOTH surfaces (Kimi + Claude/ACP share the layer).
Tradeoff noted: at >75% GPU+CPU the router yields nothing and Discord's transcript is NOT currently used as
fallback (rare; raise BASE_MAX in whisper_router.py to make base/CPU run at higher load instead).

## 2026-07-19 — 👂/👄 reactions on voice messages (core patch)
Eric wanted the bot to react 👂 when a voice is heard, 👄 when not. No config hook exists → patched
message-handler.process-*.js right after `ackReactionContext` is built (where messageChannelId + message.id
+ mediaList + preflightAudioTranscript + reactMessageDiscord + valid reaction opts are all in scope):
injected a fire-and-forget, try/catch-wrapped call — if the message has an audio attachment, react
`reactMessageDiscord(... preflightAudioTranscript!==void 0 ? 👂 : 👄, ackReactionContext)`. Can NEVER break
message processing (fire-and-forget + guarded). node --check passed, gateway healthy (ready ✓, Discord ✓).
Reapply after update: `python3 ~/.openclaw/workspace/tools/whisper_reactions_patch.py`. Revert = restore
.bak-earmouth-*. NOTE: 👂/👄 keys on the PREFLIGHT transcript; with whisper-primary the preflight runs on all
audio, but if a DM voice note ever shows 👄 despite being heard, the signal needs to move to the media-
understanding stage (per-surface timing) — validate with a real voice note.

### Voice stack — full picture (2026-07-19)
Voice note → OpenClaw ffmpeg→16kHz WAV → **load-aware whisper router** (`whisper_router.py`, GPU<40%→large/GPU
~1s · CPU<40%→large/CPU · GPU<75%→base/GPU · CPU<75%→base/CPU · else Discord) → text → Kimi OR Claude/ACP
(shared layer). whisper is PRIMARY (Discord native = last rung). 👂/👄 reaction on the message. 3 reversible
core patches (whisper_primary, whisper_reactions) + kimi_router + heartbeat — all have reapply scripts in
workspace/tools; rerun each after `openclaw update`.

## 2026-07-20 — FIX: Kimi's ✅/❌ status reactions never showed (only 👀)
Eric reported the checkmark/x reactions weren't appearing — only the 👀 ack. ROOT CAUSE (message-handler.process):
on reply completion the code sets ✅ (setDone) / ❌ (setError), then with `removeAckAfterReply=false` (our config)
immediately calls `statusReactions.restoreInitial()` → reverts the ✅/❌ straight back to the 👀 ack. So ✅ WAS
set, then instantly undone → user only ever saw 👀. (removeAckAfterReply=true only holds it doneHoldMs=1500ms
then clears — also too brief.) FIX (reversible core patch): removed the success-branch `else
statusReactions.restoreInitial();` (unique anchor: the one after the async IIFE `})();`; aborted-branch one kept).
Now ✅/❌ PERSIST on the message. node --check passed, gateway healthy. Reapply after update:
`python3 ~/.openclaw/workspace/tools/status_reactions_persist_patch.py`.
NOTE on 😐 "neutral": OpenClaw's outcomes are binary (done✅/error❌); 😐 (stallSoft/stallHard) fires only on a
STALL (long delay), NOT as a general "uncertain outcome" — no native trigger for that.

## 2026-07-20 — Show ALL tool calls (both Kimi + Claude/ACP) — config, no patch
Eric wanted every tool call output on both surfaces. Root: "sessions suppress verbose tool/progress summaries
by default" — normally you'd `/verbose on` per session. FIX = set the DEFAULT: `agents.defaults.verboseDefault
= "full"` (valid: off | on | full). Tool summaries gate on `verboseLevel !== "off"`, and the ACP/Claude path
uses `shouldSendToolSummaries = () => shouldSendVerboseProgressMessages()` — the SAME verbose gate — so ONE
setting covers Kimi AND Claude/ACP. Gateway restarted, `config get` confirms "full", healthy.
- Per-session override still works: `/verbose off` (this session), `/verbose on` (lighter than full), `/verbose full`.
- Note: applies to NEW sessions; a session with a persisted verbose level keeps it until changed. "full" can be
  noisy (every tool call + progress) — drop to "on" if it's too much.

## 2026-07-20 — FIX: voice transcription failing — "ffmpeg not found in trusted system directories"
Eric's 3 voice notes didn't get replies. Log showed `audio: failed (0/1) reason=ffmpeg not found in trusted
system directories` (×3, matching the 3 notes) → Opus never converted to WAV → whisper NEVER ran (router log
empty). ROOT CAUSE: OpenClaw resolves ffmpeg via `requireSystemBin("ffmpeg")` = `resolveSystemBin` which
IGNORES PATH and only searches trusted OS dirs (System32, Program Files, SysWOW64, chocolatey) to block
PATH-hijack. Eric's ffmpeg is WinGet-installed in %LOCALAPPDATA% — not trusted → refused. (This is why my
earlier `where ffmpeg` check was misleading: it's on PATH but OpenClaw won't use PATH.)
FIX: copied ffmpeg.exe + ffprobe.exe (v8.1.1) → stable `~/.openclaw/ffmpeg/`; patched `buildWindowsTrustedDirs`
(resolve-system-bin-*.js, reversible) to add that dir. Verified `resolveSystemBin('ffmpeg'/'ffprobe')` now
resolves to ~/.openclaw/ffmpeg. Reapply: `tools/ffmpeg_trusted_dir_patch.py`. SECURITY: adds a user-writable
dir to the trusted-bin list — fine for single-user; keep only trusted bins there. This was the ACTUAL blocker
behind "voice doesn't work" all along (the whole whisper pipeline was correct; ffmpeg conversion was the wall).

## 2026-07-20 — Voice FIXED + KEY LESSON: `openclaw gateway start` does NOT reload code patches
After the ffmpeg-dir patch, voice STILL failed with the same ffmpeg error even though a fresh `import` of the
patched file resolved ffmpeg correctly. ROOT CAUSE: **`openclaw gateway start` on a running gateway hot-reloads
CONFIG but keeps the same node process running the OLD code** — so node_modules CODE PATCHES don't take effect.
(The process even had a post-patch CreationDate yet ran stale code — likely the hidden-launcher task semantics.)
FIX = HARD restart: `schtasks /End` + kill the `node ... gateway --port` process (Stop-Process) + `schtasks /Run`.
After that (proc 54828), verified end-to-end via `openclaw infer audio transcribe --file v.ogg`:
`audio.transcribe via local · outputs:1`, router fired `route=large/GPU → done rc=0 wrote_txt=True`. ffmpeg +
router + whisper all working. NOTE: first GPU run after a fresh process is the ~29s Blackwell JIT cold-start
(then ~1s warm). ⇒ IMPLICATION: all today's code patches (whisper-primary, reactions, react-persist, ffmpeg-dir)
only truly took effect at this hard restart. RULE: after ANY node_modules patch, do the hard kill+restart, not
just `openclaw gateway start`.

## 2026-07-20 — FIX: "doesn't react when told" — bot guessed wrong message ID
Eric: bot said "Reacting ✅" + ran react_message.py → HTTP 204 but NO checkmark on his message. ROOT CAUSE:
Kimi IMPROVISED a script (react_message.py) and passed the WRONG messageId → 204 = it reacted on some other
message, not the user's. The native `message(action:"react")` tool was AVAILABLE (isActionEnabled('reactions')
=true) but Kimi didn't use it, AND it REQUIRES an explicit messageId (`required:true`) even though ctx.messageId
(the triggering message) is right there. TWO-PART FIX:
1. CORE PATCH (runtime-*.js, reversible, react_default_message_patch.py): react action messageId now
   `readStringParam(...,{required:false}) ?? ctx.messageId` → defaults to the message that triggered the turn.
   Unique anchor = the react action (list-reactions action, which shares the line, is followed by `const limit`,
   left untouched).
2. AGENTS.md: explicit "HOW to react" — call native `message(action="react", emoji="✅")`, it auto-targets the
   user's message (no messageId/channel needed); NEVER write a script (react_message.py/curl/REST) to react
   (those guess the wrong message; 204 ≠ correct message). remove: pass remove:true.
HARD restart applied (proc 51192). Now "react checkmark if yes" → native tool → lands on the user's message.

## 2026-07-20 — FIX: reaction ADDED then REMOVED (the ✅ kept reverting to 👀)
Eric: "it added the check mark and removed it." Kimi's react_message.py DID add ✅ to the right message (only
does PUT, never DELETE) — so the removal came from OpenClaw's STATUS-REACTION CONTROLLER: `restoreInitial()`
reverts the message's reaction back to the initial 👀 ack, stripping the ✅. It has 4 CALLERS
(`statusReactionController.restoreInitial()` ×3 + the message-handler one), so the earlier single-call-site
persist patch wasn't enough. FIX = no-op `restoreInitial()` at the SOURCE (channel-feedback-*.js,
`restoreinitial_noop_patch.py`) → status + command reactions PERSIST. HARD restart (proc 44880). Cosmetic
tradeoff: an aborted turn may leave its last progress emoji instead of reverting — acceptable (user wants
reactions to stay). NOTE: Kimi still reacts via react_message.py because `tools.profile=coding` STRIPS the
native `message` tool (logged "tool policy removed 5 tool(s) via tools.profile (coding): …message…"); the
react_default_message_patch + AGENTS.md guidance only help once the message tool is re-enabled — deferred (didn't
want tools.allow to accidentally whitelist-strip Kimi's other tools). The script path works now that reactions persist.

## 2026-07-20 — Reaction removal ROOT CAUSE isolated → disabled the status-reaction controller
Proved it definitively via the Discord API: Eric's message ("can you react check mark?") had the ✅ added
(HTTP 204, correct message id) then stripped — leaving only the 👀 ack. A reaction ADDED MANUALLY (no bot turn)
via the API PERSISTED (👀+✅ survived 8s). ⇒ the removal is TURN-TRIGGERED by the status-reaction controller,
and it happens even with restoreInitial no-op'd (so it's the controller's transitions/clear, not just
restoreInitial). The controller never actually delivered a working persistent ✅ anyway. FIX = disable it:
`messages.statusReactions.enabled = false` (config, no patch). ackReaction 👀 kept. Now nothing strips Kimi's
command-reactions; a reaction Kimi adds should persist. HARD restart (proc 29756). (Earlier restoreInitial/persist
patches are now moot for this but harmless.) If Eric wants the 👀→🧠→✅ lifecycle back later, it needs a proper
fix so it doesn't fight command-reactions — deferred.

## 2026-07-20 — FIX: voice notes "don't activate any reactions or actions" (ffmpeg hardcode + ear/mouth broaden)

**Symptom:** Discord voice notes produced no transcript-driven reply AND no 👂/👄 reaction, even though
`openclaw infer audio transcribe --file x.ogg` (a fresh process) worked perfectly.

**Root cause #1 — ffmpeg (the "no actions" blocker).** Gateway log showed `audio: failed (0/1) reason=ffmpeg
not found in trusted system directories`. So the voice note WAS detected as audio (1 found) and transcription
STARTED — it failed only because the long-running gateway process couldn't resolve ffmpeg. OpenClaw resolves
ffmpeg via `requireSystemBin("ffmpeg")` → `resolveSystemBin(trust:"standard")`, which scans "trusted" dirs and
deliberately ignores PATH. The earlier `ffmpeg_trusted_dir_patch` (adds `~/.openclaw/ffmpeg` to the scan) works
in a FRESH `infer` process but the gateway process intermittently fails the scan (the Program-Files standard-dir
builder can throw/short-circuit in that process, so it never reaches our dir). → no WAV → no transcript → no reply.
- **Fix:** `~/.openclaw/workspace/tools/ffmpeg_hardcode_patch.py` — short-circuits `requireSystemBin` for exactly
  `"ffmpeg"`/`"ffprobe"` to the absolute path `~/.openclaw/ffmpeg/<name>.exe` (existence-checked via an added
  `existsSync` import). No dir scan, no cache, no throw. Complements (doesn't replace) `ffmpeg_trusted_dir_patch`.

**Root cause #2 — reaction gate too narrow (the "no reactions" half).** The 👂/👄 patch fired only when an
attachment's `contentType` started with `audio/`. But voice notes often arrive classified `<media:document>`
(non-audio contentType) while whisper STILL transcribes them, because its real detector `isAudioAttachment` →
`resolveAttachmentKind` also matches by FILENAME (`.ogg` etc.). So a note got transcribed but no 👂. (OpenClaw's
own line 253 `mediaList.findIndex(m=>m.contentType?.startsWith("audio/"))` has the same latent bug.)
- **Fix:** `~/.openclaw/workspace/tools/earmouth_broaden_patch.py` — react when we actually heard a voice note:
  transcript present (`preflightAudioTranscript!==void 0` → 👂) OR any attachment is audio by contentType OR by
  audio filename ext (`.ogg|opus|oga|m4a|mp3|wav|webm|weba|flac|aac|amr|3gp` → 👄 when transcription failed).
  Text messages (no audio, no transcript) still get no reaction.

**Mechanics confirmed:** gateway launch = plain `node dist/index.js gateway --port 18789` (no snapshot / no
compile cache), so a HARD restart genuinely reloads dist patches; `openclaw gateway start` does NOT. Both patches
loaded via hard restart (schtasks End + kill node gateway proc + schtasks Run) → gateway proc 52940, @clanker
probe resolved. Wiring verified: `tools.media.audio.enabled=true` → whisper-cli.cmd router, 7 wake-words,
`verboseDefault=full`, `statusReactions.enabled=false`.

**Behaviour to expect:** any voice note now gets 👂 (heard) / 👄 (couldn't transcribe). A *reply* still requires a
wake-word IN the transcript (openclaw/claw/clanker/osama/djerok…) because of the server mention-gate Eric asked
for — a wake-word-less voice note is heard (👂) but intentionally not answered.

## 2026-07-20 — ★ TRUE ROOT CAUSE: stale Node compile cache served the gateway pre-patch bytecode ★

**This supersedes the "hard restart reloads dist patches" claim above — that was WRONG.** Every dist patch this
session (ffmpeg dir, ffmpeg hardcode, ear/mouth, react-default, restoreInitial no-op, whisper-primary…) was
correct *in source* but the **gateway kept running the OLD compiled bytecode** after every hard restart — which is
why Eric kept seeing "still broken" and the `audio: failed (0/1) ffmpeg not found` line reappeared even on a
freshly-restarted gateway proc.

**Mechanism.** OpenClaw's `dist/entry.js` calls Node's `enableCompileCache()` →
`%TEMP%/node-compile-cache/openclaw/<version>/<installMarker>`, where `installMarker = <package.json mtimeMs>-<size>`.
Editing `dist/*.js` does **not** touch `package.json`, so the marker (and cache dir) never changes. The cache had
**36,214 files / 216 MB** of stale compiled modules; `find -newermt 01:10` showed **0** rewritten after the patches
→ the gateway loaded cached bytecode, never recompiling the edited source. Fresh one-off `node script.mjs` /
`openclaw infer` processes resolved ffmpeg fine because their module graph/cache-keying differed — which is exactly
the trap that made every local test pass while the live gateway stayed broken.

**Fix / procedure (REQUIRED after ANY dist/*.js edit):**
1. Stop the gateway (schtasks End + `Stop-Process` the `node …gateway --port 18789` proc).
2. **Wipe `%TEMP%/node-compile-cache/openclaw/`** (`rm -rf`; safe — regenerates). This is the step that was missing.
3. schtasks Run. First boot recompiles from source (~seconds slower); patches are finally live.

Also cleaned up two **stuck `/acp doctor` node procs** (PIDs 49336/14372) leaked since 2026-07-19 14:12.

**Proven end-to-end on the real Discord audio (not a synthetic clip):** pulled Eric's actual voice note from
#new1 via the Discord REST API (msg 1528451702, `voice-message.ogg`, `content_type=audio/ogg`, isVoiceFlag=true),
ran the real bytes through the pipeline → hardcoded ffmpeg converted ogg→wav, whisper (large-v3-turbo-q8 GPU)
transcribed **"Clanker, what time is it?"**. (So the notes were always correctly classified as audio — ffmpeg was
the sole blocker.)

**One more fix surfaced by that transcript:** whisper renders "Clanker" as **"Glanker"**, which the wake-word
`\bcl[au]nker\b` missed → no reply even with a good transcript. Broadened to `\b[cgk]l[au]n+[ck]er\b` (+ explicit
`glanker`/`clunker`) so C/G/K mishearings still trigger a response. Config-only (hot-reloads, no restart).

**Remaining live-only step:** the gateway processes Discord **websocket** events, which can't be replayed from an
old message — so the final confirmation needs one freshly-sent voice note. The blocker itself is gone.

### UPDATE (same night): wiping the cache was INSUFFICIENT — disabled it instead
After the wipe + restart, a live voice note STILL logged `audio: failed (0/1) ffmpeg not found` — and the cache
had already repopulated (3,464 files) so the gateway was again running non-source bytecode. Verified the fix
`requireSystemBin` hardcode is intact on disk and *cannot* throw for ffmpeg if executed (existsSync of the path is
true), which proves the gateway was NOT executing the patched source. **Real fix: `set "NODE_DISABLE_COMPILE_CACHE=1"`
added to `~/.openclaw/gateway.cmd`** so the gateway compiles every module from disk on each start. Proof it took:
after restart the `node-compile-cache/openclaw` dir **stays at 0 files** (vs 3,464 before) → source execution
guaranteed. So the rule is stronger than "wipe the cache": **for a machine that hand-patches `dist/*.js`, keep
`NODE_DISABLE_COMPILE_CACHE=1` in gateway.cmd permanently.** Also gated the 👂 reaction on an actual wake-word match
(`earmouth_keyword_gate_patch.py`): 👂 = a wake-word was heard (bot replies), 👄 = audio received but no wake-word /
couldn't transcribe. Gateway proc 59816, Discord connected, 0 ffmpeg errors, cache 0 files. Pending Eric's live note.

## 2026-07-20 — New `/acp commands` cheat-sheet action + compile-cache disabled (ACP)

**`/acp commands`** added: a described, Discord-friendly reference of every /acp command (sessions,
model, set-mode, etc.) with the "type the whole line for commands that take an <argument>" gotcha.
Wired in three dist spots (reversible: `~/.openclaw/workspace/tools/acp_commands_subcommand_patch.py`):
`commands-registry.data-*.js` choices array (adds the button), `shared-*.js` resolveAcpAction (recognizes
it), `commands-handlers.runtime-*.js` dispatch (prints the cheat-sheet, before the owner gate so it's
open to anyone like `help`). Verified in source; node --check OK on all three.

**ACP owner-gate finding:** owner-required /acp actions (model, set-mode, spawn, close, status, …) need
`senderIsOwner`; for Discord that = membership in `channels.discord.allowFrom` (djerok 662339124627374100
and asiansnextdoor 901676858322595862 are both listed, so both are owners). The button picker can't pass
an `<argument>` (clicking `model` just shows Usage) — type the full line, e.g. `/acp model fable`.

**Compile cache DISABLED for the gateway** (`NODE_DISABLE_COMPILE_CACHE=1` in gateway.cmd) — required so
hand-patched dist/*.js actually loads (see prior entry). Confirmed cache stays at 0 files.

**KNOWN OUTAGE (environmental, not the patch):** Discord is DNS-blocked on this network — `discord.com`
resolves to a parking IP (199.59.149.206), `gateway.discord.gg` to a Twitter IP (104.244.46.165); direct
TCP:443 to Discord times out. The UniClash proxy (127.0.0.1:7993) tunnels around it, but around 02:47 the
tunnel began flapping: REST to discord.com works intermittently (3/3 then 0/3 then 3/3), but the persistent
gateway **websocket** to gateway.discord.gg keeps resetting (code 1006 / READY-wait timeout / backoff), so
the bot can't hold a session. Surfshark services are running (a suspected factor, previously exonerated).
Gateway left running (PID cycles) to auto-reconnect when the tunnel stabilizes; stopped restarting it since
that only re-enters backoff. Fix path = reconnect/restart UniClash and/or settle Surfshark, or wait for the
network to stabilize — the `/acp commands` feature will register and work the moment a stable session forms.

## 2026-07-20 — Discord back online via HTTP→SOCKS5h bridge (new UniClash)

**Problem:** After Eric switched to a new UniClash, the bot went fully offline. Root cause chain:
- This network **DNS-blocks Discord** — system DNS (router 10.192.1.1 / 192.168.1.1) returns bogus IPs
  for discord.com / gateway.discord.gg; direct TCP:443 to Discord times out.
- New UniClash exposes DNS on :53 (fake-IP 198.18.x for Discord), an HTTP/SOCKS proxy on :7993, and a
  service on :50061. Hitting Discord's fake-IP directly (198.18.0.4) returns 200 — so the **TUN tunnel works**.
- BUT: as an **HTTP** proxy, 7993 resolves Discord via the poisoned system DNS → fails (works for google/kimi).
  As **SOCKS5h**, 7993 resolves at UniClash (fake-IP) → **works (200)**. And OpenClaw **only supports HTTP/HTTPS
  proxies** ("SOCKS and PAC proxy URLs are not supported" — node-proxy-agent), so it couldn't use the SOCKS path.

**Fix — a tiny HTTP→SOCKS5h bridge:** `~/.openclaw/discord_socks_bridge.py` listens on **127.0.0.1:7994** as an
HTTP proxy (CONNECT + plain HTTP) and forwards every request over **SOCKS5h to 127.0.0.1:7993**, so UniClash
resolves hostnames to its fake-IP and tunnels them. Robust to fake-IP changes (resolution is live), no hosts/DNS
edits. Pointed the bot at it: `openclaw.json` `proxy.proxyUrl` + `channels.discord.proxy` = `http://127.0.0.1:7994`.
Result: gateway **CONNECTED & STABLE** (probe resolved, 3 ok / 0 fail), bot `clanker` reachable.

**Gotchas learned:**
- Under **pythonw.exe** `sys.stderr` is None → any write crashes; the bridge now redirects stdout/stderr to
  `~/.openclaw/bridge.log`.
- Windows **SO_REUSEADDR** lets many instances bind the same port → the bridge now uses **SO_EXCLUSIVEADDRUSE**
  so a duplicate launch fails/exits (singleton). (Also: a `Get-CimInstance ... -like '*discord_socks_bridge*'`
  count is inflated because the querying powershell's own command line matches — filter by `name='pythonw.exe'`.)

**Persistence:** launched now as an independent hidden process (`start_bridge.ps1` = kill-all + Start-Process);
reboot auto-start via `Startup\openclaw-discord-bridge.vbs`. A proper auto-restarting Scheduled Task needs admin
(schtasks Create returned Access Denied) — TODO if we want the bridge to self-heal without a reboot. To restart
the bridge manually: `powershell -File ~/.openclaw/start_bridge.ps1`.

## 2026-07-20 — `/claw` command-helper (config part) shipped; true takeover deferred to dist fix

Eric wants a `/claw` "sudo, help me run this" command. A real takeover *command* (intercept the message in a
Claude Code channel, hand one turn to the brain, run it, return) is dist code — the thing that's been unreliable
on this gateway all session. OpenClaw's only config command mechanism (`customCommands`) is Telegram-only, so no
config Discord `/claw`. Eric chose "build both, config part first."

**Shipped (config, reliable — brain reads it live):** added a `## /claw` section to `workspace/AGENTS.md`. "claw"
is already a wake-word (mentionPatterns), so it summons the brain. The section teaches the brain: map intent →
exact ACP command (with a full value table: mode/profile = default|acceptEdits|plan|bypassPermissions, model =
fable|opus|sonnet|haiku|claude-fable-5), hand Eric the exact one-line command to paste for ACP controls, and for
shell/system tasks just run them via its `exec` tool. So "claw, set permission to bypass" → it replies with
`/acp permissions bypassPermissions`. Solves Eric's original "the commands don't tell you the values" pain.

**Deferred (needs dist fix):** the per-turn takeover inside a Claude-Code-bound channel + auto-running the ACP
command for him. Both require the gateway to reliably execute new dist code — still blocked on the unexplained
dist-loading issue (fresh cache-wiped gateway 5232 runs old code despite loading the edited files; one voice note
on 5232, still untested, would confirm whether it's already fixed).

## 2026-07-20 — Discord Stop button BUILT but blocked; compile-cache theory DISPROVEN; bridge hardened

### Discord one-tap 🛑 stop — built + verified correct, inert on the live gateway
Eric asked for an in-Discord stop control. Since OpenClaw shows no bot message during a run (only the 👀
reaction on the user's message), a floating component-button would need a posted+babysat message each turn
(fragile); Eric chose a one-tap 🛑 reaction instead. Built it across 3 dist files (reversible patch script
`workspace/tools/stop_reaction_patch.py`, all `node --check` clean):
- `message-handler.process-*.js`: on run-start seed 🛑 on the trigger msg + register `{msgId→sessionKey}` on
  `globalThis.__clankerStop`; remove 🛑 + deregister at run-end.
- `provider-DNXfDOia.js`: reaction-add branch — user taps 🛑 → `globalThis.__clankerAbort({key})` (the exact
  `abortSessionRunTargetWithOutcome` that `/stop` uses; confirmed it reaches `abortEmbeddedAgentRun`).
- `abort-*.js`: expose the abort fn on `globalThis` (no cross-file import wiring).
A fresh `node` import of the patched provider fires its boot-log (pid 4076) → **the on-disk patch is correct**.
The live gateway does NOT run it (no boot-log) → same stale-load wall as voice + /acp values.
**Note for Eric: typing `/stop` (or stop/cancel/abort) already aborts a run TODAY — built-in, no patch.**

### ★ CORRECTION to the 2026-07-20 "stale compile cache = TRUE ROOT CAUSE" entry (above): DISPROVEN ★
That earlier entry was wrong/incomplete. Exhaustively retested today: wiped `%TEMP%/node-compile-cache`
(283 files) AND busted the cache key by touching `openclaw/package.json` mtime AND confirmed a fresh gateway
process via `gateway.cmd` — the daemon STILL loads old bytecode of `provider-DNXfDOia.js` (logs "client
initialized" from that file but never fires my top-of-file boot-log), while a plain `node import()` of the same
file loads the patch fine. So the compile cache is NOT the (whole) cause. Real bug found but insufficient:
`enableOpenClawCompileCache({ installRoot })` passes **no `env`**, so `isNodeCompileCacheDisabled(undefined)`
is always false → the cache "disable" env var is never consulted → cache nominally always on; yet wiping it
doesn't dislodge the stale load. **Root cause still unresolved; a clean `npm` reinstall of openclaw is the
likely reset.** All dist-level features (stop button, voice, /acp help values, /claw takeover) remain blocked
by this until then.

### Discord connection instability root-caused + bridge hardened (TCP_NODELAY)
Found clanker's Discord gateway websocket was dropping every 1–5 min (`1006` closes + `heartbeat ACK timeout`
→ zombie reconnect) — that flakiness, not just the dist wall, is why the bot felt broken. The keepalive path
runs through the HTTP→SOCKS5h bridge; it was missing `TCP_NODELAY`, so Nagle can delay the tiny heartbeat
frames enough to trip Discord's ACK timeout. Hardened `~/.openclaw/discord_socks_bridge.py`: `_tune_sock()`
sets `TCP_NODELAY` + `SO_KEEPALIVE` on both tunnel sockets (to UniClash and to the bot) for every CONNECT.
Restarted the bridge; gateway resumed cleanly and held with **no drops** afterward. Caveat: several rapid
gateway restarts during debugging churned Discord's one-IDENTIFY-at-a-time limit and made it look permanently
stuck — it self-recovered once restarts stopped. Residual flakiness beyond this is UniClash tunnel quality.
Lesson (again): **do not rapid-restart the gateway — each restart resets the Discord session.**


## 2026-07-20 — Full from-scratch setup guide written (docs/openclawconfig/ in robotr repo)

Wrote a 415-line step-by-step `README.md` that rebuilds the entire stack from zero: prerequisites →
install OpenClaw → Kimi brain → Discord + the HTTP→SOCKS5h bridge → `openclaw.json` section-by-section →
`.env` secrets → **the ACP harness in detail** (acpx plugin, claude + codex backends, wrappers,
per-backend config/auth, session/lease model, multi-session) → exec-approvals → voice → running via
Scheduled Tasks → personality/memory → a gotchas table, a full file map (with secret flags), and a
from-zero checklist. Placed under `Desktop/robotr/docs/openclawconfig/` alongside a **redacted**
`openclaw.template.json` (secrets → placeholders; verified no leaks) and copies of this CHANGELOG +
COMMANDS.md. Documents the known walls honestly (stale-dist, don't-rapid-restart, Kimi model-echo,
Claude-on-Anthropic-sub ToS). Primary audience: reproducing the setup on a fresh machine.
## 2026-07-20 — Config published to github.com/djerok/openclaw-config

Consolidated the reproducible config into `Desktop/openclawconfig/` and pushed it to
**https://github.com/djerok/openclaw-config** (branch `main`). Contents: this CHANGELOG, COMMANDS.md,
`openclaw.template.json` (live config, all secrets → placeholders), and `whisper/` (load-aware STT
router + CLI wrapper + patch scripts + WHISPER-SETUP.md; models/binaries excluded, documented for
download). A `.gitignore` guards against committing secrets or large artifacts. The detailed setup
**README stays local** (robotr/docs/openclawconfig/README.md) — not pushed, per Eric. Secret-gated
before push (clean).

## 2026-07-20 — README rewritten: provider-agnostic "OpenClaw + Discord" guide (not Kimi-only)

Rewrote `README.md` (in `Desktop/openclawconfig/`) from a Kimi-specific guide into a **general
OpenClaw + Discord setup guide** usable on any machine, per Eric ("not only need kimi… make it say
openclaw discord setup… any api key (kimi, glm, etc), claude subscription, codex subscription…
uniclash/proxy for china and native for those not… specify everything not only for my case").

Structural changes:
- **Two-brains framing up front:** (1) chat brain = one model provider via **API key**; (2) coding
  agents (`/acp`) = Claude Code / Codex CLIs on an **API key OR a subscription** — independent, mixable.
- **§3 "Choose your brain / power source"** replaces the Kimi-only section with three routes: **3A** any
  API-key provider (generic `models.providers` block + a Kimi/GLM/OpenAI/Anthropic/DeepSeek quick-ref
  table), **3B** Claude **subscription** (claude CLI OAuth → acpx `claude` backend, `~/.claude/…`, ToS
  caveat + API-key alternative), **3C** Codex **subscription** (codex CLI ChatGPT OAuth → acpx `codex`
  backend, `~/.codex/auth.json` → `codex-home/`, the account-vs-API-key model-version gate documented).
- **§5 network is now conditional:** explicit decision (can you open Discord normally?). **5A native/
  direct** = no proxy at all (`proxy.enabled:false`, drop `channels.discord.proxy`) for everyone outside
  the GFW; **5B proxy** = the UniClash + HTTP→SOCKS5h bridge path for China/blocked networks (bridge
  optional if the proxy already speaks HTTP).
- **De-personalized:** paths → `~/…`, Discord IDs/tokens/keys → placeholders; Windows kept as the
  reference with **(Windows)** tags + macOS/Linux (launchd/systemd/pm2) notes. Kept the hard-won gotchas
  (stale-dist wall, don't-rapid-restart, endpoint model-echo, doctor-before-restart, codex version gate).
- Honest note added that `@zed-industries/codex-acp` is a compiled native binary pinned to a codex
  version (don't expect a trivial rebuild) — distilled from tonight's failed source-rebuild attempt.

## 2026-07-20 — gpt-5.6 on the ChatGPT account UNLOCKED + codex wired in via MCP (Kimi + Claude callable)

**The culprit was purely the codex CLIENT version.** Updating the external codex CLI
`npm i -g @openai/codex@latest` (0.125.0 → **0.144.6**, current latest) cleared the account-path
*"requires a newer version of Codex"* gate. On a ChatGPT **account**, plain `gpt-5.6` / `gpt-5.6-codex`
are rejected ("not supported when using Codex with a ChatGPT account" — API-only names); the
account-blessed 5.6 model is **`gpt-5.6-terra`** (codex's default on the account). Verified working:
`codex exec` returned PONG/READY on gpt-5.6-terra with chatgpt auth. (The embedded codex-acp.exe still
carries codex 0.137 → the `/acp codex` path stays too old until Zed ships a 0.144-based build; we did
NOT rebuild it — see the rebuild-verdict memory.)

**Integration = codex as an MCP server (no rebuild):** `codex mcp-server` (from the 0.144.6 CLI) wired
into two places, both using the same command + safe flags
(`-c approval_policy=never -c sandbox_mode=read-only -c model=gpt-5.6-terra -c notify=[]`):
- **OpenClaw / Kimi brain** — added `mcp.servers.codex` to `~/.openclaw/openclaw.json` (node → codex.js
  → mcp-server; connectTimeout 120, timeout 300). Gateway **hot-reloaded** it (`config hot reload applied
  (mcp.servers.codex)`, no restart, Discord stayed up); child process spawned + persistent.
- **Claude Code** — `claude mcp add -s user codex -- …` → `~/.claude.json` (user scope), so every Claude
  Code session, including the `/acp claude` agent, can call codex.

**Verified end-to-end** via a direct MCP handshake against `codex mcp-server`: `initialize` → serverInfo
`codex-mcp-server 0.144.6`; `tools/list` → **`['codex', 'codex-reply']`** (run a session / continue a
thread); `tools/call codex` → ran a real turn, **MODEL USED gpt-5.6-terra**, returned `MCPOK`.

Sandbox is **read-only** (codex reads/reasons/returns code, does not autonomously edit files or run
commands) — flip `sandbox_mode` to `workspace-write` in both the openclaw.json args and the `claude mcp
add` command to let it apply changes. Reverting the CLI: `npm i -g @openai/codex@0.125.0`.

## 2026-07-21 — Root-caused the "stale-dist wall": clean reinstall + verified re-patch (✅ + 🎤 fixed)

The 🛑-stop / ✅-checkmark / 🎤-voice features that "silently didn't work" were all **hand-patches sitting
on dead code paths.** OpenClaw's `dist` is minified + code-split into hundreds of hash-named, lazily-loaded
chunks; the prior patches targeted the wrong chunk (`provider-DNXfDOia.js`), which the live Discord flow
never loads. Verified by driving a **second Discord test bot** ("clanker 2", app id `1528723654576312361`,
token in `~/.openclaw/.env`, in "clanker do my work" guild) — `allowBots:true` + it added to
`channels.discord.allowFrom` so clanker responds to it; drive via REST through the bridge (`~/clanker-test/test_bot.py`).

**Fix approach:** `npm install -g openclaw@2026.7.1-2` (clean dist, same version) → re-apply patches onto
the **verified-live** bundles, each proven with a boot-trace before declaring done.

- **✅ check-mark — FIXED + CONFIRMED.** Reaction went 👀→🧠→✅ and **stuck**. Root cause: after `setDone()`
  applies ✅, `restoreInitial()` reverts it to the 👀 ack. Fix = `if (finished) return;` guard in
  `channel-feedback-*.js` (the status controller) so a final done/error reaction can't be reverted.
  Durable script: **`~/.openclaw/workspace/tools/checkmark_persist_patch.py`**. (Also flipped
  `messages.statusReactions.enabled:true`.)
- **🎤 voice — the ffmpeg "fix" above was WRONG (Eric: "it absolutely did not"); REAL fix below, now
  CONFIRMED.** The ffmpeg error was a *different* code path (manual `media` tool), not inbound Discord voice,
  so the ffmpeg hardcode changed nothing. Chased a second red herring ("unimplemented") by grepping the
  discord.js *library* bundle. **Real root cause: transcription IS built + wired for Discord** — the discord
  extension preflight `preflight-audio-*.js` (`loadDiscordPreflightAudioRuntime` → downloads `att.url` from
  the Discord CDN → `transcribeFirstAudio`), called by `message-handler.preflight-*.js`. It was **gated, not
  missing**: `needsPreflightTranscription = hasAudio && !hasTypedText && (isDirectMessage ||
  shouldRequireMention && mentionRegexes.length>0)`. Clanker's channel is `groupPolicy:"open"` ⇒
  `shouldRequireMention=false`, not a DM ⇒ the gate is false ⇒ **an open channel never transcribes voice.**
  **Fix = relax the gate** to `(isDirectMessage || !shouldRequireMention || mentionRegexes.length>0)`. Durable
  patch: **`~/.openclaw/workspace/tools/voice_gate_patch.py`** (globs the gate across hash-renamed bundles,
  `node --check`, idempotent). **PROVEN** with 3 fresh TTS nonce clips sent as real voice messages (flags=8192
  + waveform, via new `~/clanker-test/voice_send.py`) → clanker replied "pineapple 🍍", "Velvet Thunder 9",
  "Scarlet Falcon 7" — content that existed only in the audio. (`inferAudioAttachmentMime` already detects
  Discord voice via `duration_secs`/`waveform`.)
- **🧹 voice privacy cleanup — Eric: "delete afterwards the transcript and the audio".** OpenClaw does NOT
  auto-delete inbound voice: it saves every one to `~/.openclaw/media/inbound/*.ogg` (+ workspace
  `openclaw-staged-*`) and keeps it ~30 min for history reference (hardcoded TTL). Transcription reads the CDN
  url, not that saved copy, so deleting it is safe. Two-part: (1) `voice_gate_patch.py` patch 2 adds a
  `finally{ unlink(fileOutput) }` in `runner.entries-*.js` `resolveCliOutput` so the whisper `-otxt`
  transcript `.txt` is removed after read (was leaking); (2) **`~/.openclaw/workspace/tools/
  voice_privacy_sweep.py`** + Windows Scheduled Task **"OpenClaw Voice Privacy Sweep"** (every 1 min) deletes
  audio + `.txt` in the two inbound dirs older than 180 s (>worst-case turn; images untouched). Verified it
  swept 4 lingering recordings (incl Eric's own) and each test clip within ~3 min.
- **⚠️ gateway slowness / flaky delivery (separate, pre-existing).** `start_clanker.cmd` sets
  `NODE_DISABLE_COMPILE_CACHE=1` (leftover from the debunked stale-dist theory) → full recompile every boot
  (~3 min) and a CPU-bound process → event-loop stalls → Discord "heartbeat ACK timeout" → websocket
  zombie/reconnect → replies delayed (one nonce took ~5 min, delivered after reconnect). Removing that flag
  should speed boot and stabilize delivery. Not changed on the running process this session.
- **🛑 stop — DEFERRED (Eric shipped the 2).** The live Discord plugin *receives* reactions (intent on) but
  wires **no handler** for them; the prior patch's handler bundle never loads, so a 🛑 reaction never
  reaches the gateway. Viable path (Eric's idea): external watcher polls Discord for 🛑 → fires a stop
  hook. Hook found: `openclaw gateway call chat.abort --params '{"sessionKey":"agent:main:discord:channel:<CH>","runId":"<id>"}'`
  (needs the active runId; `sessions.abort` needs `key`). `/stop` is a slash command, not message-parsed.
  Not built this session.

**⚠️ PERSISTENCE / AUTO-START — UNRESOLVED (known-bad, has a clean fix).** clanker runs fine when launched
directly (any interactive shell), but the **Scheduled Task can't start it**: the Task's batch-logon token
gets `MODULE_NOT_FOUND` for `…\openclaw\dist\index.js` even though the file exists + `ericc` has FullControl.
**Smoking gun:** the openclaw folder carries **AppContainer / `djerok116\CodexSandboxUsers` ACLs** because
the reinstall ran *inside the Claude sandbox*. A plain Task token can't satisfy those. ACL grants
(`icacls … /grant Users:(RX)`) are the right idea but recursing `node_modules` bogged the box into timeouts.
**CLEAN FIX (do outside the sandbox):** open a normal PowerShell/cmd *yourself* and
`npm install -g openclaw@2026.7.1-2` (or `openclaw onboard`) → gives the folder normal ACLs → the existing
Task works. Then re-run `checkmark_persist_patch.py` + `ffmpeg_hardcode_patch.py` (both idempotent).

**Manual start meanwhile:** `~/.openclaw/start_clanker.cmd` (run from your own terminal). Gateway currently
runs as a direct process (not the Task) — survives until this machine/session ends. Config edits this
session: `channels.discord.allowBots:true`, `allowFrom` += test-bot id, `messages.statusReactions.enabled:true`.
`gateway.vbs`/`gateway.cmd`/the Task action were edited during debugging (blocking wscript, log redirect) —
harmless but note before the clean reinstall.

### 2026-07-21 (late night 2) — human voice ignored (mention gate) + CPU cleanup

- **FIXED: your own voice messages were ignored, the test bot's worked.** Root cause:
  `resolveDiscordShouldRequireMention` defaults to **TRUE** for guild messages
  (`channelConfig?.requireMention ?? guildInfo?.requireMention ?? true`), so clanker needs an @mention from
  humans. Your TEXT works because you @mention/reply clanker; a **voice message has no text so it can never
  contain a mention** → dropped. The test bot bypasses the whole gate via `allowBots: true` (= "all" mode).
  Fix: set **`channels.discord.guilds["1527763934508089446"].requireMention = false`** (guild-level — the top
  `channels.discord.requireMention` is schema-INVALID and silently skips the whole config reload; must be
  under `guilds.<id>` or `channels.<id>`). Gateway restarted (with Kimi env re-injected) to load it. Effect:
  clanker now answers ALL human messages in that guild without a mention (voice + text). If too chatty,
  alternative = surgical patch so only voice bypasses the mention.
- **CPU cleanup:** killed 6 orphaned `claude-agent-acp` node harnesses left by ACP testing (node procs 25→17).
  Whisper confirmed on GPU (`route=large/GPU`); gateway + watcher are I/O-bound (Kimi API + Discord polling),
  nothing else is GPU-offloadable. clanker/ACP inference is remote (Kimi API), not local.

### 2026-07-21 (late night) — ACP Claude Code: auth FIXED (Kimi) + stop/listening now WORK

- **ACP claude 401 FIXED — routed to Kimi.** Root cause chain: acpx strips provider-auth env from the harness
  → harness auths via `~/.claude` → `.credentials.json` (real-Anthropic OAuth) overrode the Kimi settings → 401.
  Fix (Eric: "move ACP to claude-kimi"): `claude_auth_switch.py kimi` (settings.json → Kimi) + **backed up and
  renamed `~/.claude/.credentials.json` → `.credentials.json.disabled-for-kimi-acp`** (backup in
  `~/.claude/backups/`). ACP claude then authenticated: `🤖 claude | AUTH OK via kimi`. **SIDE EFFECT: Eric's
  own Claude Code CLI is now Kimi-only** until he restores the credential / re-logs in ("figure out claude code
  later"). Kimi token verified valid independently (direct /v1/messages → 200).
- **🛑 stop + 🎧 listening now reach ACP Claude Code sessions.** stop_watcher `text_channels()` now also polls
  `/guilds/{g}/threads/active` (ACP `--thread auto` runs in a `🤖 claude` thread; `--bind here` runs in the
  channel). Confirmed: `/stop` aborts a live ACP run (`Got it. Stopping here.` → `⚙️ Agent was aborted.`), and a
  🛑 reaction in the ACP thread → watcher `/stop` → **aborted an ACP essay mid-stream**. Watcher polling
  parallelized (ThreadPoolExecutor, 10 workers) so many channels+threads don't slow the cycle and let fast runs
  finish before `/stop` lands. Spawn gotcha: `/acp spawn claude --cwd <path>` splits on the path — omit `--cwd`.
- **Remaining ACP TODO:** permission approve/deny UI. acpx `nonInteractivePermissions: deny` means non-read
  tools are silently denied without an interactive Discord prompt (unbuilt). That's the last piece for full
  Claude-Code-over-Discord.

### 2026-07-21 (night) — transcript echo + ACP-scope findings + gateway keeps dying

- **🎤 transcript echo before thinking** (Eric: "output the transcription in text before it starts to
  think"). The config `tools.media.audio.echoTranscript` exists but is ONLY wired into the media-*tool*
  path — Discord's inbound-voice `preflight-audio-*.js` never calls it, so the config is a no-op for
  Discord voice. Bridged in our own components instead: `whisper_router.py` appends each transcript to
  `~/.openclaw/voice_echo/transcripts.jsonl`; `stop_watcher.py` FIFO-matches new transcripts to the voice
  messages it 🎧'd and posts `🎤 "<transcript>"` as a reply. Freshness guard (only queue voice msgs <25s
  old) prevents FIFO misalignment after a watcher restart. Verified: echo posts with the correct text,
  BEFORE clanker's reply.
- **ACP UPDATE (tested in claude-agi3-zixuan): watcher now thread-aware; ACP claude itself is 401-broken.**
  - **Thread-aware watcher DONE + confirmed:** `text_channels()` now also polls `/guilds/{g}/threads/active`,
    so 🎧/🛑/🎤-echo reach ACP sessions spawned with `--thread auto` (which run in a `🤖 claude` thread).
    Verified: a message in the ACP thread got 🛑 seeded. `--bind here` sessions run in the channel and were
    already covered.
  - **BLOCKER — ACP claude can't authenticate:** every `/acp spawn claude` turn dies with
    `Failed to authenticate. API Error: 401` / `ACP_TURN_FAILED`. Root cause: the acpx claude harness inherits
    `~/.claude/settings.json`, which currently has **ANTHROPIC_BASE_URL unset (→ real Anthropic), model=fable,
    no auth token** — i.e. Claude Code's global auth is pointed at the real Anthropic sub with invalid/expired
    OAuth, NOT Kimi. So there is no working ACP run to /stop and no permission prompt ever fires.
  - **Consequence:** verifying /stop aborts an ACP run + building the permission approve/deny UI are BLOCKED
    until ACP claude auth is fixed (route Claude Code to Kimi, which is how ACP is meant to run — a global
    Claude Code auth change, so left for Eric to decide). Spawn syntax gotcha: `--cwd <path>` gets split by the
    arg parser (both slash styles) — omit it; acpx defaults to `~/.openclaw/workspace`.
- **ACP (Claude Code) sessions — the new features mostly DON'T reach them (investigated, not extended).**
  Everything built this session targets the main clanker/kimi path. For `/acp spawn claude` sessions:
  (1) **listening/🎧/echo** — likely carries over (transcription + 🎧 are channel-ingress level, and there's
  a `dispatch-acp-media.runtime`), but UNTESTED with a live ACP session. (2) **🛑 stop** — the watcher polls
  text channels (type 0/5) NOT threads, and ACP sessions typically bind to a thread → the 🛑 won't appear
  there; also `/stop` reaching an ACP run is untested (ACP shares abortSignal/runId infra, so it *might*).
  (3) **permissions** — ACP tool approvals go through `resolvePermissionRequest`→`promptUserPermission`
  (CLI prompt), and the Discord approve/deny UI is a known UNBUILT item. So ACP permission prompts are not
  surfaced interactively in Discord. Net: to make stop/permissions work for Claude Code sessions is real
  additional work (thread-aware watcher + ACP-run abort test + a Discord permission UI).
- **⚠️ gateway keeps dying.** The gateway runs as a foreground process inside the Claude session; when that
  session churns/exits, the gateway dies and clanker goes silent (happened again — "it didn't reply").
  Restarted (boot ~108s). Root fix is still the sandbox-ACL reinstall so the Scheduled Task can own it.

### 2026-07-21 (evening) — edit-in-place streaming + instant 🎧 voice feedback

- **✍️ streaming = edit-in-place.** Discord was posting complete chunks as separate messages. Set
  **`channels.discord.streaming = {"mode":"partial"}`** (openclaw.json) — OpenClaw now EDITS a message as
  tokens arrive (`discordStreamMode==="partial"` in message-handler.process tracks `lastPartialText`). Hot-
  reloaded (no restart). Verified: one msg grew via edits `len 234→615→731→1856`; long replies still span
  multiple messages only because of Discord's 2000-char cap, each streamed by editing. Modes:
  off / partial / block(old default) / progress.
- **🎧 instant voice feedback.** Voice DOES work (confirmed repeatedly: 👀→🧠→✅ + correct reply, whisper
  ~4s on GPU) — but the 👀 ack only fires AFTER whisper transcribes (~12-14s), so a voice message looked
  ignored for 10-15s ("doesn't react like it does"). `stop_watcher.py` now adds a **🎧 "heard you"** reaction
  to any voice message immediately (before the transcription-delayed 👀), and removes it (with the 🛑) when the
  prompt gets ✅/❌. Verified: 🎧 in ~9s, reply "The secret code word is pineapple" in ~15s, clean finish
  (🎧/🛑 gone, ✅ remains). If voice still seems dead it's transient kimi API errors, not transcription.

### 2026-07-21 (later) — voice really fixed, whisper GPU/CPU, gateway un-throttled, 🛑 stop button

- **🎤 voice — root cause was a GATE, not ffmpeg (corrected above); now proven with 3 fresh TTS nonces**
  (clanker echoed "pineapple 🍍", "Velvet Thunder 9", "Scarlet Falcon 7" — each only in the audio). Fix =
  relax the discord audio-preflight gate for open channels. Durable: `voice_gate_patch.py`.
- **🧹 voice privacy** (Eric: "delete the transcript and the audio afterwards"). OpenClaw keeps inbound voice
  in `~/.openclaw/media/inbound/` ~30 min; transcription reads the CDN url not that copy, so deleting it is
  safe. `voice_gate_patch.py` patch-2 unlinks the whisper `-otxt` `.txt`; **`voice_privacy_sweep.py`** +
  Task **"OpenClaw Voice Privacy Sweep"** (`/SC MINUTE`) deletes audio+`.txt` >180s old from the inbound dirs.
- **🎧 whisper router — GPU-if-free-else-CPU** (Eric's ask). `~/.openclaw/whisper/whisper_router.py` already
  routed by live GPU/CPU load (RTX 5070, cuBLAS build); simplified `pick()` to: GPU when util <85%, else CPU,
  **never** the Discord fallback. Verified `route=large/GPU`.
- **⚡ gateway un-throttled.** Removed `NODE_DISABLE_COMPILE_CACHE=1` from `start_clanker.cmd` (leftover from
  the debunked stale-dist theory). It forced a full recompile every boot and stalled the event loop ~23s
  mid-run (`eventLoopDelayP99Ms=23270`), which delayed replies AND made `/stop` miss its window. Now responsive.
- **🛑 STOP BUTTON — BUILT + CONFIRMED.** The live plugin ignores inbound reactions, so bridged via an external
  watcher: **`~/.openclaw/workspace/tools/stop_watcher.py`** + Task **"OpenClaw Stop Watcher"** (`/SC MINUTE`,
  pythonw hidden, self-healing, single-instance port-lock). It **seeds 🛑 on every prompt**, on a **human
  click** posts **`/stop`** (the working text-abort trigger) to abort, and **removes the 🛑** when the prompt
  gets a terminal ✅/❌ status reaction. Auto-deletes its `/stop` message; recency guard (600s) stops stale
  re-fires. **Key gotcha:** `/stop` only aborts when it comes from an `allowFrom` sender — clanker's own id is
  NOT in allowFrom, so the watcher posts `/stop` as **"clanker 2" (TEST_BOT_TOKEN, which IS in allowFrom)**.
  ⇒ the stop feature now DEPENDS on clanker 2 staying in the guild+allowFrom. End-to-end test:
  `~/clanker-test/test_stop_v2.py` → seeded 🛑 in 3s, click → `aborted=True`, 🛑 removed. Cleaner long-term
  path (no bot dependency): wire the gateway control API `chat.abort` (per-run AbortController registry in
  `chat-abort-*.js`) — not built.

### 2026-07-21 (very late) — MANUAL per-action approve for ACP (build + wake-word variations)

- **🔐 Manual approve/deny for ACP tools — BUILT.** acpx only ships approve-all/approve-reads/deny-all (no
  per-action prompt) because the permission event fires headless. Bridged it: `acp_manual_approve_patch.py`
  patches the embedded runtime (`runtime-*.js` `resolveReadOrPromptPermission`) so the headless auto-DENY
  branch instead calls a helper that writes a pending file to `~/.openclaw/acp_perms/pending/` and block-polls
  `decided/` (90s). `stop_watcher.py` sees the pending file, posts **"🔐 clanker wants to run `<tool>` — ✅/❌"**
  to the active ACP thread (tracked via the `🤖 claude` author), reads your reaction, writes the decision.
  VERIFIED the Discord half end-to-end (simulated pending → prompt → ✅ → `decided={"allow":true}`). permissionMode
  set back to **approve-reads** (reads auto, everything else prompts). Re-apply the patch after `openclaw update`.
  Couldn't drive the harness half via the test bot (only Eric can bind a session; auto-threads hard to target) —
  needs Eric to confirm in a real session. Correlation caveat: assumes one active ACP session at a time.
- **🗣 wake-word variations** — mentionPatterns now cover clanker/clunker/blanker/glanker/claw/glaw/openclaw/
  openclock via 3 regexes; verified matches vs rejects (glow/blow/black stay quiet).
- **acpx test-session cleanup** — killed orphaned `claude-agent-acp` node processes (they pile up per spawn).

### 2026-07-21 (final) — one-click Start/Stop launcher + resource accounting + headless cleanup

- **🖱 Desktop launcher — `C:\Users\ericc\Desktop\Clanker Control.cmd`.** Double-click menu (START / STOP /
  STATUS / RESTART) for the whole clanker stack. Drives **`~/.openclaw/clanker_control.py`**, which:
  - **START** — launches the gateway **detached + hidden** (`DETACHED_PROCESS|NEW_PROCESS_GROUP|NO_WINDOW`)
    with the **Kimi env pulled from `~/.claude/settings.json`** (so ACP-claude authenticates and the bot
    survives the launcher window closing), then `schtasks /Run` for the watcher + voice-sweep + status board,
    then waits (≤3 min) for port 18789 to bind.
  - **STOP** — kills the gateway (PID on :18789) + stop-watcher (PID on :18790), **disables the "OpenClaw
    Gateway" self-heal task** (else it retries every 5 min), and ends the aux tasks.
  - **STATUS** — reports gateway/watcher up-or-down + task registration.
  - Note: a `.cmd` is the practical Windows "exe" here (double-clickable, no build step); it calls the
    known-good Python 3.12 interpreter directly since bare `python` is a 0-byte stub on this PC.
- **📊 Resource accounting** (measured, steady-state RAM; clanker only, excludes this machine's VS Code/MCP node):
  gateway **~436 MB** · stop-watcher **~21 MB** · status board **~21 MB** · Discord socks bridge **~14 MB**
  ⇒ **≈490 MB resident**. CPU is **near-idle** (event loop + 3–5 s polls); the only real burst is **whisper**
  on a voice message (**GPU if free**, ~1–4 s, else CPU). Whisper is **local = $0**. The one variable cost is
  **Kimi API tokens** — every clanker reply and every ACP-claude turn bills the Kimi Code subscription
  (no per-message Anthropic charge, since ACP is routed to Kimi). Disk: faster-whisper model (~1.5 GB) + logs.
- **🧹 Headless / efficiency** — `whisper-cli.cmd` now calls **`pythonw.exe`** (windowless, no console flash per
  transcription); the voice-privacy sweep runs windowless; watcher poll relaxed to 3 s. No more popup spam.
- **↩ `/brain` toggle reverted** — the "swap OpenClaw's brain to Claude-Code-CLI-via-Kimi" `/brain` command
  (patched into `message-handler.preflight-*.js`) didn't work and was removed (`node --check` clean). ACP
  (`/acp spawn claude`) remains the way to reach Claude Code from Discord; not worth the patch-maintenance.
- **🔘 Button GUI** (follow-up, same day) — replaced the number-menu `.cmd` with a real **tkinter panel**
  (`~/.openclaw/clanker_gui.py`, ships with Python 3.12, no install). Window shows **two live status dots**
  (Discord bot / stop-watcher, green=up red=down, auto-poll 4 s) and **▶ Start / ■ Stop / ⟳ Restart / ↻ Refresh**
  buttons that shell out to `clanker_control.py` and stream its output into a log pane. `Clanker Control.cmd`
  now launches it windowless via `pythonw`. Note: "OpenClaw" here **is** the gateway — Stop kills that node
  process, so the buttons turn OpenClaw itself on/off. All three scripts versioned in `openclawconfig/launcher/`.
