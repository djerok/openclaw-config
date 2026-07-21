#!/usr/bin/env python3
"""acp_elicit_bridge_patch.py — bridge Claude's multiple-choice questions (AskUserQuestion
-> ACP elicitation) to Discord numbered reactions.

The claude-agent-acp adapter's `handleAskUserQuestion` builds an ACP form and calls
`this.client.unstable_createElicitation(...)`. OpenClaw's client doesn't implement it, so the
call throws and the question dies ("Could not present the question to the user"). We replace that
call with a file-IPC bridge: write a pending elicitation, block-poll for a decision, and return a
`{action:"accept", content:{question_0:<label>}}` shaped exactly like applyAskElicitationResponse
expects. stop_watcher.py renders the options as 1..9 reactions and writes the pick.

Idempotent, node --check gated. Re-apply after `openclaw update`.
"""
import os, subprocess, sys

ADAPTER = os.path.expanduser(
    "~/.openclaw/npm/projects/openclaw-acpx-052d680d6d/node_modules/@openclaw/acpx/"
    "node_modules/@agentclientprotocol/claude-agent-acp/dist/acp-agent.js")

CALL_OLD = "await this.client.unstable_createElicitation(createRequest, signal)"
CALL_NEW = "await __clankerDiscordElicit(createRequest, questions, signal)"

HELPER = r'''
async function __clankerDiscordElicit(createRequest, questions, signal) {
  const { mkdirSync, writeFileSync, existsSync, readFileSync, unlinkSync } = await import("node:fs");
  const { homedir } = await import("node:os");
  const { join } = await import("node:path");
  const base = join(homedir(), ".openclaw", "acp_elicit");
  const pend = join(base, "pending"), dec = join(base, "decided");
  mkdirSync(pend, { recursive: true }); mkdirSync(dec, { recursive: true });
  const id = String(Date.now()) + "-" + Math.random().toString(36).slice(2, 8);
  const qs = (questions || []).map((q) => ({
    question: q.question,
    options: (q.options || []).map((o) => o.label),
  }));
  const pfile = join(pend, id + ".json"), dfile = join(dec, id + ".json");
  writeFileSync(pfile, JSON.stringify({ id, questions: qs,
    message: createRequest && createRequest.message, ts: Date.now() }));
  const deadline = Date.now() + 110000;
  try {
    while (Date.now() < deadline) {
      if (signal && signal.aborted) break;
      if (existsSync(dfile)) {
        let d = {}; try { d = JSON.parse(readFileSync(dfile, "utf8")); } catch (e) {}
        try { unlinkSync(dfile); } catch (e) {}
        try { unlinkSync(pfile); } catch (e) {}
        if (d && d.action === "cancel") return { action: "cancel" };
        const content = {};
        const picks = (d && d.picks) || {};
        for (const k of Object.keys(picks)) content["question_" + k] = picks[k];
        return { action: "accept", content };
      }
      await new Promise((r) => setTimeout(r, 1000));
    }
  } finally {
    try { unlinkSync(pfile); } catch (e) {}
  }
  return { action: "cancel" };
}
'''

def main():
    s = open(ADAPTER, encoding="utf-8").read()
    if "__clankerDiscordElicit" in s:
        if CALL_OLD in s:
            s = s.replace(CALL_OLD, CALL_NEW)
            open(ADAPTER, "w", encoding="utf-8").write(s)
            print("reapplied call-swap")
        else:
            print("already patched")
    else:
        if CALL_OLD not in s:
            print("SKIP: unstable_createElicitation call not found"); sys.exit(1)
        s = s.replace(CALL_OLD, CALL_NEW) + "\n" + HELPER
        open(ADAPTER, "w", encoding="utf-8").write(s)
        print("PATCHED")
    chk = subprocess.run(["node", "--check", ADAPTER], capture_output=True, text=True)
    print("node --check:", "OK" if chk.returncode == 0 else "FAIL " + chk.stderr[:300])
    sys.exit(0 if chk.returncode == 0 else 2)

if __name__ == "__main__":
    main()
