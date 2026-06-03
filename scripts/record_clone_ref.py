"""Record a single clean English reference clip for OpenVoice voice cloning.

Why: OpenVoice clones a timbre fingerprint from whatever's in the reference clip.
The Phase 0.5 Sanskrit chant recordings give a chant-flavored clone (steady drone
pitch, elongated vowels, ritual prosody). A 10–15 s clip of you speaking English
naturally gives a clone that sounds like you talking, which is what you want for
the coaching voice.

Usage:
    uv sync --extra dev --extra eval
    uv run python scripts/record_clone_ref.py

After recording, point the app at the clip by adding this to
~/.config/sandhyavandanam_guru/config.yaml:

    tts:
      openvoice:
        clone_ref: eval/recordings/clone_ref_en.wav

Or pass it explicitly:

    uv run sgr --voice openvoice --clone-ref eval/recordings/clone_ref_en.wav
"""
from __future__ import annotations

import argparse
import sys
import time
import wave
from pathlib import Path

from sandhyavandanam_guru import config

SAMPLE_RATE = 16000
CHANNELS = 1
SAMPWIDTH = 2  # int16

PROMPT_TEXT = (
    "My name is Arvind. I live in Boston. Today I will perform the morning sandhya. "
    "I am sitting facing east, and I am about to begin the achamana ritual. "
    "I take a little water in my right palm and sip it three times."
)


def record(out_path: Path, prompt_text: str) -> None:
    try:
        import numpy as np
        import sounddevice as sd
    except ImportError as e:
        raise SystemExit(
            "missing audio deps; run `uv sync --extra dev --extra eval` first"
        ) from e

    print()
    print("=" * 70)
    print("OpenVoice clone reference recorder")
    print("=" * 70)
    print()
    print("Read the following sentence aloud, naturally, at your usual pace.")
    print("Speak clearly. About 12–15 seconds is ideal.")
    print()
    print(f"  > {prompt_text}")
    print()
    print(f"Output: {out_path}")
    print(f"Format: {SAMPLE_RATE} Hz mono PCM-16 (what OpenVoice prefers).")
    print()

    try:
        input("Press [Enter] to start recording …")
    except EOFError:
        raise SystemExit("no tty")

    # Allocate a generous buffer (30 s) and use a streaming InputStream so we
    # can stop whenever the user hits Enter again.
    max_seconds = 30
    buf = np.zeros(int(SAMPLE_RATE * max_seconds), dtype=np.int16)
    pos = {"n": 0}
    print("Recording … press [Enter] to stop.")

    def callback(indata, frames, time_info, status) -> None:  # type: ignore[no-untyped-def]
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
    print(f"  recorded {duration:.1f} s ({pos['n']} samples)")
    if duration < 5:
        print("⚠  too short — re-run and aim for 10–15 seconds.")
    if duration > 25:
        print("⚠  long — OpenVoice prefers ≤20 s of clean speech.")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(out_path), "wb") as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(SAMPWIDTH)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(buf[: pos["n"]].tobytes())

    print(f"✓ saved {out_path}  ({duration:.1f} s)")
    print()
    print("Point the app at it:")
    print(f"  uv run sgr --voice openvoice --clone-ref {out_path.relative_to(config.PROJECT_ROOT)}")
    print()
    print("Or persist by adding to ~/.config/sandhyavandanam_guru/config.yaml:")
    print("  tts:")
    print("    openvoice:")
    print(f"      clone_ref: {out_path.relative_to(config.PROJECT_ROOT)}")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--out",
        default=str(config.PROJECT_ROOT / "eval" / "recordings" / "clone_ref_en.wav"),
        help="Output wav path (default: eval/recordings/clone_ref_en.wav).",
    )
    p.add_argument(
        "--prompt",
        default=PROMPT_TEXT,
        help="Text to read aloud.",
    )
    args = p.parse_args(argv)
    record(Path(args.out), args.prompt)
    return 0


if __name__ == "__main__":
    sys.exit(main())
