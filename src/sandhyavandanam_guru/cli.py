from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import config
from .coaching_loader import load_coaching
from .ritual_loader import load_ritual
from .settings import Settings, load_settings

# Default clone reference: shortest clean recording from the Phase 0.5 eval set.
# OpenVoice clones timbre only, so a Sanskrit reference works fine.
DEFAULT_CLONE_MANTRA_ID = "m10_asavaadityo"


def _print_dry_run(ritual_path: str) -> int:
    ritual = load_ritual(ritual_path)
    print(f"{ritual.sandhya_kind} sandhya — {len(ritual.steps)} steps")
    for i, step in enumerate(ritual.steps, 1):
        print(f"  {i:>2}. {step.name_sa:<26} ({step.advance_rule})")
    return 0


def _print_logs(lines: int = 50) -> int:
    """Print the location of the TTS log and tail the last N lines."""
    log_path = config.USER_DATA_DIR / "tts.log"
    print(f"TTS log: {log_path}")
    if not log_path.exists():
        print("(no log yet — run `sgr` first)")
        return 0
    print(f"--- last {lines} lines ---")
    try:
        text = log_path.read_text()
    except OSError as e:
        print(f"(could not read log: {e})")
        return 1
    tail = text.splitlines()[-lines:]
    print("\n".join(tail) if tail else "(empty)")
    return 0


def _clear_logs() -> int:
    """Truncate the TTS log to zero bytes."""
    log_path = config.USER_DATA_DIR / "tts.log"
    if log_path.exists():
        log_path.write_text("")
        print(f"cleared {log_path}")
    else:
        print(f"no log at {log_path}")
    return 0


def _resolve_clone_ref(explicit_rel: str | None) -> Path:
    """Resolve the OpenVoice reference clip path.

    Order: explicit override > eval/recordings/manifest_clean.json default > raise.
    """
    if explicit_rel:
        p = Path(explicit_rel)
        if not p.is_absolute():
            p = config.PROJECT_ROOT / p
        return p.resolve()

    manifest_path = config.PROJECT_ROOT / "eval" / "recordings" / "manifest_clean.json"
    if not manifest_path.exists():
        raise SystemExit(
            "OpenVoice needs a reference clip. Either record one with "
            "`uv run python scripts/record_eval.py --variant clean` or set "
            "tts.openvoice.clone_ref in your config."
        )
    manifest: list[dict] = json.loads(manifest_path.read_text())
    for m in manifest:
        if m["mantra_id"] == DEFAULT_CLONE_MANTRA_ID:
            return config.PROJECT_ROOT / m["path"]
    return config.PROJECT_ROOT / manifest[0]["path"]


def _build_speaker(s: Settings):
    backend = s.tts.backend
    if backend == "openvoice":
        try:
            from .audio.tts_openvoice import OpenVoiceSpeaker

            ref_wav = _resolve_clone_ref(s.tts.openvoice.clone_ref)
            print(
                f"[sgr] OpenVoice v2 — ref={ref_wav.name} lang={s.tts.openvoice.language} "
                f"(first run downloads ~500 MB and warms MPS; please wait)",
                file=sys.stderr,
            )
            return OpenVoiceSpeaker(ref_wav=ref_wav, language=s.tts.openvoice.language)
        except Exception as e:
            print(f"[sgr] OpenVoice unavailable ({e}); falling back to Piper.", file=sys.stderr)
    if backend == "melotts":
        try:
            from .audio.tts_melotts import MeloSpeaker

            print(
                f"[sgr] MeloTTS bare — lang={s.tts.melotts.language} speed={s.tts.melotts.speed}",
                file=sys.stderr,
            )
            return MeloSpeaker(language=s.tts.melotts.language, speed=s.tts.melotts.speed)
        except Exception as e:
            print(f"[sgr] MeloTTS unavailable ({e}); falling back to Piper.", file=sys.stderr)
    try:
        from .audio.tts_piper import PiperSpeaker

        return PiperSpeaker(s.tts.piper.voice)
    except Exception as e:
        print(f"[sgr] Piper voice unavailable ({e}); continuing in silent mode.", file=sys.stderr)
        return None


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="sgr", description="Sandhyavandanam Guru — terminal coach.")
    p.add_argument("--config", default=None, help="Extra YAML overlay (deep-merged on top of defaults).")
    p.add_argument("--ritual", default=None, help="Override ritual YAML path.")
    p.add_argument("--coaching", default=None, help="Override coaching YAML path.")
    p.add_argument(
        "--voice",
        choices=["piper", "openvoice", "melotts"],
        default=None,
        help="Override tts.backend.",
    )
    p.add_argument("--clone-ref", default=None, help="Override tts.openvoice.clone_ref.")
    p.add_argument("--no-audio", action="store_true", help="Disable TTS — silent study-aid mode.")
    p.add_argument("--dry-run", action="store_true", help="List steps and exit (no TUI).")
    p.add_argument(
        "--logs",
        action="store_true",
        help="Print the TTS log path and tail the last 50 lines.",
    )
    p.add_argument(
        "--clear-logs",
        action="store_true",
        help="Truncate the TTS log to empty.",
    )
    args = p.parse_args(argv)

    if args.clear_logs:
        return _clear_logs()
    if args.logs:
        return _print_logs()

    extra_path = Path(args.config) if args.config else None
    settings = load_settings(extra_path)
    if args.voice:
        settings.tts.backend = args.voice  # type: ignore[assignment]
    if args.clone_ref:
        settings.tts.openvoice.clone_ref = args.clone_ref

    ritual_path = args.ritual or str(settings.ritual_path())
    coaching_path = args.coaching or str(settings.coaching_path())

    if args.dry_run:
        return _print_dry_run(ritual_path)

    from .tui import GuruApp

    ritual = load_ritual(ritual_path)
    coaching = load_coaching(coaching_path)
    speaker = None if args.no_audio else _build_speaker(settings)
    GuruApp(ritual, coaching=coaching, speaker=speaker).run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
