# Whisper voice transcription — download + setup

Local speech-to-text for Discord voice notes, using **whisper.cpp** (GPU-accelerated) fronted by a
load-aware router. Discord's native transcript is only the last-resort fallback.

## What's in this folder
- `whisper-cli.cmd` — thin CLI wrapper OpenClaw calls to transcribe a file.
- `whisper_router.py` — **load-aware router**: picks the GPU or CPU whisper build + model based on
  current system load, so a busy GPU doesn't stall transcription.
- `whisper_primary_patch.py` — makes the router the **primary** transcriber (runs before Discord's
  native transcript). *(dist patch — subject to the stale-dist wall; see main CHANGELOG.)*
- `whisper_reactions_patch.py` — adds the 👂 / 👄 reactions on voice messages (heard-keyword / heard-no-keyword).

> Paths inside the scripts are hard-coded to `C:\Users\ericc\.openclaw\whisper\…`. Adjust them for your
> machine. The large model + compiled binaries are **not** committed (too big) — build/download below.

## 1. Build whisper.cpp with GPU (cuBLAS)

```powershell
git clone https://github.com/ggerganov/whisper.cpp
cd whisper.cpp
# GPU build (NVIDIA, e.g. RTX 5070 — ~8x faster than CPU):
cmake -B build -DGGML_CUDA=1
cmake --build build --config Release
# The CLI binary lands in build\bin\Release\whisper-cli.exe
```
Also keep a **CPU** build (no `-DGGML_CUDA`) — the router falls back to it when the GPU is busy.
Drop the GPU binary under `whisper/gpu/` and the CPU one under `whisper/bin/` (that's the layout the
router expects).

## 2. Download the model

```powershell
# primary: large-v3-turbo, q8_0 quant (fast + accurate)
curl.exe -L -o ggml-large-v3-turbo-q8_0.bin `
  https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-large-v3-turbo-q8_0.bin
# tiny fallback:
curl.exe -L -o ggml-base.en.bin `
  https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-base.en.bin
```
Put both `.bin` files in this `whisper/` folder. Always run with `-l en` for English.

## 3. Wire it into OpenClaw

1. Point OpenClaw's transcription at `whisper-cli.cmd` (via the router) instead of the native path.
2. Apply `whisper_primary_patch.py` to run whisper before Discord's transcript, and
   `whisper_reactions_patch.py` for the 👂/👄 feedback — both from `~/.openclaw/workspace/tools/`:
   ```
   PYTHONPATH=. python3 whisper_primary_patch.py
   PYTHONPATH=. python3 whisper_reactions_patch.py
   ```
3. Restart the gateway.

> **Reality check:** the whisper-primary + reaction pieces are *code* patches, so they're gated by the
> stale-dist wall documented in the main CHANGELOG — they only take effect on a gateway that loads
> fresh dist (i.e. after a clean reinstall). The router + CLI themselves are external and work
> regardless.
