"""MeloTTS speaker — no voice cloning, just the base MeloTTS English voice.

Use this when you want to A/B the OpenVoice clone overlay against the bare
MeloTTS output and judge how much of the "doesn't sound like me" effect is
the accent baseline (MeloTTS) versus the timbre clone (OpenVoice converter).
"""
from __future__ import annotations

import logging
import os
import tempfile
import threading
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from .. import config as _cfg
from .player import Player

if TYPE_CHECKING:
    import numpy as np

os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
os.environ.setdefault("TQDM_DISABLE", "1")
os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")


def _install_threadsafe_tqdm_lock() -> None:
    """See tts_openvoice for the rationale — MeloTTS uses tqdm too."""
    try:
        import tqdm.std as _tqdm_std  # type: ignore[import-not-found]
    except ImportError:
        return
    if not hasattr(_tqdm_std.tqdm, "_lock"):
        _tqdm_std.tqdm._lock = threading.RLock()  # type: ignore[attr-defined]


_install_threadsafe_tqdm_lock()

_log = logging.getLogger("sgr.tts.melo")
_cfg.USER_DATA_DIR.mkdir(parents=True, exist_ok=True)
_log_handler = logging.FileHandler(_cfg.USER_DATA_DIR / "tts.log")
_log_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
_log.addHandler(_log_handler)
_log.setLevel(logging.INFO)


def _best_device() -> str:
    try:
        import torch  # type: ignore[import-not-found]

        if torch.backends.mps.is_available():
            return "mps"
        if torch.cuda.is_available():
            return "cuda"
    except Exception:
        pass
    return "cpu"


class MeloSpeaker:
    """Bare MeloTTS English speaker. Picks one of the 5 English regional voices."""

    def __init__(
        self,
        language: Literal["EN_INDIA", "EN_US", "EN_BR", "EN_AU", "EN_Default"] = "EN_Default",
        device: str | None = None,
        speed: float = 1.0,
    ):
        self.language = language
        self.device = device or _best_device()
        self.speed = speed
        self._tts = None
        self._speaker_id: int | None = None
        self._load_lock = threading.Lock()
        self.player = Player()
        self._speaking = threading.Event()
        self._loading = threading.Event()

    def state(self) -> str:
        if self._speaking.is_set():
            return "speaking"
        if self._loading.is_set():
            return "loading"
        return "idle"

    def is_speaking(self) -> bool:
        return self._speaking.is_set()

    def _ensure_loaded(self) -> None:
        if self._tts is not None:
            return
        with self._load_lock:
            if self._tts is not None:
                return
            from melo.api import TTS as MeloTTS  # type: ignore[import-not-found]

            _log.info("loading MeloTTS English on %s", self.device)
            tts = MeloTTS(language="EN", device=self.device)
            spk2id_raw = tts.hps.data.spk2id
            try:
                spk2id = dict(spk2id_raw)
            except (TypeError, ValueError):
                spk2id = {
                    k: v
                    for k, v in getattr(spk2id_raw, "__dict__", {}).items()
                    if not k.startswith("_")
                }
            cand = self.language.upper()
            candidates = {cand, cand.replace("_", "-"), cand.replace("-", "_")}
            speaker_id = None
            for k, v in spk2id.items():
                if str(k).upper() in candidates:
                    speaker_id = v
                    break
            if speaker_id is None:
                fallback_key = next(iter(spk2id)) if spk2id else None
                speaker_id = spk2id[fallback_key] if fallback_key is not None else 0
                _log.warning(
                    "MeloTTS speaker %s not in %s; using %s",
                    candidates,
                    sorted(str(k) for k in spk2id),
                    fallback_key,
                )
            self._tts = tts
            self._speaker_id = speaker_id
            _log.info("MeloTTS ready (speaker_id=%s)", speaker_id)

    def synthesize(self, text: str) -> tuple["np.ndarray", int]:
        import numpy as np
        import soundfile as sf

        self._ensure_loaded()
        with tempfile.TemporaryDirectory() as td:
            out_path = Path(td) / "out.wav"
            self._tts.tts_to_file(text, self._speaker_id, str(out_path), speed=self.speed)  # type: ignore[union-attr]
            data, sr = sf.read(str(out_path))
        pcm = np.asarray(data, dtype=np.float32)
        if pcm.ndim > 1:
            pcm = pcm.mean(axis=1)
        pcm = np.clip(pcm, -1.0, 1.0)
        return (pcm * 32767.0).astype(np.int16), int(sr)

    def say(self, text: str) -> None:
        text = (text or "").strip()
        if not text:
            return
        self.stop()

        def _run() -> None:
            self._loading.set()
            try:
                pcm, sr = self.synthesize(text)
                _log.info("melo synth ok: %d samples @ %d Hz", len(pcm), sr)
                self._loading.clear()
                self._speaking.set()
                self.player.play(pcm, sr, block=True)
            except Exception:
                _log.exception("melo say() failed for text=%r", text[:80])
            finally:
                self._loading.clear()
                self._speaking.clear()

        threading.Thread(target=_run, daemon=True).start()

    def stop(self) -> None:
        self.player.stop()
