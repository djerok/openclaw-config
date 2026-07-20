# OpenClaw + Discord — Full Setup Guide

Build a Discord chat bot on an [OpenClaw](https://www.npmjs.com/package/openclaw) gateway. The bot's
brain can be **any model provider** (Kimi, GLM/Z.ai, OpenAI, Anthropic, DeepSeek, a local model, …),
and it can spawn real **coding agents over ACP** (Claude Code and/or Codex) that run on either an
**API key** or a **subscription** (Anthropic Pro/Max, ChatGPT Plus/Pro). It works **with or without a
proxy** — a proxy is only needed on networks that block Discord/OpenAI/Anthropic (e.g. mainland China).

This guide is written to be reproducible on **any** machine, not one specific setup. Paths use `~`
(on Windows that expands to `C:\Users\<you>`). Fill every `<PLACEHOLDER>` with your own value.

Companion files in this folder:
- **`openclaw.template.json`** — a redacted copy of a working `openclaw.json` (all secrets → placeholders). Your starting config.
- **`COMMANDS.md`** — start/stop/restart cheat-sheet for the gateway + status board.
- **`CHANGELOG.md`** — the dated history of the reference build (every fix and why).
- **`whisper/`** — optional local speech-to-text (voice notes). See `whisper/WHISPER-SETUP.md`.

> **Secrets rule:** never commit real tokens/keys. Everything below uses placeholders. Real values
> live only in `~/.openclaw/.env`, `~/.openclaw/openclaw.json`, and the per-backend auth files on the
> machine — all git-ignored.

> **Platform note:** the reference build runs on **Windows** (gateway as a Scheduled Task, `pythonw`
> for the bridge). OpenClaw itself is cross-platform — on macOS/Linux use a `launchd`/`systemd`/`pm2`
> service instead of a Scheduled Task; the Python bridge, the CLIs, and every config file are the same.
> Windows-only steps are marked **(Windows)**.

---

## 0. Architecture — the whole pipeline

There are **two independent brains** in this system; understanding the split is the key to the config:

```
                            ┌─────────────────────────────────────────────────────────┐
You type in Discord ──▶ Discord ──▶ (proxy, ONLY if your network blocks Discord) ──▶   │
                            │                                                            │
                            ▼                                                            │
                    OpenClaw gateway (node, loopback API 127.0.0.1:18789)               │
                            │                                                            │
      ┌─────────────────────┴───────────────────────────┐                              │
      │ 1) CHAT BRAIN  (the @bot conversation)           │                              │
      │    → one model provider via API KEY              │                              │
      │      Kimi | GLM | OpenAI | Anthropic | …         │                              │
      │                                                  │                              │
      │ 2) CODING AGENTS  (/acp …)                       │                              │
      │    → acpx plugin spawns a coding-agent CLI:      │                              │
      │      • "claude" → Claude Code CLI  → Anthropic   │  ← API key  OR  subscription │
      │      • "codex"  → Codex CLI        → OpenAI      │  ← API key  OR  subscription │
      └──────────────────────────────────────────────────┘                              │
                            │                                                            │
                            ▼                                                            │
                    response streams back up the same chain ─────────────────────────────┘
```

- **Chat brain (1):** whatever you `@mention` the bot with is answered by a single model, defined by a
  **provider block + API key** in `openclaw.json`. Any OpenAI- or Anthropic-compatible endpoint works.
- **Coding agents (2):** `/acp` spawns a real coding-agent CLI. These can run on a **subscription**
  (log the CLI in with your account over OAuth) **or** an **API key** — independently of the chat brain.

You can mix freely: e.g. a cheap **GLM API key** for chat, plus a **Claude Max subscription** for the
`/acp claude` coding agent.

---

## 1. Prerequisites

| Need | Notes |
|---|---|
| **Node.js** | LTS or current. `node -v` must work in a plain shell. |
| **Python 3** | Only needed for the optional proxy bridge and helper scripts. Use whatever command launches Python 3 on your system (on some Windows installs bare `python` is a broken stub — use `python3`). |
| **A Discord bot** | Create at <https://discord.com/developers> → New Application → **Bot** → copy the token. Enable **Message Content Intent**. Invite it to your server (Part 4). |
| **A brain** | Pick ONE of: an **API key** for any provider (Part 3A), a **Claude subscription** (3B), or a **Codex subscription** (3C). You can add more later. |
| **A proxy** — *only if your network blocks Discord/OpenAI/Anthropic* (e.g. China) | Any VPN/proxy that can reach them. Not needed elsewhere. See Part 5. |

Config lives in a few homes:
- **`~/.openclaw/`** — OpenClaw config, secrets, the workspace, ACP wrappers, (optional) bridge.
- **`~/.claude/`** — the `claude` CLI's own config (only for the Claude Code ACP backend).
- **`~/.codex/`** and/or **`~/.openclaw/acpx/codex-home/`** — the `codex` CLI's config (Codex backend).

---

## 2. Install OpenClaw

```bash
npm install -g openclaw
openclaw --version                 # confirm it runs
openclaw                           # first-time wizard → scaffolds ~/.openclaw/openclaw.json + .env
```

> **Known wall (important):** some installs have a *stale-dist* bug — the long-running gateway executes
> **old compiled bytecode** for any hand-edited `dist/*.js` file, even when the file on disk is correct.
> **Config changes (`openclaw.json`, workspace `*.md`) take effect; hand-patched program code does not.**
> If a *code-level* feature won't turn on, this is why. A clean `npm` reinstall is the only known reset.
> (Detail in `CHANGELOG.md`.) Everything in this guide is config- or file-based, so it is unaffected —
> except a couple of clearly-marked optional code patches (voice).

---

## 3. Choose your brain / power source

Do **at least one** of 3A / 3B / 3C. 3A powers the chat bot; 3B/3C power the `/acp` coding agents.

### 3A. Chat brain via ANY API key (Kimi, GLM, OpenAI, Anthropic, …)

The chat brain is defined entirely by a **provider block** in `openclaw.json → models.providers`. The
shape is always the same — a base URL, a wire-protocol (`api`), your key, and the model list:

```jsonc
"models": {
  "mode": "merge",
  "providers": {
    "<provider-name>": {
      "baseUrl": "<https endpoint>",
      "api": "anthropic-messages",          // wire protocol: "anthropic-messages" or an OpenAI value
      "apiKey": "<YOUR_API_KEY>",           // or pull from .env; see Part 6
      "models": [
        { "id": "<model-id>", "name": "<label>", "reasoning": true,
          "input": ["text","image"], "contextWindow": 262144, "maxTokens": 32768 }
      ]
    }
  }
},
"agents": { "defaults": { "model": { "primary": "<provider-name>/<model-id>" } } }
```

The `api` field is OpenClaw's protocol selector: **`anthropic-messages`** for Anthropic-style endpoints,
an **OpenAI** value (e.g. `openai-chat` / `openai-responses`) for OpenAI-style endpoints. If unsure,
copy a known-good block for that provider and run `openclaw doctor` to validate.

**Provider quick-reference** (confirm current base URLs + model ids in each provider's own dashboard):

| Provider | `baseUrl` | `api` | Where to get the key |
|---|---|---|---|
| **Kimi** (Moonshot) | `https://api.kimi.com/coding/` | `anthropic-messages` | **kimi.com/code** (a *coding subscription* key — NOT moonshot.ai, which 401s on this endpoint) |
| **GLM / Z.ai** (Zhipu) | `https://api.z.ai/api/anthropic` (Anthropic-compat) or `https://api.z.ai/api/paas/v4/` (OpenAI-compat) | `anthropic-messages` / OpenAI | z.ai coding plan dashboard |
| **OpenAI** | `https://api.openai.com/v1/` | OpenAI (`openai-chat`/`openai-responses`) | platform.openai.com → API keys (`sk-proj-…`) |
| **Anthropic** | `https://api.anthropic.com/` | `anthropic-messages` | console.anthropic.com (`sk-ant-…`) |
| **DeepSeek / OpenRouter / local (Ollama, LM Studio, vLLM)** | provider/host URL | OpenAI (they're OpenAI-compatible) | provider dashboard / none for local |

> Concrete Kimi example (the reference build's default) — `openclaw.template.json` ships this verbatim:
> models `k3` (1M ctx), `kimi-for-coding`, `kimi-for-coding-highspeed`; default `kimi/auto`.
>
> **Gotcha (echoing endpoints):** some coding endpoints (Kimi's included) **echo any model id** — asking
> for `opus` or `fable` still serves *their* model wearing that label. A `/model fable` that "works" is
> not real Fable. Real Claude/Codex only comes through the **ACP agents** (3B/3C).

> **"Subscription" note:** most consumer subscriptions can't directly power the *chat brain*, because
> they're OAuth-gated to their own CLI/app rather than exposing a key. The clean way to use a
> subscription is the **ACP coding agents** below (3B/3C). The exception is products that sell a
> *coding-subscription API key* (e.g. Kimi's kimi.com/code, GLM's coding plan) — those are already
> "API key" providers and slot straight into 3A.

### 3B. Coding agent via a **Claude subscription** (Anthropic Pro/Max)

This runs the real `claude` CLI as an ACP backend, on your Anthropic **subscription** (OAuth login) —
so `/acp claude …` in Discord spawns a genuine Claude Code agent.

1. **Install + log in** the Claude CLI:
   ```bash
   npm install -g @anthropic-ai/claude-code
   claude            # on first run, choose "Log in with your Anthropic account" (Pro/Max)
   claude --version  # must run
   ```
   OAuth tokens are stored in **`~/.claude/.credentials.json`** (never commit this).
2. **Pick the model** in **`~/.claude/settings.json`** → `"model": "<opus|sonnet|haiku|fable|full-id>"`.
   (This is the model the ACP agent uses — separate from your chat brain.)
3. **Endpoint:** leave `ANTHROPIC_BASE_URL` unset (or `https://api.anthropic.com`) to use real Anthropic.
4. Turn on the acpx `claude` backend (Part 7). Spawn recipe: `agentId: "claude"`.

> **Alternative — API key instead of subscription:** set `ANTHROPIC_API_KEY` (or point
> `ANTHROPIC_BASE_URL` at any Anthropic-compatible endpoint + key). Pay-per-token, no subscription.
>
> **ToS caveat:** running a *subscription* login inside a third-party harness (acpx) is a gray area in
> Anthropic's terms. If you want to stay strictly clean, use an **API key** for the ACP backend instead.

### 3C. Coding agent via a **Codex / ChatGPT subscription** (Plus/Pro)

This runs the real `codex` CLI as an ACP backend, on your **ChatGPT subscription** (OAuth) — so
`/acp codex …` spawns a genuine Codex agent billed to your Plus/Pro plan, not per-token.

1. **Install + log in** the Codex CLI:
   ```bash
   npm install -g @openai/codex      # or the official installer for your OS
   codex login                       # choose "Sign in with ChatGPT" (your Plus/Pro account)
   codex --version                   # must run
   ```
   Account OAuth is stored in **`~/.codex/auth.json`** with `auth_mode = "chatgpt"` (never commit).
2. **Give the ACP backend that auth.** acpx uses a dedicated home `~/.openclaw/acpx/codex-home/`:
   - Copy your account `auth.json` into `~/.openclaw/acpx/codex-home/auth.json`, **or** set the wrapper's
     `CODEX_HOME` to `~/.codex`. (Copying is simplest; re-copy if the token later rotates.)
   - `~/.openclaw/acpx/codex-home/config.toml` → `model = "<gpt-5.x>"`, `model_reasoning_effort = "xhigh"`,
     and your trusted-project list.
3. Turn on the acpx `codex` backend (Part 7). Spawn recipe: `agentId: "codex"`.

> **Account vs API-key gotcha (learned the hard way):** on the **subscription/account** path, OpenAI
> **server-side-gates the newest models by your `codex` CLI version.** A newer model (e.g. `gpt-5.6`)
> can return *"requires a newer version of Codex"* on an older CLI, while an older model (e.g. `gpt-5.5`)
> works fine. Fixes: **update the `codex` CLI**, or use a model your version is allowed, or switch that
> backend to an **API key** (`OPENAI_API_KEY = sk-proj-…` in `codex-home/auth.json`) — the **API-key path
> has no such version gate**, but it's pay-per-token instead of included in your subscription.

---

## 4. Discord bot (provider-independent)

1. <https://discord.com/developers> → **New Application** → **Bot** → **Reset/Copy Token** → this is your
   `DISCORD_BOT_TOKEN`.
2. Under **Bot → Privileged Gateway Intents**, enable **Message Content Intent** (required to read
   messages). Enable **Server Members** only if you need it.
3. **OAuth2 → URL Generator** → scopes `bot` (+ `applications.commands`) → bot permissions
   (Send Messages, Read Message History, Add Reactions, and — if you want the bot to work in threads —
   Create/Send in Threads). Open the generated URL and invite the bot to your server.
4. Wire it in `openclaw.json → channels.discord` (token via `.env`, plus who may command it):
   ```jsonc
   "channels": { "discord": {
       "enabled": true,
       "token": { "source": "env", "id": "DISCORD_BOT_TOKEN" },
       "allowFrom": ["<YOUR_DISCORD_USER_ID>"],     // only these users can command the bot
       "execApprovals": { ... },                     // Part 8
       "threadBindings": { "enabled": true },
       "groupPolicy": "open"
       // "proxy": "http://127.0.0.1:7994"           // ADD ONLY on the proxy path (Part 5B)
   }}
   ```
   Get your Discord user id by enabling Developer Mode in Discord → right-click yourself → Copy User ID.

---

## 5. Network: direct (native) vs proxied (China / blocked)

**Decision:** can this machine open `discord.com` (and `api.openai.com` / `api.anthropic.com`) normally
in a browser?
- **Yes → you're "native".** Do **5A** (no proxy at all). This is most of the world.
- **No — behind the Great Firewall / a blocking network → you're "proxy".** Do **5B**.

### 5A. Native / direct (NOT in China) — no proxy

Nothing to install. In `openclaw.json`:
```jsonc
"proxy": { "enabled": false },
"channels": { "discord": { "proxy": null /* omit the proxy key entirely */ } }
```
Discord, OpenAI, and Anthropic all connect directly. Skip to Part 6.

### 5B. Proxy path (China / blocked network) — UniClash + a bridge

You need a VPN/proxy that can actually reach Discord + the AI APIs. The reference build uses
**UniClash** (any Clash-family or SOCKS/HTTP proxy works) exposing a local proxy port. Two wrinkles:

1. **OpenClaw speaks only HTTP proxy, not SOCKS.** If your proxy only offers SOCKS5, run the tiny
   included **HTTP→SOCKS5h bridge** in front of it:
   - `~/.openclaw/discord_socks_bridge.py` — listens on `127.0.0.1:7994`, forwards every `CONNECT` over
     **SOCKS5h** to your proxy (e.g. UniClash on `127.0.0.1:7993`). SOCKS5**h** = hostnames resolve at
     the proxy, beating local DNS poisoning.
   - Hardening it carries (keep these): `SO_EXCLUSIVEADDRUSE` singleton; **`TCP_NODELAY` + `SO_KEEPALIVE`**
     on both tunnel sockets — without `TCP_NODELAY`, Nagle delays Discord's tiny websocket heartbeats and
     Discord drops the gateway ("heartbeat ACK timeout").
   - **(Windows)** launcher `~/.openclaw/start_bridge.ps1` starts a hidden `pythonw` instance and verifies
     `Test-NetConnection 127.0.0.1 -Port 7994`. Autostart via a Startup-folder VBS. **The bridge must be
     up BEFORE the gateway** or the gateway flaps in reconnect backoff. On macOS/Linux run the same script
     under `python3` as a `launchd`/`systemd` unit.
   - *If your proxy already exposes an **HTTP** proxy port, skip the bridge* and point OpenClaw straight
     at that `http://…` URL.
2. **Point OpenClaw at the proxy** (`openclaw.json`):
   ```jsonc
   "proxy": { "enabled": true, "proxyUrl": "http://127.0.0.1:7994" },
   "channels": { "discord": { "proxy": "http://127.0.0.1:7994" } }   // Discord REST + gateway websocket
   ```
3. **AI-API traffic for the coding agents** (OpenAI/Anthropic) — set proxy env in the gateway
   environment (Part 10's `gateway.cmd`), routed straight through your proxy port:
   ```
   HTTPS_PROXY=http://127.0.0.1:7993
   HTTP_PROXY=http://127.0.0.1:7993
   NO_PROXY=localhost,127.0.0.1,::1
   ```
   Make sure your proxy's rules route the AI domains (OpenAI/Anthropic/Google-AI) out through the VPN.
4. **Sanity check:**
   ```powershell
   (Test-NetConnection 127.0.0.1 -Port 7994).TcpTestSucceeded
   curl.exe -x http://127.0.0.1:7994 -s -o NUL -w "%{http_code}" https://discord.com
   ```

---

## 6. `~/.openclaw/.env` (secrets)

OpenClaw injects these as managed env keys. **Never commit it.** Put in it whichever keys your chosen
brain/agents need:

```dotenv
# ~/.openclaw/.env
DISCORD_BOT_TOKEN=<your Discord bot token>
# --- chat brain (3A): whichever provider you chose ---
KIMI_API_KEY=<kimi.com/code key>            # example; or GLM/OpenAI/Anthropic key, named to match your provider block
# OPENAI_API_KEY / ANTHROPIC_API_KEY / GLM_API_KEY=...
```

Declare them as managed keys so the service picks them up (in `gateway.cmd`, Part 10):
```
set "OPENCLAW_SERVICE_MANAGED_ENV_KEYS=DISCORD_BOT_TOKEN,KIMI_API_KEY"
```

Secrets that live **outside** `.env` (each in its own home):
- Gateway control token → `openclaw.json` (`gateway.auth.token`)
- Exec-approvals socket token → `~/.openclaw/exec-approvals.json`
- Codex backend key/account → `~/.openclaw/acpx/codex-home/auth.json`
- Claude backend OAuth → `~/.claude/.credentials.json`

---

## 7. The ACP harness (acpx) — coding agents over Discord

ACP = **Agent Client Protocol**, a JSON-RPC-over-stdio standard. OpenClaw's **acpx** plugin is an ACP
*client*; it spawns a coding-agent CLI wrapped as an ACP *server*. Backends are chosen by `agentId`:
`claude` (set up in 3B) and/or `codex` (3C).

### 7a. Turn the plugin on (`openclaw.json`)
```jsonc
"plugins": { "allow": ["<your-provider>","acpx","discord","memory-core"],
  "entries": {
    "acpx": { "enabled": true, "config": {
      "permissionMode": "approve-reads",     // auto-allow reads, prompt for writes/exec
      "nonInteractivePermissions": "deny",    // no human to approve → deny
      "timeoutSeconds": 120
    }}
}}
```

### 7b. The adapters
acpx keeps its own npm project under `~/.openclaw/npm/projects/openclaw-acpx-<hash>/`. The ACP adapters
install there (automatically on first spawn):
- `@agentclientprotocol/claude-agent-acp` — a **JS** package; spawns the `claude` CLI. (Easy: `npm install`.)
- `@zed-industries/codex-acp` — a **native binary**; spawns/embeds `codex`. (It's compiled Rust pinned to
  a specific codex version — treat it as a black box; don't expect to rebuild it against an arbitrary
  codex version without a real porting effort.)

Both underlying CLIs must be installed + logged in (Parts 3B/3C): `claude --version`, `codex --version`.

### 7c. The wrappers (`~/.openclaw/acpx/`)
acpx generates one wrapper per backend (you don't hand-write these):
- `claude-agent-acp-wrapper.mjs` — launches the Claude adapter.
- `codex-acp-wrapper.mjs` — launches the Codex adapter; can set `CODEX_HOME` to the acpx `codex-home`.

Each spawn gets a **process lease** (cap 4096) tagging it with `leaseId`, `sessionKey`, `rootPid` so
OpenClaw can supervise + clean it up.

### 7d. Sessions & multiplicity
- Spawn from Discord / `AGENTS.md`: `sessions_spawn({ runtime: "acp", agentId: "claude" | "codex", … })`.
- Each session gets key **`agent:<agentId>:acp:<uuid>`** (a random UUID, **not** the channel id).
- **Multiple concurrent sessions are supported** (up to the lease cap). A channel/thread binds to one
  ongoing session, but you can spawn more; each is a separate CLI process with its own context.
- Transcripts: Claude → `~/.claude/projects/<workspace-slug>/<id>.jsonl`; Codex → `~/.openclaw/acpx/codex-home/sessions/…`.

### 7e. Verify a backend end-to-end (no Discord needed)
Drive a wrapper directly with a minimal ACP client (`initialize → session/new → session/prompt`). If you
get `stopReason: end_turn` with model text back, the backend works. (Good for confirming a subscription
login actually reaches the provider before wiring Discord.)

---

## 8. Exec approvals (human-in-the-loop)

When an agent wants to do something guarded (run a shell command, write a file), OpenClaw posts an
**approval card** and waits for a human. `openclaw.json → channels.discord.execApprovals`:
```jsonc
"execApprovals": {
  "enabled": true,
  "approvers": ["<YOUR_DISCORD_USER_ID>"],
  "cleanupAfterResolve": true,
  "target": "channel"                         // ONLY "dm" | "channel" | "both"
}
```
> **Gotcha:** `target` accepts only `dm` / `channel` / `both`. Any other value (e.g. `"origin"`)
> **crashes the gateway** with a schema error → bot goes offline. Always `openclaw doctor` after editing.

Guardrails (in `openclaw.json → tools`):
- `tools.deny: ["write","edit","apply_patch"]` — hard-blocks direct file-mutation tools.
- Prefer `exec.security` cautious/ask for unattended sessions; full-auto (`security:"full", ask:"off"`)
  lets shell `del`/`rm` run unprompted. The socket token lives in `~/.openclaw/exec-approvals.json`.

---

## 9. Voice (optional, speech-to-text)

Discord voice notes → local Whisper transcription → the brain. Full setup in **`whisper/WHISPER-SETUP.md`**.
In short: build **whisper.cpp** (GPU/cuBLAS if you have an NVIDIA card), download `large-v3-turbo-q8_0`,
and point `openclaw.json → tools.media.audio` at the `whisper-cli.cmd` wrapper. A load-aware router picks
GPU vs CPU by current load; Discord's native transcript is the last-resort fallback.

> The router + CLI work regardless, but the "make whisper the *primary* transcriber" and 👂/👄 reaction
> pieces are **code** patches → gated by the stale-dist wall (Part 2). They fully engage only on a
> gateway that loads fresh dist.

---

## 10. Running it

The gateway should run as a background **service** so it survives logout and self-heals.

**(Windows) — Scheduled Tasks (the reference):**
- `~/.openclaw/gateway.cmd` — sets env (managed keys, `TMPDIR`, port 18789, proxy env if on the 5B path)
  then runs `node …/openclaw/dist/index.js gateway --port 18789`.
- `~/.openclaw/gateway.vbs` — hidden launcher the task invokes.
- Task **"OpenClaw Gateway"** runs the vbs at logon.
- Task **"OpenClaw Status Board"** (optional) runs a model-free daemon that edits a `#status` Discord
  webhook every few seconds (gateway up/down + usage). Keeps working even when the gateway is down.

**(macOS/Linux):** wrap the same `node … gateway --port 18789` in a `launchd` plist / `systemd` unit /
`pm2` process. Set the proxy env there if on the 5B path.

Essentials (full cheat-sheet in **`COMMANDS.md`**):
```powershell
# (5B only) start the bridge FIRST
powershell -File ~\.openclaw\start_bridge.ps1
# start the gateway
Enable-ScheduledTask -TaskName 'OpenClaw Gateway'; Start-ScheduledTask -TaskName 'OpenClaw Gateway'
(Test-NetConnection 127.0.0.1 -Port 18789).TcpTestSucceeded     # reachable?
```

> **Two hard-won operational rules:**
> 1. **Don't rapid-restart the gateway.** It may be launched *detached* with a watchdog that respawns it
>    instantly, so `Stop-ScheduledTask` alone won't stop it — kill the node PID for a real restart. And
>    several fast restarts trip Discord's one-login-at-a-time (IDENTIFY) limit, leaving the bot stuck at
>    "awaiting gateway readiness" until you stop and let it settle.
> 2. **(5B) Bridge up before gateway**, always.

---

## 11. Personality + memory (`~/.openclaw/workspace/`)

Plain Markdown the brain reads live (edits take effect immediately):
- `AGENTS.md` — agent instructions, the `sessions_spawn` ACP recipes, and command helpers.
- `IDENTITY.md` / `SOUL.md` / `USER.md` — who the bot is, tone, who you are.
- `HEARTBEAT.md` — autonomous-tick instructions (**disable** it so the brain only runs when prompted).
- `MEMORY.md` + the `memory-core` plugin — persistent notes.
- `skills/` — your own skills.

---

## 12. Known issues / gotchas

| Symptom | Cause / fix |
|---|---|
| A **code** feature won't turn on (voice primary, a custom Discord button) | **Stale-dist wall** — gateway runs old bytecode for hand-patched `dist/*.js`. Config works, code patches don't. Fix = clean `npm` reinstall. |
| Bot stuck at "awaiting gateway readiness" | Rapid-restart → Discord IDENTIFY limit. Stop restarting; it self-recovers. (5B) Confirm the bridge is up + has `TCP_NODELAY`. |
| Gateway "won't stop" via `Stop-ScheduledTask` | Node is detached + self-healed. Kill the node PID directly, then start the task. |
| `/model <something>` "works" but isn't that model | Coding endpoints echo any model id → serve their own model. Real Claude/Codex only via the **ACP** backends. |
| Editing `openclaw.json` took the bot offline | A schema error (e.g. `execApprovals.target:"origin"`) silently kills it. Always `openclaw doctor` before restart. |
| Codex account rejects the newest model | Account path gates models by `codex` CLI version. Update codex, use an allowed model, or switch to an API key (no gate). |
| Discord drops whenever the network/VPN changes | (5B) All Discord traffic must stay proxied through the bridge → your proxy. Keep both up. |
| `python` hangs / not found | Use `python3` (or your system's Python-3 launcher). |

---

## 13. File map

| Path | Purpose | Secret? |
|---|---|---|
| `~/.openclaw/.env` | `DISCORD_BOT_TOKEN` + chat-brain key(s) | **YES** |
| `~/.openclaw/openclaw.json` | main config (+ `gateway.auth.token`) | **YES** (token) |
| `~/.openclaw/discord_socks_bridge.py` | (5B) HTTP→SOCKS5h bridge | no |
| `~/.openclaw/start_bridge.ps1` | (5B) bridge launcher | no |
| `~/.openclaw/gateway.cmd` / `gateway.vbs` | (Windows) gateway service launcher | no |
| `~/.openclaw/exec-approvals.json` | approvals socket token | **YES** |
| `~/.openclaw/acpx/*-wrapper.mjs` | ACP backend wrappers (claude, codex) | no |
| `~/.openclaw/acpx/codex-home/config.toml` | Codex model/settings | no |
| `~/.openclaw/acpx/codex-home/auth.json` | Codex account/API key | **YES** |
| `~/.openclaw/workspace/AGENTS.md` + `*.md` | personality + spawn recipes | no |
| `~/.claude/settings.json` | Claude backend model | no |
| `~/.claude/.credentials.json` | Anthropic OAuth (Claude sub) | **YES** |
| `~/.codex/auth.json` | ChatGPT/Codex OAuth (Codex sub) | **YES** |
| OpenClaw install `…/openclaw/dist/` | the program (the stale-dist part) | no |

**If you version this for backup:** commit `openclaw.template.json` (redacted), the bridge + launchers,
the workspace `*.md`, and helper scripts. **Never commit** `.env`, the real `openclaw.json`, any
`auth.json` / `.credentials.json`, `exec-approvals.json`, `state/`, logs, or `node_modules`.

---

## 14. From-zero checklist

1. Install Node (+ Python 3 if you'll use the 5B bridge or voice).
2. `npm install -g openclaw`; run `openclaw` once to scaffold `~/.openclaw/`.
3. **Brain:** do 3A (API-key provider block) and/or 3B (Claude sub) and/or 3C (Codex sub). Confirm any
   CLI logs in (`claude`/`codex --version`).
4. **Discord:** create the bot, enable Message Content Intent, invite it, set `channels.discord` + `allowFrom`.
5. **Network:** native? → `proxy.enabled:false`, done. Blocked (China)? → start the bridge, set the proxy
   URLs + AI-API proxy env (5B).
6. Put secrets in `~/.openclaw/.env`; fill `openclaw.json` from `openclaw.template.json`.
7. Enable plugins: your provider, `acpx`, `discord`, `memory-core`. Set `execApprovals` + `allowFrom`.
8. Copy `workspace/AGENTS.md` + personality files; disable `HEARTBEAT.md`.
9. Register the gateway service (Scheduled Task / launchd / systemd). Optionally the Status Board.
10. `openclaw doctor` → (5B: start bridge →) start gateway → `@bot hi` in Discord.
11. Test ACP: `/acp` a coding prompt; confirm a Claude/Codex session spawns.

For the blow-by-blow history of the reference build and every fix's rationale, read `CHANGELOG.md`.
