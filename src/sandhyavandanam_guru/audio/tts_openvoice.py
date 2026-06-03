"""OpenVoice v2 speaker: render English (Indian) via MeloTTS, then re-paint with the user's timbre.

Architecture:
    text -> MeloTTS English-India base voice -> intermediate wav
    intermediate wav + user's reference embedding -> tone-color converter -> cloned wav

Only the timbre is cloned, so the reference clip language does not matter — a Sanskrit
recitation captures the same vocal-tract fingerprint as an English clip would.
"""
from __future__ import annotations

import logging
import os
import tempfile
import threading
import urllib.request
from pathlib import Path
from typing import TYPE_CHECKING

from .. import config as _cfg
from .player import Player

# OpenVoice's converter loads wavmark via huggingface_hub, which uses tqdm with
# multiprocessing locks. Spawning a resource tracker from a daemon thread (which
# is exactly where TUI-driven say() runs) crashes with "bad value(s) in
# fds_to_keep". These env knobs tell tqdm/HF to use no locks and no progress
# bars, which sidesteps the entire problem. Must be set before any HF call.
os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
os.environ.setdefault("TQDM_DISABLE", "1")
os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")

if TYPE_CHECKING:
    import numpy as np

_log = logging.getLogger("sgr.tts.openvoice")
_cfg.USER_DATA_DIR.mkdir(parents=True, exist_ok=True)
_log_handler = logging.FileHandler(_cfg.USER_DATA_DIR / "tts.log")
_log_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
_log.addHandler(_log_handler)
_log.setLevel(logging.INFO)


OV_BASE = "https://huggingface.co/myshell-ai/OpenVoiceV2/resolve/main"
OV_FILES = [
    "converter/checkpoint.pth",
    "converter/config.json",
    "base_speakers/ses/en-india.pth",
]


def _openvoice_cache_dir() -> Path:
    d = Path.home() / ".cache" / "sandhyavandanam_guru" / "openvoice_v2"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _ensure_checkpoints() -> Path:
    cache = _openvoice_cache_dir()
    for rel in OV_FILES:
        dst = cache / rel
        if not dst.exists():
            dst.parent.mkdir(parents=True, exist_ok=True)
            _log.info("downloading %s", rel)
            urllib.request.urlretrieve(f"{OV_BASE}/{rel}", dst)
    return cache


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


class OpenVoiceSpeaker:
    """Guru voice cloned from a short reference clip via OpenVoice v2 + MeloTTS-EN-India."""

    def __init__(self, ref_wav: Path, language: str = "EN_INDIA", device: str | None = None):
        self.ref_wav = str(ref_wav)
        self.language = language
        self.device = device or _best_device()
        self._tts = None
        self._converter = None
        self._source_se = None
        self._target_se = None
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

    def _ensure_loaded(self) -> None:
        if self._tts is not None:
            return
        with self._load_lock:
            if self._tts is not None:
                return

            import torch  # type: ignore[import-not-found]

            from melo.api import TTS as MeloTTS  # type: ignore[import-not-found]
            from openvoice.api import ToneColorConverter  # type: ignore[import-not-found]

            cache = _ensure_checkpoints()
            _log.info("loading OpenVoice converter on %s", self.device)
            converter = ToneColorConverter(str(cache / "converter/config.json"), device=self.device)
            converter.load_ckpt(str(cache / "converter/checkpoint.pth"))

            _log.info("loading MeloTTS English on %s", self.device)
            tts = MeloTTS(language="EN", device=self.device)
            # MeloTTS exposes spk2id as an HParams object, not a plain dict.
            # Iterating it raw goes through __getitem__ with int indices and
            # throws TypeError. Materialise to a real dict first.
            spk2id_raw = tts.hps.data.spk2id
            try:
                spk2id = dict(spk2id_raw)
            except (TypeError, ValueError):
                # Last-resort: read the underlying __dict__ that HParams wraps.
                spk2id = {k: v for k, v in getattr(spk2id_raw, "__dict__", {}).items()
                          if not k.startswith("_")}
            # MeloTTS is inconsistent: EN_INDIA uses an underscore while EN-US /
            # EN-BR / EN-AU / EN-Default all use dashes. Match by trying both.
            cand = self.language.upper()
            candidates = {cand, cand.replace("_", "-"), cand.replace("-", "_")}
            speaker_id = None
            for k, v in spk2id.items():
                if str(k).upper() in candidates:
                    speaker_id = v
                    break
            wanted = "/".join(sorted(candidates))
            if speaker_id is None:
                # Pull a safe key as fallback; never use list(HParams).
                fallback_key = next(iter(spk2id)) if spk2id else None
                speaker_id = spk2id[fallback_key] if fallback_key is not None else 0
                _log.warning(
                    "speaker %s not in %s; using %s",
                    wanted,
                    sorted(str(k) for k in spk2id),
                    fallback_key,
                )

            base_key = self.language.lower().replace("_", "-")  # "en-india"
            source_se = torch.load(
                cache / f"base_speakers/ses/{base_key}.pth",
                map_location=self.device,
            )

            # Extract the user's timbre fingerprint directly from the reference
            # clip via the converter's extract_se. This skips openvoice.se_extractor,
            # which tries to VAD-split + ASR-align the audio and pulls in
            # whisper-timestamped + silero + faster-whisper — every one of those
            # has dep conflicts in our env. Our eval clips are already 8–12 s of
            # clean speech, so we don't need any of that splitting.
            target_se = converter.extract_se([self.ref_wav])

            self._converter = converter
            self._tts = tts
            self._speaker_id = speaker_id
            self._source_se = source_se
            self._target_se = target_se
            _log.info("OpenVoice ready (speaker_id=%s)", speaker_id)

    def synthesize(self, text: str) -> tuple["np.ndarray", int]:
        import numpy as np
        import soundfile as sf

        self._ensure_loaded()
        with tempfile.TemporaryDirectory() as td:
            base_path = Path(td) / "base.wav"
            out_path = Path(td) / "out.wav"
            self._tts.tts_to_file(text, self._speaker_id, str(base_path), speed=1.0)  # type: ignore[union-attr]
            self._converter.convert(  # type: ignore[union-attr]
                audio_src_path=str(base_path),
                src_se=self._source_se,
                tgt_se=self._target_se,
                output_path=str(out_path),
            )
            data, sr = sf.read(str(out_path))
        pcm = np.asarray(data, dtype=np.float32)
        if pcm.ndim > 1:
            pcm = pcm.mean(axis=1)
        pcm = np.clip(pcm, -1.0, 1.0)
        return (pcm * 32767.0).astype(np.int16), int(sr)

    def is_speaking(self) -> bool:
        return self._speaking.is_set()

    def say(self, text: str) -> None:
        text = (text or "").strip()
        if not text:
            return
        self.stop()

        def _run() -> None:
            self._loading.set()
            try:
                pcm, sr = self.synthesize(text)
                _log.info("ov synth ok: %d samples @ %d Hz", len(pcm), sr)
                self._loading.clear()
                self._speaking.set()
                self.player.play(pcm, sr, block=True)
            except Exception:
                _log.exception("openvoice say() failed for text=%r", text[:80])
            finally:
                self._loading.clear()
                self._speaking.clear()

        threading.Thread(target=_run, daemon=True).start()

    def stop(self) -> None:
        self.player.stop()
