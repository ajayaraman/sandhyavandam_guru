"""Record your own English coaching voice, one wav per ritual step.

For each step in the ritual, displays the canonical coaching line from
ritual/coaching_en.yaml. You read it your own way and the recording is saved as
assets/coaching/<step_id>.wav. The TUI's --voice recording mode plays these.

Usage:
    uv run python scripts/record_coaching.py             # record everything missing
    uv run python scripts/record_coaching.py 01 03 06    # just those step prefixes
    uv run python scripts/record_coaching.py --redo 02   # re-record an existing one
"""
from __future__ import annotations

import argparse
import sys
import wave
from pathlib import Path

from sandhyavandanam_guru import config
from sandhyavandanam_guru.coaching_loader import load_coaching
from sandhyavandanam_guru.ritual_loader import load_ritual

SAMPLE_RATE = 16_000
CHANNELS = 1
SAMPWIDTH = 2

OUT_DIR = config.PROJECT_ROOT / "assets" / "coaching"


def _record_one(step_id: str, name_sa: str, text: str) -> Path:
    try:
        import numpy as np
        import sounddevice as sd
    except ImportError as e:
        raise SystemExit("missing audio deps; run `uv sync --extra dev --extra eval` first") from e

    print()
    print("=" * 78)
    print(f"  {step_id}    ({name_sa})")
    print("=" * 78)
    print()
    for line in text.strip().splitlines():
        print(f"    {line}")
    print()
    print("  Read it in your own words and pace. The guru in the app will sound like you.")
    print("  [Enter] to start recording …", end="", flush=True)
    try:
        input()
    except EOFError:
        raise SystemExit("no tty")

    max_seconds = 60
    buf = np.zeros(int(SAMPLE_RATE * max_seconds), dtype=np.int16)
    pos = {"n": 0}
    print("  Recording … [Enter] to stop.")

    def cb(indata, frames, time_info, status):  # type: ignore[no-untyped-def]
        if status:
            print(status, file=sys.stderr)
        n = pos["n"]
        end = min(n + frames, buf.size)
        buf[n:end] = indata[: end - n, 0]
        pos["n"] = end

    with sd.InputStream(samplerate=SAMPLE_RATE, channels=CHANNELS, dtype="int16", blocksize=0, callback=cb):
        try:
            input()
        except EOFError:
            pass
    duration = pos["n"] / SAMPLE_RATE
    print(f"  recorded {duration:.1f} s")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / f"{step_id}.wav"
    with wave.open(str(out), "wb") as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(SAMPWIDTH)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(buf[: pos["n"]].tobytes())
    print(f"  ✓ {out.relative_to(config.PROJECT_ROOT)}")
    return out


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("filters", nargs="*", help="Step id prefixes to record (e.g. 01 03 06).")
    p.add_argument("--redo", action="store_true", help="Re-record steps that already have a wav.")
    args = p.parse_args(argv)

    ritual = load_ritual(config.PROJECT_ROOT / "ritual" / "pratah_rigveda.yaml")
    coaching = load_coaching(config.PROJECT_ROOT / "ritual" / "coaching_en.yaml")

    plan = []
    for step in ritual.steps:
        line = coaching.for_step(step.id)
        if not line.strip():
            continue
        if args.filters and not any(step.id.startswith(f) for f in args.filters):
            continue
        wav = OUT_DIR / f"{step.id}.wav"
        if wav.exists() and not args.redo:
            continue
        plan.append((step.id, step.name_sa, line))

    if not plan:
        print("Nothing to record. (use --redo to overwrite existing clips.)")
        return 0

    print(f"Will record {len(plan)} coaching clip(s). [Ctrl-C] at any prompt to stop.")
    try:
        for i, (sid, name, text) in enumerate(plan, 1):
            print(f"\n[{i}/{len(plan)}]")
            _record_one(sid, name, text)
    except KeyboardInterrupt:
        print("\n\n  stopped — partial progress is saved.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
