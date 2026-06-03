"""Bootstrap the canonical mantra bank under assets/mantras/.

Copies each <id>_clean.wav from eval/recordings/ into assets/mantras/<id>.wav.
The eval clips are the user's own clean recordings — priest-quality enough to
serve as the canonical bank. Anyone who wants to swap in a different chanter's
recording just drops a wav with the matching filename into assets/mantras/.

Run:
    uv run python scripts/build_mantras.py
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
RITUAL_YAML = ROOT / "ritual" / "pratah_rigveda.yaml"
EVAL_DIR = ROOT / "eval" / "recordings"
DEST_DIR = ROOT / "assets" / "mantras"


def main() -> int:
    DEST_DIR.mkdir(parents=True, exist_ok=True)
    ritual = yaml.safe_load(RITUAL_YAML.read_text())
    mantra_ids = sorted({s["mantra_id"] for s in ritual["steps"]})

    copied: list[str] = []
    missing: list[str] = []
    for mid in mantra_ids:
        src = EVAL_DIR / f"{mid}_clean.wav"
        dst = DEST_DIR / f"{mid}.wav"
        if not src.exists():
            missing.append(mid)
            continue
        if dst.exists() and dst.stat().st_size == src.stat().st_size:
            continue  # idempotent
        shutil.copy2(src, dst)
        copied.append(mid)

    print(f"mantra bank: {DEST_DIR}")
    print(f"  copied:  {len(copied)}  {copied}")
    print(f"  missing: {len(missing)}  {missing}")
    print(f"  total ritual mantras: {len(mantra_ids)}")
    if missing:
        print()
        print("To fill gaps, record the missing mantras into eval/recordings/")
        print("as <id>_clean.wav, or drop a third-party recording directly into")
        print(f"{DEST_DIR.relative_to(ROOT)}/<id>.wav.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
