"""F5-TTS speaker — full prosody + timbre clone via flow-matching DiT.

Architectural difference vs OpenVoice v2:
  - OpenVoice clones spectral timbre only; prosody/cadence come from MeloTTS.
    Result: your voice timbre painted on top of MeloTTS's stock speaking style.
  - F5-TTS clones the *whole voice* — timbre + pitch contour + breathiness +
    pacing. Result: output reads like you would read it. Slower, larger model.

API: F5TTS.infer(ref_file, ref_text, gen_text, …). Needs the ref_file AND its
transcript. A 10-15 s clean English clip with a known transcript is ideal —
exactly what scripts/record_clone_ref.py produces.
"""
from __future__ import annotations

import logging
import os
import threading
from pathlib import Path
from typing import TYPE_CHECKING

from .. import config as _cfg
from .player import Player

if TYPE_CHECKING:
    import numpy as np

os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
os.environ.setdefault("TQDM_DISABLE", "1")
os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")


def _install_threadsafe_tqdm_lock() -> None:
    try:
        import tqdm.std as _tqdm_std  # type: ignore[import-not-found]
    except ImportError:
        return
    if not hasattr(_tqdm_std.tqdm, "_lock"):
        _tqdm_std.tqdm._lock = threading.RLock()  # type: ignore[attr-defined]


_install_threadsafe_tqdm_lock()

_log = logging.getLogger("sgr.tts.f5")
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


class F5Speaker:
    """Guru voice via F5-TTS — clones the full speaking voice from one 10-15 s clip."""

    def __init__(
        self,
        ref_wav: Path,
        ref_text: str,
        model: str = "F5TTS_v1_Base",
        device: str | None = None,
        speed: float = 0.85,
        nfe_step: int = 16,
        remove_silence: bool = False,
    ):
        self.ref_wav = str(ref_wav)
        self.ref_text = (ref_text or "").strip()
        self.model_name = model
        self.device = device or _best_device()
        self.speed = float(speed)
        self.nfe_step = int(nfe_step)
        self.remove_silence = bool(remove_silence)
        self._engine = None
        self._load_lock = threading.Lock()
        self.player = Player()
        self._speaking = threading.Event()
        self._loading = threading.Event()
        self._gen = 0
        self._gen_lock = threading.Lock()

    def state(self) -> str:
        if self._speaking.is_set():
            return "speaking"
        if self._loading.is_set():
            return "loading"
        return "idle"

    def is_speaking(self) -> bool:
        return self._speaking.is_set()

    def _ensure_loaded(self) -> None:
        if self._engine is not None:
            return
        with self._load_lock:
            if self._engine is not None:
                return
            from f5_tts.api import F5TTS  # type: ignore[import-not-found]

            _log.info("loading F5-TTS model=%s on %s", self.model_name, self.device)
            self._engine = F5TTS(model=self.model_name, device=self.device)
            _log.info("F5-TTS ready")

    def synthesize(self, text: str) -> tuple["np.ndarray", int]:
        import numpy as np

        self._ensure_loaded()
        wav, sr, _ = self._engine.infer(  # type: ignore[union-attr]
            ref_file=self.ref_wav,
            ref_text=self.ref_text,
            gen_text=text,
            file_wave=None,
            file_spec=None,  # note: spec, not spect (changed in upstream f5-tts)
            remove_silence=self.remove_silence,
            speed=self.speed,
            nfe_step=self.nfe_step,
        )
        pcm = np.asarray(wav, dtype=np.float32)
        if pcm.ndim > 1:
            pcm = pcm.mean(axis=1)
        pcm = np.clip(pcm, -1.0, 1.0)
        return (pcm * 32767.0).astype(np.int16), int(sr)

    def say(self, text: str) -> None:
        text = (text or "").strip()
        if not text:
            return
        with self._gen_lock:
            self._gen += 1
            my_gen = self._gen
        self.stop()

        def _run() -> None:
            self._loading.set()
            try:
                pcm, sr = self.synthesize(text)
                with self._gen_lock:
                    if my_gen != self._gen:
                        _log.info("f5 synth stale (gen %d != %d); discarding", my_gen, self._gen)
                        return
                _log.info("f5 synth ok: %d samples @ %d Hz", len(pcm), sr)
                self._loading.clear()
                self._speaking.set()
                self.player.play(pcm, sr, block=True)
            except Exception:
                _log.exception("f5 say() failed for text=%r", text[:80])
            finally:
                self._loading.clear()
                self._speaking.clear()

        threading.Thread(target=_run, daemon=True).start()

    def stop(self) -> None:
        self.player.stop()
