from __future__ import annotations

import urllib.request
from pathlib import Path

PIPER_HF_BASE = "https://huggingface.co/rhasspy/piper-voices/resolve/main"

# Map of voice id -> path under the piper-voices repo (without .onnx / .onnx.json suffix).
PIPER_VOICE_PATHS: dict[str, str] = {
    "en_US-lessac-medium": "en/en_US/lessac/medium/en_US-lessac-medium",
    "en_US-amy-medium": "en/en_US/amy/medium/en_US-amy-medium",
    "en_GB-alan-medium": "en/en_GB/alan/medium/en_GB-alan-medium",
}


def piper_cache_dir() -> Path:
    d = Path.home() / ".cache" / "sandhyavandanam_guru" / "piper"
    d.mkdir(parents=True, exist_ok=True)
    return d


def ensure_piper_voice(voice: str) -> tuple[Path, Path]:
    """Download the Piper voice files into the cache dir if missing. Returns (onnx, json)."""
    rel = PIPER_VOICE_PATHS.get(voice)
    if rel is None:
        raise ValueError(
            f"unknown piper voice {voice!r}; known: {sorted(PIPER_VOICE_PATHS)}"
        )
    cache = piper_cache_dir()
    onnx = cache / f"{voice}.onnx"
    cfg = cache / f"{voice}.onnx.json"
    if not onnx.exists():
        urllib.request.urlretrieve(f"{PIPER_HF_BASE}/{rel}.onnx", onnx)
    if not cfg.exists():
        urllib.request.urlretrieve(f"{PIPER_HF_BASE}/{rel}.onnx.json", cfg)
    return onnx, cfg
