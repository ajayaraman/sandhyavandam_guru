"""Sarvam Bulbul TTS speaker — English coaching voice (cloud).

Same backend as the SarvamChanter mantra path, but speaks English-Indian for the
guru's coaching lines. Useful for trying a consistent voice across coaching and
chanting (same speaker on en-IN and hi-IN).
"""
from __future__ import annotations

import logging
import threading

from .. import config as _cfg
from .player import Player
from .sarvam_chanter import _load_dotenv_if_present  # reuse the .env loader
import base64
import io
import os
import wave

_log = logging.getLogger("sgr.tts.sarvam")
_cfg.USER_DATA_DIR.mkdir(parents=True, exist_ok=True)
_h = logging.FileHandler(_cfg.USER_DATA_DIR / "tts.log")
_h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
_log.addHandler(_h)
_log.setLevel(logging.INFO)


class SarvamSpeaker:
    def __init__(
        self,
        api_key: str | None = None,
        model: str = "bulbul:v3",
        speaker: str = "sumit",
        target_language: str = "en-IN",
    ):
        _load_dotenv_if_present()
        self.api_key = api_key or os.environ.get("SARVAM_API_KEY")
        if not self.api_key:
            raise RuntimeError(
                "SARVAM_API_KEY not set — add it to .env or export it in your shell."
            )
        self.model = model
        self.speaker = speaker
        self.target_language = target_language
        self._client = None
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

    def _ensure_client(self) -> None:
        if self._client is not None:
            return
        with self._load_lock:
            if self._client is not None:
                return
            from sarvamai import SarvamAI  # type: ignore[import-not-found]

            self._client = SarvamAI(api_subscription_key=self.api_key)
            _log.info(
                "sarvam speaker ready: model=%s speaker=%s lang=%s",
                self.model, self.speaker, self.target_language,
            )

    def _decode(self, response):
        import numpy as np

        audios = getattr(response, "audios", None) or response.get("audios", [])
        if not audios:
            raise RuntimeError(f"sarvam: no audio in response: {response}")
        chunks: list = []
        sr = 0
        for b64 in audios:
            raw = base64.b64decode(b64)
            with wave.open(io.BytesIO(raw), "rb") as wf:
                sr = wf.getframerate()
                nchan = wf.getnchannels()
                data = wf.readframes(wf.getnframes())
            pcm = np.frombuffer(data, dtype=np.int16)
            if nchan > 1:
                pcm = pcm.reshape(-1, nchan).mean(axis=1).astype(np.int16)
            chunks.append(pcm)
        return np.concatenate(chunks), sr

    def synthesize(self, text: str):
        self._ensure_client()
        resp = self._client.text_to_speech.convert(  # type: ignore[union-attr]
            model=self.model,
            text=text,
            target_language_code=self.target_language,
            speaker=self.speaker,
        )
        return self._decode(resp)

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
                        return
                _log.info("sarvam synth ok: %d samples @ %d Hz", len(pcm), sr)
                self._loading.clear()
                self._speaking.set()
                self.player.play(pcm, sr, block=True)
            except Exception:
                _log.exception("sarvam say() failed for text=%r", text[:80])
            finally:
                self._loading.clear()
                self._speaking.clear()

        threading.Thread(target=_run, daemon=True).start()

    def stop(self) -> None:
        self.player.stop()
