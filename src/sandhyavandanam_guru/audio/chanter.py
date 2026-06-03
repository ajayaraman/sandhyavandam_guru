"""Mantra chanter — plays canonical wavs from assets/mantras/.

Separate from the TTS speaker so a stop() to one doesn't kill the other and so
the status bar can distinguish "guru is speaking" from "guru is chanting".
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

_log = logging.getLogger("sgr.chanter")
_cfg.USER_DATA_DIR.mkdir(parents=True, exist_ok=True)
_h = logging.FileHandler(_cfg.USER_DATA_DIR / "tts.log")
_h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
_log.addHandler(_h)
_log.setLevel(logging.INFO)


def _load_wav(path: Path) -> tuple["np.ndarray", int]:
    import numpy as np

    with wave.open(str(path), "rb") as wf:
        sr = wf.getframerate()
        nframes = wf.getnframes()
        nchan = wf.getnchannels()
        raw = wf.readframes(nframes)
    pcm = np.frombuffer(raw, dtype=np.int16)
    if nchan > 1:
        pcm = pcm.reshape(-1, nchan).mean(axis=1).astype(np.int16)
    return pcm, sr


class Chanter:
    def __init__(self, bank_dir: Path):
        self.bank_dir = Path(bank_dir)
        self.player = Player()
        self._chanting = threading.Event()
        self._gen = 0
        self._gen_lock = threading.Lock()

    def state(self) -> str:
        return "chanting" if self._chanting.is_set() else "idle"

    def is_chanting(self) -> bool:
        return self._chanting.is_set()

    def has(self, mantra_id: str) -> bool:
        return (self.bank_dir / f"{mantra_id}.wav").exists()

    def chant(self, mantra_id: str, on_finish=None) -> None:
        path = self.bank_dir / f"{mantra_id}.wav"
        if not path.exists():
            _log.info("chanter: no wav for %s", mantra_id)
            if on_finish:
                on_finish()
            return
        with self._gen_lock:
            self._gen += 1
            my_gen = self._gen
        self.stop()

        def _run() -> None:
            try:
                pcm, sr = _load_wav(path)
                with self._gen_lock:
                    if my_gen != self._gen:
                        return
                self._chanting.set()
                _log.info("chant %s: %d samples @ %d Hz", mantra_id, len(pcm), sr)
                self.player.play(pcm, sr, block=True)
            except Exception:
                _log.exception("chanter failed for %s", mantra_id)
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
