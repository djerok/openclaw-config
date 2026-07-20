"""Load-aware whisper transcription router for OpenClaw.

OpenClaw calls this via `whisper-cli.cmd` (basename must be `whisper-cli` so OpenClaw
reads the `-of <base>.txt` output). It receives OpenClaw's whisper args, IGNORES the
--model it was given, and instead picks an engine/model based on live GPU + CPU load:

    GPU util < 40%   -> large (turbo-q8) on GPU     (best, only when the GPU is free)
    elif CPU util < 40% -> large (turbo-q8) on CPU
    elif GPU util < 75% -> base.en on GPU           (lighter model when moderately busy)
    elif CPU util < 75% -> base.en on CPU
    else             -> DO NOTHING (write no .txt)  -> OpenClaw falls back to Discord's
                        native transcript (the last-resort rung of the ladder)

Thresholds are the LARGE_MAX / BASE_MAX constants below — edit to taste.

It writes the transcript to `<of-base>.txt` (the path OpenClaw expects) using the real
whisper-cli.exe (GPU cuBLAS build or CPU build). Decisions are logged to
`whisper_router.log` next to this file.
"""
import os, sys, subprocess, time

HERE = os.path.dirname(os.path.abspath(__file__))
LOG = os.path.join(HERE, "whisper_router.log")
NO_WINDOW = 0x08000000 if os.name == "nt" else 0

# --- engines -------------------------------------------------------------
GPU_EXE = os.path.join(HERE, "gpu", "bin", "Release", "whisper-cli.exe")
CPU_EXE = os.path.join(HERE, "bin", "Release", "whisper-cli.exe")
LARGE   = os.path.join(HERE, "ggml-large-v3-turbo-q8_0.bin")
BASE    = os.path.join(HERE, "ggml-base.en.bin")

# --- load thresholds (utilization %, run the tier when load is BELOW it) --
LARGE_MAX = 40     # big model only when GPU/CPU is quite free
BASE_MAX  = 75     # light model up to moderately busy; above this -> Discord


def log(msg):
    try:
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(time.strftime("%Y-%m-%d %H:%M:%S ") + msg + "\n")
    except Exception:
        pass


def gpu_util():
    """GPU utilization % (int), or None if no GPU / nvidia-smi unavailable."""
    try:
        r = subprocess.run(
            ["nvidia-smi", "--query-gpu=utilization.gpu", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=6, creationflags=NO_WINDOW)
        return int(r.stdout.strip().splitlines()[0])
    except Exception as e:
        log("gpu_util error: " + str(e))
        return None


def cpu_util():
    """CPU utilization % (float), or None."""
    try:
        import psutil
        return psutil.cpu_percent(interval=0.2)
    except Exception as e:
        log("cpu_util error: " + str(e))
        return None


def pick(gpu, cpu):
    """Return (exe, model, tag) per the ladder, or None to hand off to Discord."""
    if gpu is not None and gpu < LARGE_MAX:
        return GPU_EXE, LARGE, f"large/GPU (gpu={gpu}%)"
    if cpu is not None and cpu < LARGE_MAX:
        return CPU_EXE, LARGE, f"large/CPU (cpu={cpu}%)"
    if gpu is not None and gpu < BASE_MAX:
        return GPU_EXE, BASE, f"base/GPU (gpu={gpu}%)"
    if cpu is not None and cpu < BASE_MAX:
        return CPU_EXE, BASE, f"base/CPU (cpu={cpu}%)"
    return None


def get_of_base(args):
    """The -of / --output-file value OpenClaw passed (== the media path)."""
    for i, a in enumerate(args):
        if a in ("-of", "--output-file") and i + 1 < len(args):
            return args[i + 1]
    return None


def main():
    args = sys.argv[1:]
    of_base = get_of_base(args)
    # input file = last positional arg (OpenClaw passes {{MediaPath}})
    inp = args[-1] if args else None
    if not of_base or not inp:
        log("ABORT: could not parse -of/input from args: " + " ".join(args))
        sys.exit(0)   # produce nothing -> Discord fallback

    gpu, cpu = gpu_util(), cpu_util()
    choice = pick(gpu, cpu)
    if choice is None:
        log(f"TOO BUSY gpu={gpu} cpu={cpu} -> no whisper, hand off to Discord")
        sys.exit(0)   # no .txt written -> OpenClaw falls back to Discord's transcript

    exe, model, tag = choice
    cmd = [exe, "--model", model, "-l", "en", "-otxt", "-of", of_base, "-np", inp]
    log(f"route={tag} gpu={gpu} cpu={cpu} model={os.path.basename(model)}")
    try:
        t = time.time()
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=120, creationflags=NO_WINDOW)
        dt = time.time() - t
        wrote = os.path.exists(of_base + ".txt")
        log(f"  done rc={r.returncode} {dt:.1f}s wrote_txt={wrote}")
        if r.returncode != 0:
            log("  stderr: " + (r.stderr or "")[:300])
    except Exception as e:
        log("  RUN ERROR: " + str(e))
    sys.exit(0)


if __name__ == "__main__":
    main()
