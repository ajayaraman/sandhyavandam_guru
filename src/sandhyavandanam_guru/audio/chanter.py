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
    def __init__(self, bank_dir: Path, mode: str = "bank", mms=None):
        """
        mode: "bank" — wav only, skip if missing
              "fallback" — wav if present, synth otherwise
              "mms"/"sarvam" — always synth, ignore wav bank
        mms: a synth-like object with .chant(mid, text, on_finish), .stop(), .is_chanting().
             Named `mms` for back-compat; can be any synth backend (MMS, Sarvam).
        """
        self.bank_dir = Path(bank_dir)
        self.mode = mode
        self.mms = mms
        self.player = Player()
        self._chanting = threading.Event()
        self._gen = 0
        self._gen_lock = threading.Lock()

    def state(self) -> str:
        if self._chanting.is_set():
            return "chanting"
        if self.mms is not None and self.mms.is_chanting():
            return "chanting"
        return "idle"

    def is_chanting(self) -> bool:
        if self._chanting.is_set():
            return True
        return self.mms is not None and self.mms.is_chanting()

    def _wav_exists(self, mantra_id: str) -> bool:
        return (self.bank_dir / f"{mantra_id}.wav").exists()

    def has_line_clip(self, mantra_id: str, line_index: int) -> bool:
        if line_index <= 0:
            return False
        return (self.bank_dir / f"{mantra_id}__{line_index}.wav").exists()

    def has_any_line_clip(self, mantra_id: str, n_lines: int) -> bool:
        return any(self.has_line_clip(mantra_id, i) for i in range(1, n_lines + 1))

    def has(self, mantra_id: str) -> bool:
        """True if we can play *something* for this mantra."""
        if self.mode in ("mms", "sarvam"):
            return self.mms is not None
        # In bank/fallback modes, either the whole-mantra wav or any per-line
        # clip is enough for the lesson to have something to play.
        has_bank = self._wav_exists(mantra_id) or self.has_line_clip(mantra_id, 1)
        if self.mode == "fallback":
            return has_bank or self.mms is not None
        return has_bank

    def chant(
        self,
        mantra_id: str,
        on_finish=None,
        mantra_text: str = "",
        line_index: int = 0,
    ) -> None:
        # Prefer the per-line clip <id>__N.wav when line_index > 0; fall back
        # to the whole-mantra clip if the per-line wav isn't recorded yet.
        if line_index > 0:
            per_line = self.bank_dir / f"{mantra_id}__{line_index}.wav"
            if per_line.exists():
                path = per_line
            else:
                path = self.bank_dir / f"{mantra_id}.wav"
        else:
            path = self.bank_dir / f"{mantra_id}.wav"
        wav_exists = path.exists()
        _log.info(
            "chant() mantra_id=%s mode=%s wav_exists=%s mms=%s",
            mantra_id, self.mode, wav_exists, self.mms is not None,
        )
        use_mms = (
            self.mode in ("mms", "sarvam")
            or (self.mode == "fallback" and not wav_exists)
        )
        if use_mms and self.mms is not None:
            if not mantra_text:
                _log.info("chanter: mms requested for %s but no text — skipping", mantra_id)
                if on_finish:
                    on_finish()
                return
            self.stop()
            self.mms.chant(mantra_id, mantra_text, on_finish=on_finish)
            return
        if not wav_exists:
            _log.info("chanter: no wav for %s — skipping (mode=%s)", mantra_id, self.mode)
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
                _log.info("chant %s: %d samples @ %d Hz", path.name, len(pcm), sr)
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
        if self.mms is not None:
            self.mms.stop()

    def prefetch(self, mantra_id: str, mantra_text: str) -> None:
        """Warm the synth cache so playback can start as soon as it's requested.
        No-op for the wav-bank path; only relevant for cloud/local synth backends."""
        if self.mms is not None and hasattr(self.mms, "prefetch"):
            wav_exists = self._wav_exists(mantra_id)
            use_synth = (
                self.mode in ("mms", "sarvam")
                or (self.mode == "fallback" and not wav_exists)
            )
            if use_synth:
                self.mms.prefetch(mantra_id, mantra_text)
