"""Make WHISPER primary over Discord's native voice transcript (reversible core patch).

WHY: OpenClaw's preflight transcriber `transcribeFirstAudio` (which runs tools.media.audio =
our load-aware whisper router) only processes audio where `!att.alreadyTranscribed`. When
Discord attaches its own native transcript, the audio is marked `alreadyTranscribed` → the
router is SKIPPED → Discord's (flaky) transcript wins. Removing that one condition makes the
router transcribe every voice note → whisper is primary; Discord's native transcript is only
used when the router yields nothing (machine too busy — the bottom rung of the ladder).

PATCH (media-runtime-*.js, one unique line):
  attachments.find((att) => att && isAudioAttachment(att) && !att.alreadyTranscribed)
  -> attachments.find((att) => att && isAudioAttachment(att))

Reapply after `openclaw update` (patch lives in global node_modules):
    python3 whisper_primary_patch.py
Idempotent, backs up, validates with `node --check`. Then: openclaw gateway start.
To REVERT: restore the .bak-whisperprimary-* file (or re-add ` && !att.alreadyTranscribed`).
"""
import os, glob, shutil, datetime, subprocess, sys

DIST = os.path.join(os.path.expanduser("~"), "AppData", "Roaming", "npm",
                    "node_modules", "openclaw", "dist")
OLD = "attachments.find((att) => att && isAudioAttachment(att) && !att.alreadyTranscribed)"
NEW = "attachments.find((att) => att && isAudioAttachment(att))"


def patch(f):
    t = open(f, encoding="utf-8").read()
    if NEW in t and OLD not in t:
        print("  already whisper-primary — skipping:", os.path.basename(f)); return True
    if t.count(OLD) != 1:
        print("  ANCHOR NOT FOUND (core layout changed) — patch manually:", os.path.basename(f)); return False
    bak = f + ".bak-whisperprimary-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    shutil.copy2(f, bak)
    open(f, "w", encoding="utf-8").write(t.replace(OLD, NEW, 1))
    r = subprocess.run(["node", "--check", f], capture_output=True, text=True)
    if r.returncode != 0:
        shutil.copy2(bak, f)
        print("  SYNTAX ERROR, restored backup:", r.stderr[:200]); return False
    print("  WHISPER PRIMARY + node --check PASSED (backup:", os.path.basename(bak) + ")"); return True


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    files = [f for f in glob.glob(os.path.join(DIST, "media-runtime-*.js"))
             if OLD in open(f, encoding="utf-8", errors="replace").read()
             or NEW in open(f, encoding="utf-8", errors="replace").read()]
    if not files:
        # fall back to scanning all dist for the anchor
        files = [f for f in glob.glob(os.path.join(DIST, "*.js"))
                 if OLD in open(f, encoding="utf-8", errors="replace").read()]
    if not files:
        print("No file with the anchor found under", DIST); sys.exit(1)
    ok = all(patch(f) for f in files)
    print("\nDone." + ("" if ok else "  (needs manual attention)"))
    print("Restart: openclaw gateway start")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
