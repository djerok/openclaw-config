#!/usr/bin/env python3
"""Discord SLASH-COMMAND bot for the clanker stack, hosted on the 'clanker 2' identity.

Why a separate bot: OpenClaw owns clanker's gateway connection (for messages) and does
NOT handle slash-command interactions — those arrive over a gateway WebSocket. So clanker-2
holds its own WebSocket, registers the `/` commands, and on each one posts the equivalent
TEXT command into the channel. OpenClaw allow-lists clanker-2, so it executes that text
(spawn a Claude Code session, stop a run, ask the assistant, etc.).

Slash commands need only the `applications.commands` authorization + default intents — no
Message Content intent required.
"""
import os, sys
import discord
from discord import app_commands

# Under pythonw.exe there is no console -> sys.stdout/stderr are None -> print() crashes.
# Redirect to a log so the bot runs headless (same pattern as discord_socks_bridge.py).
_LOG = os.path.expanduser("~/.openclaw/slash_bot.log")
if sys.stdout is None:
    try:
        sys.stdout = open(_LOG, "a", buffering=1, encoding="utf-8")
    except Exception:
        sys.stdout = open(os.devnull, "w")
if sys.stderr is None:
    sys.stderr = sys.stdout


def load_env(path):
    env = {}
    try:
        for line in open(path, encoding="utf-8"):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip().strip('"').strip("'")
    except Exception:
        pass
    return env


ENV = load_env(os.path.expanduser("~/.openclaw/.env"))
TOKEN = ENV.get("TEST_BOT_TOKEN") or os.environ.get("TEST_BOT_TOKEN")
APP_ID = ENV.get("TEST_BOT_APP_ID") or os.environ.get("TEST_BOT_APP_ID")
# Discord is only reachable through the HTTP->SOCKS5h bridge on 7994 (UniClash tunnel);
# direct connections fail with WinError 121. Route REST + gateway WS through it, like the
# stop-watcher and OpenClaw do.
PROXY = ENV.get("DISCORD_HTTP_PROXY") or os.environ.get("DISCORD_HTTP_PROXY") or "http://127.0.0.1:7994"

intents = discord.Intents.none()
intents.guilds = True
client = discord.Client(intents=intents, proxy=PROXY,
                        application_id=int(APP_ID) if APP_ID else None)
tree = app_commands.CommandTree(client)


async def run_text(interaction: discord.Interaction, text: str, note: str):
    """Ack the interaction (ephemeral) and post `text` so OpenClaw executes it."""
    try:
        await interaction.response.send_message(f"✅ {note}", ephemeral=True)
    except Exception:
        pass
    try:
        await interaction.channel.send(text)
    except Exception as e:
        try:
            await interaction.followup.send(f"⚠️ couldn't post the command: {e}", ephemeral=True)
        except Exception:
            pass


@tree.command(name="claude", description="Spawn a Claude Code (claude-cli) session in this thread")
async def claude(interaction: discord.Interaction):
    await run_text(interaction, "/acp spawn claude", "Spawning Claude Code…")


@tree.command(name="claude_here", description="Bind THIS channel to a Claude Code session")
async def claude_here(interaction: discord.Interaction):
    await run_text(interaction, "/acp spawn claude --bind here", "Binding this channel to Claude…")


@tree.command(name="ask", description="Send a prompt to the assistant")
@app_commands.describe(prompt="What to ask the assistant")
async def ask(interaction: discord.Interaction, prompt: str):
    await run_text(interaction, f"clanker {prompt}", "Sent to the assistant…")


@tree.command(name="stop", description="Abort the current run")
async def stop(interaction: discord.Interaction):
    await run_text(interaction, "/stop", "Stopping the current run…")


@tree.command(name="cmds", description="List the clanker slash commands")
async def cmds(interaction: discord.Interaction):
    await interaction.response.send_message(
        "**Clanker slash commands**\n"
        "`/claude` — spawn a Claude Code (claude-cli) session\n"
        "`/claude_here` — bind this channel to Claude Code\n"
        "`/ask <prompt>` — ask the assistant\n"
        "`/stop` — abort the current run",
        ephemeral=True,
    )


@tree.command(name="help", description="Full, detailed reference for every clanker command")
async def help_cmd(interaction: discord.Interaction):
    emb = discord.Embed(
        title="🦞 Clanker — Full Command Reference",
        description="Three ways to control clanker: **Discord slash commands** (this bot), "
                    "**Claude's own commands** typed inside a session, and **emoji reactions**.",
        color=0x5865F2,
    )
    emb.add_field(
        name="🟢 Discord slash commands  (type `/` — autocompletes)",
        value=(
            "`/claude` — Spawn a **Claude Code** session in a new thread. The *spawn* is one-time; then "
            "you talk **in that thread** and it remembers. Re-running starts a fresh session.\n"
            "`/claude_here` — **Bind this channel** to Claude Code. Afterwards just **type normally** — "
            "every message goes to Claude, continuously, no command needed. Best for real back-and-forth.\n"
            "`/ask <prompt>` — Send one prompt to the main assistant. Context carries across calls in the "
            "same channel (and across plain `clanker …` messages).\n"
            "`/stop` — Abort the current run (same as the 🛑 reaction).\n"
            "`/cmds` — Short list.  `/help` — this reference."
        ),
        inline=False,
    )
    emb.add_field(
        name="🔵 Inside a Claude session  (type as text — no autocomplete)",
        value=(
            "Claude Code's own slash commands. Type them as a message in a `/claude` thread or a "
            "`/claude_here` channel:\n"
            "`/model <name>` — switch model (e.g. `/model sonnet`).\n"
            "`/context` — show token / context usage.\n"
            "`/clear` — clear the conversation.  `/compact` — summarize & compress history.\n"
            "…plus skill commands (e.g. `/investigate`). Commands that normally open a picker need an "
            "argument here (no TUI over Discord)."
        ),
        inline=False,
    )
    emb.add_field(
        name="🟣 Reactions  (click the emoji)",
        value=(
            "🛑 — Stop / abort the run (auto-added to your prompts).\n"
            "🎧 — “heard you” ack on a voice message.\n"
            "🎤 — the transcript of your voice message.\n"
            "🔐 ✅ / ❌ — Approve or deny a tool the Claude session wants to run.\n"
            "❓ 1️⃣–9️⃣ / ❌ — Answer a multiple-choice question from Claude (tap a number, or ❌ to cancel)."
        ),
        inline=False,
    )
    emb.add_field(
        name="💡 Tips",
        value=(
            "• **One-shot vs ongoing:** `/ask` and `/claude` are triggers — the conversation behind them "
            "persists. For “just chat”, use `/claude_here`.\n"
            "• **Wake word:** outside a bound channel, start a message with **clanker** to get the "
            "assistant's attention.\n"
            "• Permission 🔐 prompts appear in `approve-reads` mode; multiple-choice ❓ prompts appear "
            "whenever Claude asks you to pick."
        ),
        inline=False,
    )
    emb.set_footer(text="clanker · OpenClaw gateway + Claude Code (acpx) · slash bot = clanker-2")
    await interaction.response.send_message(embed=emb, ephemeral=True)


@client.event
async def on_ready():
    total = 0
    for g in client.guilds:
        try:
            tree.copy_global_to(guild=g)
            synced = await tree.sync(guild=g)
            total += len(synced)
            print(f"[slash_bot] synced {len(synced)} cmds -> guild {g.id} ({g.name})", flush=True)
        except Exception as e:
            print(f"[slash_bot] SYNC FAILED guild {g.id} ({g.name}): {e}", flush=True)
    if not client.guilds:
        print("[slash_bot] WARNING: bot is in 0 guilds — invite it first", flush=True)
    print(f"[slash_bot] ready as {client.user} — {total} commands live across "
          f"{len(client.guilds)} guild(s)", flush=True)
    if APP_ID:
        print("[slash_bot] if commands don't appear, re-invite with applications.commands scope:\n"
              f"  https://discord.com/oauth2/authorize?client_id={APP_ID}"
              "&scope=bot+applications.commands&permissions=85056", flush=True)


if not TOKEN:
    raise SystemExit("[slash_bot] TEST_BOT_TOKEN not found in ~/.openclaw/.env")

# single-instance lock (also lets clanker_control detect us by port, like the watcher)
import socket as _sk
_LOCK = _sk.socket(_sk.AF_INET, _sk.SOCK_STREAM)
try:
    _LOCK.bind(("127.0.0.1", 18791)); _LOCK.listen(1)
except OSError:
    print("[slash_bot] another instance holds :18791 — exiting", flush=True); raise SystemExit(0)

client.run(TOKEN, log_handler=None)
