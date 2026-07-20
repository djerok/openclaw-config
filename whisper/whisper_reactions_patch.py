"""Add 👂/👄 reactions on Discord voice messages (reversible core patch).

Reacts on the incoming voice message:
  👂 (ear)   when the audio WAS transcribed  (preflightAudioTranscript is defined = heard)
  👄 (mouth) when it was NOT transcribed      (router too busy / no transcript = not heard)

Injected in message-handler.process-*.js right after the ackReactionContext is built, where
messageChannelId + message.id + mediaList + preflightAudioTranscript + reactMessageDiscord +
ackReactionContext (valid reaction opts) are all in scope. Fire-and-forget + try/catch so it can
NEVER break message processing. Only fires when the message actually has an audio attachment.

Reapply after `openclaw update`:  python3 whisper_reactions_patch.py   then: openclaw gateway start
Revert: restore the .bak-earmouth-* file.
"""
import os, glob, re, shutil, datetime, subprocess, sys

DIST = os.path.join(os.path.expanduser("~"), "AppData", "Roaming", "npm",
                    "node_modules", "openclaw", "dist")

MARK = "__earmouth"   # idempotency marker
INJECT = ("try{if(Array.isArray(mediaList)&&mediaList.some((__m)=>__m&&typeof __m.contentType===\"string\""
          "&&__m.contentType.startsWith(\"audio/\")))reactMessageDiscord(messageChannelId,message.id,"
          "preflightAudioTranscript!==void 0?\"\U0001F442\":\"\U0001F444\",ackReactionContext)"
          ".then(()=>{},()=>{});}catch(__earmouth){}")

# match:  ackReactionContext = createDiscordAckReactionContext( ...no semicolons... ) ;
ANCHOR_RE = re.compile(r'ackReactionContext\s*=\s*createDiscordAckReactionContext\([^;]*\);')


def patch(f):
    t = open(f, encoding="utf-8").read()
    if MARK in t:
        print("  already has ear/mouth reactions — skipping:", os.path.basename(f)); return True
    m = ANCHOR_RE.search(t)
    if not m:
        print("  ANCHOR NOT FOUND — patch manually:", os.path.basename(f)); return False
    if len(ANCHOR_RE.findall(t)) != 1:
        print("  anchor not unique — aborting:", os.path.basename(f)); return False
    bak = f + ".bak-earmouth-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    shutil.copy2(f, bak)
    new = t[:m.end()] + INJECT + t[m.end():]
    open(f, "w", encoding="utf-8").write(new)
    r = subprocess.run(["node", "--check", f], capture_output=True, text=True)
    if r.returncode != 0:
        shutil.copy2(bak, f)
        print("  SYNTAX ERROR, restored backup:", r.stderr[:200]); return False
    print("  EAR/MOUTH reactions added + node --check PASSED (backup:", os.path.basename(bak) + ")"); return True


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    files = [f for f in glob.glob(os.path.join(DIST, "message-handler.process-*.js"))
             if ANCHOR_RE.search(open(f, encoding="utf-8", errors="replace").read()) or MARK in open(f, encoding="utf-8", errors="replace").read()]
    if not files:
        print("No message-handler.process file with the anchor found."); sys.exit(1)
    ok = all(patch(f) for f in files)
    print("\nDone." + ("" if ok else "  (needs manual attention)"))
    print("Restart: openclaw gateway start")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
