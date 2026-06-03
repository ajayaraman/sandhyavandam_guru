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


def step_openvoice_checkpoints() -> Path:
    from sandhyavandanam_guru.audio import tts_openvoice as ov

    cache = ov._openvoice_cache_dir()
    print(f"[1/3] OpenVoice checkpoints → {cache}")
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
    print("[2/3] UniDic dictionary (one-time, ~500 MB)")
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


def step_melotts() -> None:
    print("[3/3] MeloTTS English model (downloads on first init from HF)")
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
    step_openvoice_checkpoints()
    if not args.skip_unidic:
        step_unidic()
    if not args.skip_melo:
        step_melotts()
    print(f"\nDone in {time.time() - t0:.1f}s. You can now run `uv run sgr --voice openvoice` warm.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
