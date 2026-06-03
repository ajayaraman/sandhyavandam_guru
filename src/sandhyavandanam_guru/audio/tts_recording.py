"""Recorded-coaching speaker — plays your own voice from assets/coaching/<step_id>.wav.

Implements the Speaker protocol so it slots into the TUI exactly like Piper or
Sarvam. say(text) is a no-op when no matching recording exists.

The speaker maintains a small map from coaching-line *text* to step id, populated
by the TUI via prime(coaching). When say() is called with a text it has indexed,
it plays the corresponding wav.
"""
from __future__ import annotations

import logging
import threading
import wave
from pathlib import Path
from typing import TYPE_CHECKING

from .. import config as _cfg
from .player import Player

if TYPE_CHECKING:
    import numpy as np

_log = logging.getLogger("sgr.tts.recording")
_cfg.USER_DATA_DIR.mkdir(parents=True, exist_ok=True)
_h = logging.FileHandler(_cfg.USER_DATA_DIR / "tts.log")
_h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
_log.addHandler(_h)
_log.setLevel(logging.INFO)


def _load_wav(path: Path) -> tuple["np.ndarray", int]:
    import numpy as np

    with wave.open(str(path), "rb") as wf:
        sr = wf.getframerate()
        nchan = wf.getnchannels()
        raw = wf.readframes(wf.getnframes())
    pcm = np.frombuffer(raw, dtype=np.int16)
    if nchan > 1:
        pcm = pcm.reshape(-1, nchan).mean(axis=1).astype(np.int16)
    return pcm, sr


class RecordedSpeaker:
    """Plays user-recorded English instruction clips, keyed by coaching text."""

    def __init__(self, coaching_dir: Path):
        self.coaching_dir = Path(coaching_dir)
        self.player = Player()
        self._speaking = threading.Event()
        self._loading = threading.Event()
        self._gen = 0
        self._gen_lock = threading.Lock()
        # text → step_id resolution table, primed by the TUI.
        self._text_to_step: dict[str, str] = {}

    def prime(self, coaching) -> None:
        """Populate the text → step_id resolver from a Coaching object."""
        if coaching is None:
            return
        for step_id, line in coaching.lines.items():
            self._text_to_step[line.strip()] = step_id

    def state(self) -> str:
        if self._speaking.is_set():
            return "speaking"
        if self._loading.is_set():
            return "loading"
        return "idle"

    def is_speaking(self) -> bool:
        return self._speaking.is_set()

    def _resolve_path(self, text: str) -> Path | None:
        text = (text or "").strip()
        step_id = self._text_to_step.get(text)
        if not step_id:
            return None
        path = self.coaching_dir / f"{step_id}.wav"
        return path if path.exists() else None

    def say(self, text: str) -> None:
        text = (text or "").strip()
        if not text:
            return
        path = self._resolve_path(text)
        if path is None:
            _log.info("recording: no coaching wav for %s…", text[:40])
            return
        with self._gen_lock:
            self._gen += 1
            my_gen = self._gen
        self.stop()

        def _run() -> None:
            self._loading.set()
            try:
                pcm, sr = _load_wav(path)
                with self._gen_lock:
                    if my_gen != self._gen:
                        return
                _log.info("recorded coaching: %s (%d samples @ %d Hz)", path.name, len(pcm), sr)
                self._loading.clear()
                self._speaking.set()
                self.player.play(pcm, sr, block=True)
            except Exception:
                _log.exception("recorded say() failed for %s", path)
            finally:
                self._loading.clear()
                self._speaking.clear()

        threading.Thread(target=_run, daemon=True).start()

    def stop(self) -> None:
        self.player.stop()
