"""Phase 0.5 — record the Sanskrit STT eval set.

Walks you through a curated set of 10 mantras drawn from the ritual YAML, covering
short / medium / long lengths. You record each one twice across two runs:

    uv run python scripts/record_eval.py --variant clean
    uv run python scripts/record_eval.py --variant with_error

The "with_error" variant is where you intentionally introduce small mispronunciations
(drop an aspirate, shorten a long vowel, swap a retroflex for a dental). That gives
us the data needed to score "religious-error recall" — does each candidate ASR
model actually flag the mistakes, or does it smooth them over?

Output: WAV files under eval/recordings/ + a manifest JSON per variant.
"""

from __future__ import annotations

import argparse
import json
import sys
import wave
from pathlib import Path

import numpy as np
import sounddevice as sd

from sandhyavandanam_guru import config
from sandhyavandanam_guru.ritual_loader import load_ritual

SAMPLE_RATE = 16_000  # Whisper + Gemma 4 audio both want 16 kHz mono.

# Curated 10-mantra eval set: balanced across lengths, drawn from the 26-step ritual.
EVAL_CLIPS: list[tuple[str, str]] = [
    ("m10_asavaadityo", "short"),
    ("m06_achyuta_short", "short"),
    ("m15_nyaasam", "short"),
    ("m08_gayatri_arghya", "medium"),
    ("m03_sankalpam", "medium"),
    ("m22_harihara", "medium"),
    ("m24_samarpanam", "medium"),
    ("m26_rakshaa", "medium"),
    ("m05_praashanam_pratah", "long"),
    ("m18_mitrasya_pratah", "long"),
]


def record_until_enter() -> np.ndarray:
    print("  ● Recording... press [Enter] to STOP.", flush=True)
    frames: list[np.ndarray] = []

    def cb(indata, *_):
        frames.append(indata.copy())

    with sd.InputStream(channels=1, samplerate=SAMPLE_RATE, callback=cb, dtype="float32"):
        try:
            input()
        except (KeyboardInterrupt, EOFError):
            pass
    return np.concatenate(frames, axis=0) if frames else np.zeros((0, 1), dtype="float32")


def save_wav(path: Path, audio_f32: np.ndarray) -> float:
    mono = audio_f32.reshape(-1)
    pcm = (np.clip(mono, -1.0, 1.0) * 32767).astype(np.int16)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SAMPLE_RATE)
        w.writeframes(pcm.tobytes())
    return len(pcm) / SAMPLE_RATE


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--variant", choices=["clean", "with_error"], default="clean")
    p.add_argument("--out", default=str(config.PROJECT_ROOT / "eval" / "recordings"))
    p.add_argument("--start", type=int, default=1, help="Skip to clip N (1-indexed).")
    args = p.parse_args()

    ritual = load_ritual(config.RITUAL_DIR / "pratah_rigveda.yaml")
    mantra_by_id = {step.mantra_id: step for step in ritual.steps}

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"\nPhase 0.5 eval recording — variant={args.variant}")
    print(f"Output: {out_dir}")
    try:
        mic_name = sd.query_devices(kind="input")["name"]
    except Exception as e:
        mic_name = f"(unavailable: {e})"
    print(f"Mic device: {mic_name}\n")
    if args.variant == "with_error":
        print("✱ This is the WITH-ERROR pass. For each clip, deliberately introduce a")
        print("  small mispronunciation (e.g. drop an aspirate, shorten a long vowel,")
        print("  swap a retroflex with a dental). Keep the rest correct.\n")

    manifest = []
    total = len(EVAL_CLIPS)

    for i, (mid, length) in enumerate(EVAL_CLIPS, 1):
        if i < args.start:
            continue
        step = mantra_by_id.get(mid)
        if step is None:
            print(f"!! mantra {mid} not found in ritual — skipping")
            continue

        print("=" * 70)
        print(f"[{i}/{total}]  {mid}   ({length})   variant={args.variant}")
        print("=" * 70)
        print(f"Mantra (from step '{step.name_sa}'):\n")
        print(step.mantra_text.strip())
        print(f"\nMeaning: {step.translation}\n")

        cmd = input("[Enter]=record   s=skip   q=quit  > ").strip().lower()
        if cmd == "q":
            break
        if cmd == "s":
            print("  skipped\n")
            continue

        audio = record_until_enter()
        if audio.size == 0:
            print("  !! empty recording, skipping\n")
            continue

        path = out_dir / f"{mid}_{args.variant}.wav"
        duration = save_wav(path, audio)
        print(f"  ✓ saved: {path.name}   ({duration:.1f}s)\n")

        manifest.append({
            "mantra_id": mid,
            "variant": args.variant,
            "length_bucket": length,
            "path": str(path.relative_to(config.PROJECT_ROOT)),
            "duration_s": round(duration, 2),
            "expected_text": step.mantra_text.strip(),
            "step_id": step.id,
            "step_name_sa": step.name_sa,
        })

    manifest_path = out_dir / f"manifest_{args.variant}.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False))
    print(f"\nManifest written: {manifest_path}   ({len(manifest)} clips)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
