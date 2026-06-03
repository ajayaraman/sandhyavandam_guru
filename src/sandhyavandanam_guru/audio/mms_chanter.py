"""MMS-Sanskrit TTS fallback chanter.

Uses facebook/mms-tts-san (Meta MMS, VITS architecture) to synthesize a mantra
from its Sanskrit text when the canonical assets/mantras/<id>.wav is missing.
Runs locally — no API, no network after the first model download (~150 MB).

The TUI's Chanter consults this when has() is False, so the user hears something
(machine-Sanskrit, not silence) for steps they haven't yet recorded themselves.
"""
from __future__ import annotations

import logging
import threading
from typing import TYPE_CHECKING

from .. import config as _cfg
from .player import Player

if TYPE_CHECKING:
    import numpy as np

_log = logging.getLogger("sgr.mms")
_cfg.USER_DATA_DIR.mkdir(parents=True, exist_ok=True)
_h = logging.FileHandler(_cfg.USER_DATA_DIR / "tts.log")
_h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
_log.addHandler(_h)
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


class MMSChanter:
    """Synthesizes Sanskrit mantra audio from text via facebook/mms-tts-san."""

    MODEL_ID = "facebook/mms-tts-san"

    def __init__(self, device: str | None = None):
        self.device = device or _best_device()
        self._model = None
        self._tok = None
        self._load_lock = threading.Lock()
        self.player = Player()
        self._chanting = threading.Event()
        self._gen = 0
        self._gen_lock = threading.Lock()

    def state(self) -> str:
        return "chanting" if self._chanting.is_set() else "idle"

    def is_chanting(self) -> bool:
        return self._chanting.is_set()

    def _ensure_loaded(self) -> None:
        if self._model is not None:
            return
        with self._load_lock:
            if self._model is not None:
                return
            from transformers import AutoTokenizer, VitsModel  # type: ignore[import-not-found]

            _log.info("loading MMS-san on %s", self.device)
            self._tok = AutoTokenizer.from_pretrained(self.MODEL_ID)
            self._model = VitsModel.from_pretrained(self.MODEL_ID).to(self.device)
            self._model.eval()
            _log.info("MMS-san ready")

    def synthesize(self, text: str) -> tuple["np.ndarray", int]:
        import numpy as np
        import torch

        self._ensure_loaded()
        inputs = self._tok(text, return_tensors="pt")  # type: ignore[union-attr]
        inputs = {k: v.to(self.device) for k, v in inputs.items()}
        with torch.no_grad():
            out = self._model(**inputs).waveform  # type: ignore[union-attr]
        wav = out.detach().to("cpu").squeeze().float().numpy()
        wav = np.clip(wav, -1.0, 1.0)
        sr = int(self._model.config.sampling_rate)  # type: ignore[union-attr]
        return (wav * 32767.0).astype(np.int16), sr

    def chant(self, _mantra_id: str, text: str, on_finish=None) -> None:
        text = (text or "").strip()
        if not text:
            if on_finish:
                on_finish()
            return
        with self._gen_lock:
            self._gen += 1
            my_gen = self._gen
        self.stop()

        def _run() -> None:
            try:
                pcm, sr = self.synthesize(text)
                with self._gen_lock:
                    if my_gen != self._gen:
                        return
                self._chanting.set()
                _log.info("mms chant ok: %d samples @ %d Hz", len(pcm), sr)
                self.player.play(pcm, sr, block=True)
            except Exception:
                _log.exception("mms chant failed for text=%r", text[:80])
            finally:
                self._chanting.clear()
                if on_finish:
                    try:
                        on_finish()
                    except Exception:
                        _log.exception("on_finish callback failed")

        threading.Thread(target=_run, daemon=True).start()

    def stop(self) -> None:
        self.player.stop()
