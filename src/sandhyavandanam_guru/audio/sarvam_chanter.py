"""Sarvam AI Bulbul TTS chanter (cloud).

Calls Sarvam's text-to-speech API to render a mantra. Useful as a comparator
against MMS-Sanskrit and the user's own recordings: Bulbul is trained on
Indian-language data so Devanagari-rendered mantras come out in a natural
Indian voice.

Requires SARVAM_API_KEY in the environment (auto-loaded from .env if present).
"""
from __future__ import annotations

import base64
import io
import logging
import os
import threading
import wave
from pathlib import Path
from typing import TYPE_CHECKING

from .. import config as _cfg
from .player import Player

if TYPE_CHECKING:
    import numpy as np

_log = logging.getLogger("sgr.sarvam")
_cfg.USER_DATA_DIR.mkdir(parents=True, exist_ok=True)
_h = logging.FileHandler(_cfg.USER_DATA_DIR / "tts.log")
_h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
_log.addHandler(_h)
_log.setLevel(logging.INFO)


def _load_dotenv_if_present() -> None:
    """Load PROJECT_ROOT/.env into os.environ if python-dotenv is installed.
    Silent no-op if the package or file is missing."""
    try:
        from dotenv import load_dotenv  # type: ignore[import-not-found]
    except ImportError:
        return
    env_path = _cfg.PROJECT_ROOT / ".env"
    if env_path.exists():
        load_dotenv(env_path)


class SarvamChanter:
    """Synthesizes mantras via Sarvam Bulbul TTS."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "bulbul:v3",
        speaker: str = "shubh",
        target_language: str = "hi-IN",
        transliterate: bool = True,
        source_scheme: str = "itrans",
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
        self.transliterate = transliterate
        self.source_scheme = source_scheme
        # Prefetch cache keyed by mantra_id → (pcm, sr) | "in_flight" sentinel.
        # Lets the TUI synthesize the chant in parallel with the coaching line.
        self._cache: dict = {}
        self._cache_lock = threading.Lock()
        self._client = None
        self._load_lock = threading.Lock()
        self.player = Player()
        self._chanting = threading.Event()
        self._gen = 0
        self._gen_lock = threading.Lock()

    def state(self) -> str:
        return "chanting" if self._chanting.is_set() else "idle"

    def is_chanting(self) -> bool:
        return self._chanting.is_set()

    def _ensure_client(self) -> None:
        if self._client is not None:
            return
        with self._load_lock:
            if self._client is not None:
                return
            from sarvamai import SarvamAI  # type: ignore[import-not-found]

            self._client = SarvamAI(api_subscription_key=self.api_key)
            _log.info("sarvam client ready: model=%s speaker=%s lang=%s",
                      self.model, self.speaker, self.target_language)

    def _decode_audio(self, response) -> tuple["np.ndarray", int]:
        """Sarvam returns base64-encoded wav(s) in response.audios. Concat them."""
        import numpy as np

        audios = getattr(response, "audios", None) or response.get("audios", [])
        if not audios:
            raise RuntimeError(f"sarvam: no audio in response: {response}")
        pcm_chunks: list[np.ndarray] = []
        sr = 0
        for b64 in audios:
            raw = base64.b64decode(b64)
            with wave.open(io.BytesIO(raw), "rb") as wf:
                sr = wf.getframerate()
                nchan = wf.getnchannels()
                nframes = wf.getnframes()
                data = wf.readframes(nframes)
            pcm = np.frombuffer(data, dtype=np.int16)
            if nchan > 1:
                pcm = pcm.reshape(-1, nchan).mean(axis=1).astype(np.int16)
            pcm_chunks.append(pcm)
        return np.concatenate(pcm_chunks), sr

    def _to_devanagari(self, text: str) -> str:
        """Best-effort transliterate roman Sanskrit → Devanagari.

        Sarvam reads Devanagari with hi-IN voice far more correctly than
        Latin-letter Sanskrit, which it tries to pronounce as English.
        Falls back to the original text if the lib is missing or fails.
        """
        try:
            from indic_transliteration import sanscript  # type: ignore[import-not-found]
            from indic_transliteration.sanscript import transliterate as _tr  # type: ignore[import-not-found]
        except ImportError:
            _log.warning("indic_transliteration not installed; sending roman text as-is")
            return text
        scheme_map = {
            "itrans": sanscript.ITRANS,
            "hk": sanscript.HK,
            "iast": sanscript.IAST,
            "slp1": sanscript.SLP1,
        }
        src = scheme_map.get(self.source_scheme.lower(), sanscript.ITRANS)
        try:
            return _tr(text, src, sanscript.DEVANAGARI)
        except Exception:
            _log.exception("transliteration failed; sending roman as-is")
            return text

    def synthesize(self, text: str) -> tuple["np.ndarray", int]:
        self._ensure_client()
        if self.transliterate:
            deva = self._to_devanagari(text)
            _log.info("sarvam tts: %d chars roman → %d chars devanagari", len(text), len(deva))
            text = deva
        else:
            _log.info("sarvam tts: %d chars (no transliteration)", len(text))
        resp = self._client.text_to_speech.convert(  # type: ignore[union-attr]
            model=self.model,
            text=text,
            target_language_code=self.target_language,
            speaker=self.speaker,
        )
        return self._decode_audio(resp)

    def prefetch(self, mantra_id: str, text: str) -> None:
        """Synthesize and cache audio for this mantra in the background.
        Idempotent — repeated calls with the same id are no-ops."""
        text = (text or "").strip()
        if not text:
            return
        with self._cache_lock:
            if mantra_id in self._cache:
                return
            self._cache[mantra_id] = "in_flight"

        def _fetch() -> None:
            try:
                _log.info("sarvam prefetch start: %s", mantra_id)
                pcm, sr = self.synthesize(text)
                with self._cache_lock:
                    self._cache[mantra_id] = (pcm, sr)
                _log.info("sarvam prefetch ready: %s (%d samples)", mantra_id, len(pcm))
            except Exception:
                _log.exception("sarvam prefetch failed for %s", mantra_id)
                with self._cache_lock:
                    self._cache.pop(mantra_id, None)

        threading.Thread(target=_fetch, daemon=True).start()

    def chant(self, mantra_id: str, text: str, on_finish=None) -> None:
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
                # Wait briefly for any in-flight prefetch to land.
                pcm_sr = None
                for _ in range(60):  # up to ~6 s
                    with self._cache_lock:
                        entry = self._cache.get(mantra_id)
                    if entry == "in_flight":
                        threading.Event().wait(0.1)
                        continue
                    if entry is not None:
                        pcm_sr = entry
                    break
                if pcm_sr is None:
                    pcm_sr = self.synthesize(text)
                pcm, sr = pcm_sr
                with self._gen_lock:
                    if my_gen != self._gen:
                        return
                self._chanting.set()
                _log.info("sarvam chant play: %s (%d samples @ %d Hz)", mantra_id, len(pcm), sr)
                self.player.play(pcm, sr, block=True)
            except Exception:
                _log.exception("sarvam chant failed for text=%r", text[:80])
            finally:
                self._chanting.clear()
                with self._cache_lock:
                    self._cache.pop(mantra_id, None)
                if on_finish:
                    try:
                        on_finish()
                    except Exception:
                        _log.exception("on_finish callback failed")

        threading.Thread(target=_run, daemon=True).start()

    def stop(self) -> None:
        self.player.stop()
