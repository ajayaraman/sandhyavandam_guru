from __future__ import annotations

import logging
import threading
from typing import TYPE_CHECKING

from .. import config as _cfg
from .player import Player
from .voices import ensure_piper_voice

if TYPE_CHECKING:
    import numpy as np

_log = logging.getLogger("sgr.tts")
_cfg.USER_DATA_DIR.mkdir(parents=True, exist_ok=True)
_log_handler = logging.FileHandler(_cfg.USER_DATA_DIR / "tts.log")
_log_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
_log.addHandler(_log_handler)
_log.setLevel(logging.INFO)


class PiperSpeaker:
    """Guru voice: synthesize English coaching lines via Piper and play them.

    Voice loading and synth happen lazily on first say() and are cached for
    the life of the process. say() returns immediately after kicking off
    a background worker so the TUI stays responsive; stop() cancels playback.
    """

    def __init__(self, voice: str):
        self.voice = voice
        self._voice_obj = None
        self._load_lock = threading.Lock()
        self.player = Player()
        self._worker: threading.Thread | None = None
        self._speaking = threading.Event()
        self._loading = threading.Event()

    def is_speaking(self) -> bool:
        return self._speaking.is_set()

    def state(self) -> str:
        if self._speaking.is_set():
            return "speaking"
        if self._loading.is_set():
            return "loading"
        return "idle"

    def _ensure_loaded(self) -> None:
        if self._voice_obj is not None:
            return
        with self._load_lock:
            if self._voice_obj is not None:
                return
            onnx, cfg = ensure_piper_voice(self.voice)
            from piper import PiperVoice  # type: ignore[import-not-found]

            self._voice_obj = PiperVoice.load(str(onnx), config_path=str(cfg))

    def synthesize(self, text: str) -> tuple["np.ndarray", int]:
        import numpy as np

        self._ensure_loaded()
        voice = self._voice_obj
        # piper-tts >=1.4 returns an iterable of AudioChunk (one per sentence).
        arrays = [chunk.audio_int16_array for chunk in voice.synthesize(text)]  # type: ignore[union-attr]
        if not arrays:
            return np.zeros(0, dtype=np.int16), voice.config.sample_rate  # type: ignore[union-attr]
        pcm = np.concatenate(arrays)
        return pcm, voice.config.sample_rate  # type: ignore[union-attr]

    def say(self, text: str) -> None:
        text = (text or "").strip()
        if not text:
            return
        # Cancel any in-flight clip so the new line wins immediately.
        self.stop()

        def _run() -> None:
            self._loading.set()
            try:
                pcm, sr = self.synthesize(text)
                _log.info("synth ok: %d samples @ %d Hz", len(pcm), sr)
                self._loading.clear()
                self._speaking.set()
                self.player.play(pcm, sr, block=True)
            except Exception:
                _log.exception("piper say() failed for text=%r", text[:80])
            finally:
                self._loading.clear()
                self._speaking.clear()

        self._worker = threading.Thread(target=_run, daemon=True)
        self._worker.start()

    def stop(self) -> None:
        self.player.stop()
