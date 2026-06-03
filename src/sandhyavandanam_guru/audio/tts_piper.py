from __future__ import annotations

import io
import threading
import wave
from typing import TYPE_CHECKING

from .player import Player
from .voices import ensure_piper_voice

if TYPE_CHECKING:
    import numpy as np


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
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            self._voice_obj.synthesize(text, wf)  # type: ignore[union-attr]
        buf.seek(0)
        with wave.open(buf, "rb") as wf:
            sr = wf.getframerate()
            raw = wf.readframes(wf.getnframes())
        pcm = np.frombuffer(raw, dtype=np.int16)
        return pcm, sr

    def say(self, text: str) -> None:
        text = (text or "").strip()
        if not text:
            return
        # Cancel any in-flight clip so the new line wins immediately.
        self.stop()

        def _run() -> None:
            try:
                pcm, sr = self.synthesize(text)
                self.player.play(pcm, sr)
            except Exception:
                # Silently degrade: a missing voice file or audio device should not
                # crash the TUI. The visual coaching line is still shown.
                pass

        self._worker = threading.Thread(target=_run, daemon=True)
        self._worker.start()

    def stop(self) -> None:
        self.player.stop()
