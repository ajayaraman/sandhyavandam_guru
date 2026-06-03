"""Record the missing mantras for the canonical bank.

Walks through every mantra in the ritual that doesn't yet have a clean recording
under eval/recordings/<id>_clean.wav. For each missing mantra, prints the text,
waits for [Enter] to start recording, records until [Enter] again, writes the wav.

After the run, `uv run python scripts/build_mantras.py` (which this script calls
automatically at the end) copies the new clips into assets/mantras/<id>.wav so
the TUI picks them up.

Usage:
    uv run python scripts/record_mantras.py                # record everything missing
    uv run python scripts/record_mantras.py m04 m07        # just those (prefix match)
    uv run python scripts/record_mantras.py --redo m03     # re-record an existing one
    uv run python scripts/record_mantras.py --per-line m15 # record line-by-line clips:
                                                           # m15__1.wav, m15__2.wav, …
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import time
import wave
from pathlib import Path

from sandhyavandanam_guru import config
from sandhyavandanam_guru.mantra_text import parse_mantra
from sandhyavandanam_guru.ritual_loader import load_ritual

SAMPLE_RATE = 16_000
CHANNELS = 1
SAMPWIDTH = 2
EVAL_DIR = config.PROJECT_ROOT / "eval" / "recordings"


def _prompt_start(label: str) -> None:
    print(f"\n  > [Enter] to start recording {label} …", end="", flush=True)
    try:
        input()
    except EOFError:
        raise SystemExit("no tty")


def _record_one(mantra_id: str, mantra_text: str, step_name: str) -> Path:
    try:
        import numpy as np
        import sounddevice as sd
    except ImportError as e:
        raise SystemExit(
            "missing audio deps; run `uv sync --extra dev --extra eval` first"
        ) from e

    print()
    print("=" * 78)
    print(f"  {mantra_id}    ({step_name})")
    print("=" * 78)
    print()
    for line in mantra_text.strip().splitlines():
        print(f"    {line}")
    print()
    print("  Read at a measured, teaching pace — this clip becomes the canonical")
    print("  mantra the guru plays back to the student.")
    _prompt_start(mantra_id)

    max_seconds = 120  # 2 min ceiling — Gayatri-japam class mantras are long
    buf = np.zeros(int(SAMPLE_RATE * max_seconds), dtype=np.int16)
    pos = {"n": 0}
    print("  Recording … [Enter] to stop.")

    def callback(indata, frames, time_info, status):  # type: ignore[no-untyped-def]
        if status:
            print(status, file=sys.stderr)
        n = pos["n"]
        end = min(n + frames, buf.size)
        buf[n:end] = indata[: end - n, 0]
        pos["n"] = end

    t0 = time.time()
    with sd.InputStream(
        samplerate=SAMPLE_RATE,
        channels=CHANNELS,
        dtype="int16",
        blocksize=0,
        callback=callback,
    ):
        try:
            input()
        except EOFError:
            pass
    duration = pos["n"] / SAMPLE_RATE
    print(f"  recorded {duration:.1f} s")
    if duration < 1.0:
        print("  ⚠  very short — re-run with --redo if that was a mis-press.")

    EVAL_DIR.mkdir(parents=True, exist_ok=True)
    out = EVAL_DIR / f"{mantra_id}_clean.wav"
    with wave.open(str(out), "wb") as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(SAMPWIDTH)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(buf[: pos["n"]].tobytes())
    print(f"  ✓ {out.relative_to(config.PROJECT_ROOT)}")
    return out


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "filters",
        nargs="*",
        help="Optional mantra id prefixes to limit to (e.g. m04 m07).",
    )
    p.add_argument(
        "--redo",
        action="store_true",
        help="Re-record mantras that already have a clean wav.",
    )
    p.add_argument(
        "--skip-build",
        action="store_true",
        help="Don't auto-copy into assets/mantras/ after recording.",
    )
    p.add_argument(
        "--per-line",
        action="store_true",
        help="Record each mantra line as a separate clip "
             "(<id>__1.wav, <id>__2.wav, …) directly into assets/mantras/. "
             "Used by the TUI's recording mode for line-by-line delivery.",
    )
    args = p.parse_args(argv)

    ritual = load_ritual(config.PROJECT_ROOT / "ritual" / "pratah_rigveda.yaml")
    # de-dupe by mantra_id, preserve first occurrence (step order)
    seen: set[str] = set()
    plan: list[tuple[str, str, str]] = []
    for step in ritual.steps:
        if step.mantra_id in seen:
            continue
        seen.add(step.mantra_id)
        if args.filters and not any(step.mantra_id.startswith(f) for f in args.filters):
            continue
        plan.append((step.mantra_id, step.mantra_text, step.name_sa))

    if args.per_line:
        return _record_per_line(plan, redo=args.redo)

    # Whole-mantra mode (original behavior).
    plan = [(mid, txt, name) for (mid, txt, name) in plan
            if args.redo or not (EVAL_DIR / f"{mid}_clean.wav").exists()]
    if not plan:
        print("Nothing to record — the bank is complete for the requested set.")
        print(f"(use --redo to re-record existing clips.)")
        return 0

    print(f"Will record {len(plan)} mantra(s). [Ctrl-C] at any prompt to stop.")
    print()
    try:
        for i, (mid, text, name) in enumerate(plan, 1):
            print(f"\n[{i}/{len(plan)}]")
            _record_one(mid, text, name)
    except KeyboardInterrupt:
        print("\n\n  stopped — partial progress is saved.")

    if not args.skip_build:
        print("\nUpdating assets/mantras/ from the new recordings …\n")
        subprocess.run(
            [sys.executable, str(config.PROJECT_ROOT / "scripts" / "build_mantras.py")],
            check=False,
        )
    return 0


def _record_per_line(plan, *, redo: bool) -> int:
    """Record each mantra line as a separate clip directly into assets/mantras/."""
    bank = config.PROJECT_ROOT / "assets" / "mantras"
    bank.mkdir(parents=True, exist_ok=True)

    units: list[tuple[str, int, str, str]] = []  # (mid, line_idx, sanskrit, action)
    for mid, text, name in plan:
        parsed = parse_mantra(text)
        for i, line in enumerate(parsed.lines, start=1):
            out = bank / f"{mid}__{i}.wav"
            if out.exists() and not redo:
                continue
            units.append((mid, i, line.sanskrit, line.action or ""))
    if not units:
        print("Nothing to record per-line. (use --redo to overwrite existing.)")
        return 0

    print(f"Will record {len(units)} mantra line(s) into assets/mantras/.")
    print("[Ctrl-C] at any prompt to stop.\n")
    try:
        for j, (mid, idx, sanskrit, action) in enumerate(units, 1):
            label = f"{mid}__{idx}"
            text = sanskrit + ((f"   ({action})" if action else ""))
            print(f"\n[{j}/{len(units)}]")
            wav = _record_one_to(label, text, "", bank)
            # _record_one_to writes to bank/<label>.wav
            assert wav.exists()
    except KeyboardInterrupt:
        print("\n\n  stopped — partial progress is saved.")
    return 0


def _record_one_to(label: str, mantra_text: str, step_name: str, out_dir: Path) -> Path:
    """Same flow as _record_one but writes to a chosen directory + filename."""
    import numpy as np
    import sounddevice as sd
    import time

    print()
    print("=" * 78)
    print(f"  {label}")
    print("=" * 78)
    print()
    for line in mantra_text.strip().splitlines():
        print(f"    {line}")
    print()
    print("  Read this single line at the pace you want the student to hear it.")
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

    out = out_dir / f"{label}.wav"
    with wave.open(str(out), "wb") as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(SAMPWIDTH)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(buf[: pos["n"]].tobytes())
    print(f"  ✓ {out.relative_to(config.PROJECT_ROOT)}")
    return out


if __name__ == "__main__":
    sys.exit(main())
