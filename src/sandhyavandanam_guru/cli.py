from __future__ import annotations

import argparse
import sys

from . import config
from .coaching_loader import load_coaching
from .ritual_loader import load_ritual


def _print_dry_run(ritual_path: str) -> int:
    ritual = load_ritual(ritual_path)
    print(f"{ritual.sandhya_kind} sandhya — {len(ritual.steps)} steps")
    for i, step in enumerate(ritual.steps, 1):
        print(f"  {i:>2}. {step.name_sa:<26} ({step.advance_rule})")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="sgr", description="Sandhyavandanam Guru — terminal coach.")
    p.add_argument(
        "--ritual",
        default=str(config.RITUAL_DIR / "pratah_rigveda.yaml"),
        help="Path to the ritual YAML.",
    )
    p.add_argument(
        "--coaching",
        default=str(config.RITUAL_DIR / "coaching_en.yaml"),
        help="Path to the English coaching YAML (spoken by the guru voice).",
    )
    p.add_argument(
        "--no-audio",
        action="store_true",
        help="Disable Piper TTS — silent study-aid mode.",
    )
    p.add_argument("--dry-run", action="store_true", help="List steps and exit (no TUI).")
    args = p.parse_args(argv)

    if args.dry_run:
        return _print_dry_run(args.ritual)

    from .tui import GuruApp

    ritual = load_ritual(args.ritual)
    coaching = load_coaching(args.coaching)
    speaker = None
    if not args.no_audio:
        try:
            from .audio.tts_piper import PiperSpeaker

            speaker = PiperSpeaker(config.PIPER_VOICE_EN)
        except Exception as e:
            print(f"[sgr] Piper voice unavailable ({e}); continuing in silent mode.", file=sys.stderr)
    GuruApp(ritual, coaching=coaching, speaker=speaker).run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
