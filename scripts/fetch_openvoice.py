"""Pre-download all assets needed by the OpenVoice guru voice.

Run this once after install. It fetches:

    1. OpenVoice v2 converter (~440 MB) + the EN-India base-speaker embedding (~1 MB)
    2. MeloTTS English model (~600 MB) — by instantiating it once
    3. UniDic dictionary if not already present (~500 MB; one-time)

Total disk: ~1.5 GB. Network: ~1 GB.

You can interrupt and re-run — each step is idempotent and resumable file-by-file.
"""
from __future__ import annotations

import argparse
import sys
import time
import urllib.request
from pathlib import Path


def _human(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


class _Reporter:
    """urlretrieve progress callback — keeps one line refreshing on the terminal."""

    def __init__(self, label: str):
        self.label = label
        self.t0 = time.time()
        self.last_print = 0.0

    def __call__(self, block_num: int, block_size: int, total_size: int) -> None:
        if total_size <= 0:
            return
        done = min(block_num * block_size, total_size)
        now = time.time()
        if now - self.last_print < 0.25 and done < total_size:
            return
        self.last_print = now
        pct = 100.0 * done / total_size
        elapsed = max(now - self.t0, 0.001)
        rate = done / elapsed
        bar_w = 30
        filled = int(bar_w * done / total_size)
        bar = "█" * filled + "░" * (bar_w - filled)
        end = "\n" if done >= total_size else "\r"
        sys.stdout.write(
            f"  {self.label}  [{bar}] {pct:5.1f}%  "
            f"{_human(done)} / {_human(total_size)}  @ {_human(int(rate))}/s   {end}"
        )
        sys.stdout.flush()


def step_wavmark() -> None:
    """Pre-cache the wavmark watermarking model that OpenVoice loads at startup.

    Why: ToneColorConverter.__init__ calls wavmark.load_model() which fires
    hf_hub_download(); tqdm inside hub uses multiprocessing locks which crash
    when the call originates from a daemon thread. Caching it here means the
    runtime call hits an already-downloaded file and never spawns anything.
    """
    print("[1/4] WavMark watermark model (used by OpenVoice converter)")
    try:
        import wavmark  # type: ignore[import-not-found]
    except ImportError:
        print("  ✗ wavmark not installed; skipping (it ships with openvoice).")
        return
    print("  loading wavmark.load_model() to populate the HF cache...")
    wavmark.load_model()
    print("  ✓ wavmark cached")


def step_openvoice_checkpoints() -> Path:
    from sandhyavandanam_guru.audio import tts_openvoice as ov

    cache = ov._openvoice_cache_dir()
    print(f"[2/4] OpenVoice checkpoints → {cache}")
    for rel in ov.OV_FILES:
        dst = cache / rel
        if dst.exists():
            print(f"  ✓ already present: {rel}  ({_human(dst.stat().st_size)})")
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        url = f"{ov.OV_BASE}/{rel}"
        urllib.request.urlretrieve(url, dst, _Reporter(rel))
    return cache


def step_unidic() -> None:
    print("[3/4] UniDic dictionary (one-time, ~500 MB)")
    try:
        import unidic  # type: ignore[import-not-found]
    except ImportError:
        print("  ✗ unidic package not installed; run `uv sync --extra clone` first.")
        return
    dicdir = Path(unidic.__file__).parent / "dicdir"
    if (dicdir / "mecabrc").exists():
        print(f"  ✓ already present: {dicdir}")
        return
    import subprocess

    rc = subprocess.call([sys.executable, "-m", "unidic", "download"])
    if rc != 0:
        raise SystemExit("unidic download failed")


def step_nltk_data() -> None:
    """MeloTTS' English G2P relies on NLTK corpora; download once."""
    print("[3.5/4] NLTK corpora (cmudict + averaged_perceptron_tagger_eng + punkt)")
    try:
        import nltk  # type: ignore[import-not-found]
    except ImportError:
        print("  ✗ nltk not installed; skipping (it ships with melotts).")
        return
    for name in ("averaged_perceptron_tagger_eng", "cmudict", "punkt"):
        nltk.download(name, quiet=True)
        print(f"  ✓ {name}")


def step_melotts() -> None:
    print("[4/4] MeloTTS English model (downloads on first init from HF)")
    try:
        from melo.api import TTS as MeloTTS  # type: ignore[import-not-found]
    except ImportError:
        print("  ✗ melo not installed; run `uv sync --extra clone` first.")
        return
    print("  initialising MeloTTS(language='EN', device='cpu')...")
    MeloTTS(language="EN", device="cpu")
    print("  ✓ MeloTTS ready (weights cached under ~/.cache/huggingface)")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--skip-melo", action="store_true", help="Don't pre-load MeloTTS.")
    p.add_argument("--skip-unidic", action="store_true", help="Don't download UniDic.")
    args = p.parse_args(argv)

    t0 = time.time()
    step_wavmark()
    step_openvoice_checkpoints()
    if not args.skip_unidic:
        step_unidic()
    step_nltk_data()
    if not args.skip_melo:
        step_melotts()
    print(f"\nDone in {time.time() - t0:.1f}s. You can now run `uv run sgr --voice openvoice` warm.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
