#!/usr/bin/env python3
"""
acp_manual_approve_patch.py — durable, idempotent patch that turns acpx's headless
auto-DENY into a Discord ✅/❌ manual-approve prompt.

OpenClaw's embedded ACP runtime (runtime-DB8FvL7H.js) decides tool permissions in
`resolveReadOrPromptPermission`: reads are auto-approved, and everything else hits
`if (!canPromptForPermission$1()) return resolveNonInteractivePermission(...)` —
i.e. because the harness is headless it just DENIES. We replace that deny with a
file-IPC prompt: write a pending request, block-poll for a decision, return
allow/deny. stop_watcher.py posts the 🔐 ✅/❌ message to the ACP thread and writes
the decision. Re-apply after `openclaw update`.
"""
import re, subprocess, sys, os, glob

DIST = os.path.join(os.path.expanduser("~"), "AppData", "Roaming", "npm", "node_modules", "openclaw", "dist")

HELPER = r'''async function __clankerDiscordPermPrompt(params, allowOption, rejectOption, nonInteractivePolicy) {
  try {
    const { mkdirSync, writeFileSync, existsSync, readFileSync, unlinkSync } = await import("node:fs");
    const { homedir } = await import("node:os");
    const { join } = await import("node:path");
    const base = join(homedir(), ".openclaw", "acp_perms");
    const pend = join(base, "pending"), dec = join(base, "decided");
    mkdirSync(pend, { recursive: true }); mkdirSync(dec, { recursive: true });
    const reqid = String(Date.now()) + "-" + Math.random().toString(36).slice(2, 8);
    let tool = "tool", title = "";
    try { const tc = params && params.toolCall; if (tc) { tool = tc.kind || tc.title || "tool"; title = tc.title || ""; } } catch (e) {}
    const pfile = join(pend, reqid + ".json");
    writeFileSync(pfile, JSON.stringify({ reqid, tool, title, ts: Date.now() }));
    const dfile = join(dec, reqid + ".json");
    const deadline = Date.now() + 90000;
    while (Date.now() < deadline) {
      if (existsSync(dfile)) {
        let d = {}; try { d = JSON.parse(readFileSync(dfile, "utf8")); } catch (e) {}
        try { unlinkSync(dfile); } catch (e) {}
        try { unlinkSync(pfile); } catch (e) {}
        if (d && d.allow && allowOption) return { response: selected(allowOption.optionId) };
        return resolveNonInteractivePermission(nonInteractivePolicy, rejectOption);
      }
      await new Promise((r) => setTimeout(r, 1000));
    }
    try { unlinkSync(pfile); } catch (e) {}
  } catch (e) {}
  return resolveNonInteractivePermission(nonInteractivePolicy, rejectOption);
}
'''

DENY_LINE = "if (!canPromptForPermission$1()) return resolveNonInteractivePermission(nonInteractivePolicy, rejectOption);"
NEW_LINE  = "if (!canPromptForPermission$1()) return __clankerDiscordPermPrompt(params, allowOption, rejectOption, nonInteractivePolicy);"

def patch_file(fp):
    s = open(fp, encoding="utf-8").read()
    if "__clankerDiscordPermPrompt" in s:
        # already patched — but re-apply the deny-line swap in case dist was refreshed
        if DENY_LINE in s:
            s = s.replace(DENY_LINE, NEW_LINE)
            open(fp, "w", encoding="utf-8").write(s)
            return "reapplied deny-swap"
        return "already patched"
    if DENY_LINE not in s:
        return "SKIP: deny line not found"
    # inject helper right before the resolveReadOrPromptPermission decl, swap the deny line.
    # anchor on "async function" if present (it is) so we don't split "async" off it.
    anchor = "async function resolveReadOrPromptPermission" if "async function resolveReadOrPromptPermission" in s else "function resolveReadOrPromptPermission"
    idx = s.index(anchor)
    s = s[:idx] + HELPER + "\n" + s[idx:]
    s = s.replace(DENY_LINE, NEW_LINE)
    open(fp, "w", encoding="utf-8").write(s)
    return "PATCHED"

def main():
    targets = [f for f in glob.glob(os.path.join(DIST, "runtime-*.js"))
               if "resolveReadOrPromptPermission" in open(f, encoding="utf-8", errors="ignore").read()]
    if not targets:
        print("no target runtime bundle found"); sys.exit(1)
    for fp in targets:
        r = patch_file(fp)
        chk = subprocess.run(["node", "--check", fp], capture_output=True, text=True)
        print(f"  {os.path.basename(fp)}: {r} | node --check: {'OK' if chk.returncode==0 else 'FAIL ' + chk.stderr[:200]}")
        if chk.returncode != 0:
            sys.exit(2)

if __name__ == "__main__":
    main()
