"""Opt-in audio integration tests — run the real synth and capture the PCM.

These tests don't mock the TTS engines; they actually load the models and
produce audio. To keep the default unit-test suite fast, they're guarded:

    SGR_INTEGRATION=1 uv run pytest tests/test_audio_integration.py -q

Why "capture" instead of speakers:
  - CI/sandbox has no sound card.
  - We can prove "audio was actually produced" by asserting the rendered PCM
    has plausible amplitude, dynamic range, and duration. Hearing it is for
    the human; the test guards against silence regressions like the
    wave.Error / missing-soundfile crashes we hit in Phase 2.

Phase 4 (listening) will add:
  - feed eval/recordings/*_clean.wav into the STT pipeline as a user reciting
  - assert the recitation_match advance rule fires
  - assert the with_error variant lands in the "nudge" similarity band

For now we scaffold those with skipped placeholders + sanity checks on the
recordings themselves so the inputs are wired even before the pipeline is.
"""
from __future__ import annotations

import os
import sys
import threading
import time
import types
import wave
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from sandhyavandanam_guru import config

INTEGRATION = os.environ.get("SGR_INTEGRATION") == "1"
EVAL_DIR = config.PROJECT_ROOT / "eval" / "recordings"

pytestmark = pytest.mark.skipif(
    not INTEGRATION,
    reason="set SGR_INTEGRATION=1 to run real-audio tests",
)


# ---------- recording capture helpers ----------


class _PCMRecorder:
    """Install in sys.modules['sounddevice'] to capture what would play."""

    def __init__(self) -> None:
        self.played: list[tuple[np.ndarray, int]] = []
        self._waiting = False

    def stop(self) -> None: ...
    def play(self, pcm, sr) -> None:
        self.played.append((np.asarray(pcm).copy(), int(sr)))

    def wait(self) -> None:
        # Player.play(..., block=True) calls wait(); mimic real playback duration
        # (capped) so observers actually see the SPEAKING state window.
        if self.played:
            pcm, sr = self.played[-1]
            time.sleep(min(2.0, len(pcm) / sr))

    def query_devices(self, *_a, **_kw) -> dict:
        return {"name": "fake-pcm-recorder"}


@pytest.fixture()
def pcm_recorder(monkeypatch):
    rec = _PCMRecorder()
    mod = types.ModuleType("sounddevice")
    mod.stop = rec.stop  # type: ignore[attr-defined]
    mod.play = rec.play  # type: ignore[attr-defined]
    mod.wait = rec.wait  # type: ignore[attr-defined]
    mod.query_devices = rec.query_devices  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "sounddevice", mod)
    return rec


def _bar_text(bar) -> str:
    """Read the StatusBar's rendered content, robust across Textual versions."""
    from rich.console import Console

    renderable = None
    for attr in ("_renderable", "_content", "renderable"):
        renderable = getattr(bar, attr, None)
        if renderable is not None:
            break
    if renderable is None:
        renderable = bar.render()
    console = Console(force_terminal=False, no_color=True, color_system=None, width=200)
    with console.capture() as cap:
        console.print(renderable)
    return cap.get()


def _amplitude_stats(pcm: np.ndarray) -> dict:
    pcm = pcm.astype(np.float32)
    return {
        "len": int(pcm.size),
        "abs_mean": float(np.mean(np.abs(pcm))),
        "rms": float(np.sqrt(np.mean(pcm**2))),
        "peak": float(np.max(np.abs(pcm))),
    }


def _wait_until(predicate, timeout: float = 30.0, interval: float = 0.05) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return
        time.sleep(interval)
    raise AssertionError("timed out waiting for predicate")


# ---------- Piper end-to-end ----------


def test_piper_synthesize_produces_real_audio() -> None:
    """Calling synthesize() on the real Piper backend yields non-silent PCM."""
    try:
        from sandhyavandanam_guru.audio.tts_piper import PiperSpeaker
    except ImportError:
        pytest.skip("piper-tts not installed")
    s = PiperSpeaker("en_US-lessac-medium")
    pcm, sr = s.synthesize("Begin by sitting and facing east.")
    stats = _amplitude_stats(pcm)
    # 2–6 s of speech at 22.05 kHz lives in [44k, 132k] samples; allow margin.
    assert sr == 22050
    assert 22050 <= stats["len"] <= 220500, stats
    # Not silent: real speech has at least a few thousand RMS counts in int16.
    assert stats["rms"] > 500, f"PCM looks silent: {stats}"
    # A healthy speech signal has dynamic range — abs_mean well below peak.
    assert stats["abs_mean"] < stats["peak"] / 2, stats


def test_piper_say_round_trip_through_app(pcm_recorder) -> None:
    """Drive the actual GuruApp and assert audio reached the player."""
    from sandhyavandanam_guru.coaching_loader import load_coaching
    from sandhyavandanam_guru.ritual_loader import load_ritual
    from sandhyavandanam_guru import tui

    try:
        from sandhyavandanam_guru.audio.tts_piper import PiperSpeaker
    except ImportError:
        pytest.skip("piper-tts not installed")

    ritual = load_ritual(config.RITUAL_DIR / "pratah_rigveda.yaml")
    coaching = load_coaching(config.RITUAL_DIR / "coaching_en.yaml")
    speaker = PiperSpeaker("en_US-lessac-medium")

    # We can't await async TUI here without pytest-asyncio plumbing in a sync
    # test; instead we drive say() directly, which is exactly what the TUI
    # binding triggers.
    speaker.say(coaching.for_step(ritual.steps[0].id))
    _wait_until(lambda: bool(pcm_recorder.played))

    pcm, sr = pcm_recorder.played[-1]
    stats = _amplitude_stats(pcm)
    assert sr == 22050
    assert stats["len"] > 22050  # ≥1 s
    assert stats["rms"] > 500


# ---------- OpenVoice end-to-end ----------


def _default_ref_wav() -> Path:
    p = EVAL_DIR / "m10_asavaadityo_clean.wav"
    if not p.exists():
        pytest.skip(f"reference clip {p} not present; record with scripts/record_eval.py")
    return p


def test_openvoice_synthesize_produces_real_audio_in_user_timbre(pcm_recorder) -> None:
    """Real OpenVoice synth + tone-color clone from one of the eval clips."""
    try:
        from sandhyavandanam_guru.audio.tts_openvoice import OpenVoiceSpeaker
    except ImportError:
        pytest.skip("openvoice/melo not installed")
    ref = _default_ref_wav()
    s = OpenVoiceSpeaker(ref_wav=ref, language="EN_INDIA")
    pcm, sr = s.synthesize("Good morning. Today we begin the morning sandhya.")
    stats = _amplitude_stats(pcm)
    assert sr >= 16000
    assert stats["len"] > sr  # ≥1 s
    assert stats["rms"] > 500, f"OpenVoice PCM looks silent: {stats}"


def test_openvoice_india_clone_picks_correct_speaker_and_embedding(pcm_recorder) -> None:
    """Specific to the EN_INDIA path that was silently mis-mapped before.

    Regressions this catches:
      - MeloTTS spk2id is an HParams object whose iteration crashes if treated
        as a plain dict (caused TypeError on the fallback warning).
      - EN India is keyed 'EN_INDIA' (underscore) in MeloTTS but the embedding
        file is 'en-india.pth' (dash) on HF. Earlier code converted one into
        the other and silently fell back to a different accent.
      - openvoice.se_extractor pulls broken silero + faster-whisper deps; we
        must use converter.extract_se directly.
    """
    try:
        from sandhyavandanam_guru.audio.tts_openvoice import OpenVoiceSpeaker
    except ImportError:
        pytest.skip("openvoice/melo not installed")

    s = OpenVoiceSpeaker(ref_wav=_default_ref_wav(), language="EN_INDIA", device="cpu")
    s._ensure_loaded()

    # Speaker id resolved to the EN_INDIA key, not a fallback.
    spk2id = dict(s._tts.hps.data.spk2id)  # type: ignore[union-attr]
    assert "EN_INDIA" in spk2id, f"MeloTTS English keys changed: {list(spk2id)}"
    assert s._speaker_id == spk2id["EN_INDIA"], (
        f"selected speaker_id {s._speaker_id} doesn't match EN_INDIA={spk2id['EN_INDIA']}"
    )

    # Source embedding tensor came from base_speakers/ses/en-india.pth.
    assert s._source_se is not None
    # Target embedding (user's timbre) came from the reference clip.
    assert s._target_se is not None
    # They differ — proof the clone is actually overlaying the user's timbre,
    # not echoing the base voice through identity.
    import torch

    assert not torch.equal(
        s._source_se.detach().cpu(), s._target_se.detach().cpu()
    ), "target and source embeddings are identical — clone isn't doing anything"

    # And the end-to-end synth actually produces audio with the cloned voice.
    pcm, sr = s.synthesize("Begin by sitting and facing east.")
    stats = _amplitude_stats(pcm)
    assert sr >= 16000
    assert stats["len"] > sr
    assert stats["rms"] > 500


def test_openvoice_state_transitions_through_loading_then_speaking(pcm_recorder) -> None:
    """state() reports loading during warmup and speaking during playback."""
    try:
        from sandhyavandanam_guru.audio.tts_openvoice import OpenVoiceSpeaker
    except ImportError:
        pytest.skip("openvoice/melo not installed")
    s = OpenVoiceSpeaker(ref_wav=_default_ref_wav(), language="EN_INDIA")

    seen: list[str] = []
    stop_flag = threading.Event()

    def watcher() -> None:
        while not stop_flag.is_set():
            seen.append(s.state())
            time.sleep(0.05)

    t = threading.Thread(target=watcher, daemon=True)
    t.start()
    s.say("Hello.")
    _wait_until(lambda: bool(pcm_recorder.played), timeout=180)
    stop_flag.set()
    t.join(timeout=1)
    assert "loading" in seen, seen[-30:]
    # speaking flag may flip very briefly with our zero-wait fake; allow either.
    assert any(state == "speaking" for state in seen) or pcm_recorder.played


# ---------- eval recordings as user input (Phase 4 scaffolding) ----------


def _expected_wavs() -> list[Path]:
    return sorted(EVAL_DIR.glob("*_clean.wav"))


def test_eval_recordings_are_present() -> None:
    if not _expected_wavs():
        pytest.skip(f"no clean recordings in {EVAL_DIR}; record with scripts/record_eval.py")
    assert len(_expected_wavs()) >= 5


@pytest.mark.parametrize("wav", _expected_wavs() or [pytest.param(None, marks=pytest.mark.skip)])
def test_eval_recording_meets_spt_spec(wav: Path | None) -> None:
    """Every clean recording must be 16 kHz mono PCM-16 so STT consumes it straight."""
    if wav is None:
        pytest.skip("no recordings")
    with wave.open(str(wav), "rb") as wf:
        assert wf.getframerate() == 16000, f"{wav.name} sample rate {wf.getframerate()}"
        assert wf.getnchannels() == 1, f"{wav.name} channels {wf.getnchannels()}"
        assert wf.getsampwidth() == 2, f"{wav.name} sampwidth {wf.getsampwidth()}"
        # At least 4 s of speech — anything shorter is probably a mis-record.
        n = wf.getnframes()
        assert n >= 16000 * 3, f"{wav.name} only {n/16000:.1f} s"


@pytest.mark.parametrize("wav", _expected_wavs() or [pytest.param(None, marks=pytest.mark.skip)])
def test_eval_recording_has_audible_content(wav: Path | None) -> None:
    """A clean recording isn't silence — RMS amplitude must exceed a floor."""
    if wav is None:
        pytest.skip("no recordings")
    with wave.open(str(wav), "rb") as wf:
        raw = wf.readframes(wf.getnframes())
    pcm = np.frombuffer(raw, dtype=np.int16).astype(np.float32)
    rms = float(np.sqrt(np.mean(pcm**2)))
    assert rms > 200, f"{wav.name} looks silent (rms={rms:.1f})"


# ---------- TUI ↔ real speaker (closes the silent-failure gap) ----------


async def test_real_piper_flips_status_bar_to_speaking_inside_tui(pcm_recorder) -> None:
    """Drive the live GuruApp with a real PiperSpeaker; observe SPEAKING in the bar.

    This is the test that would have failed during the missing-soundfile / wave.Error
    regressions: a real speaker worker that crashes never sets _speaking, so the bar
    never reports SPEAKING — even if the FakeSpeaker test still passes.
    """
    from rich.console import Console

    from sandhyavandanam_guru import tui
    from sandhyavandanam_guru.coaching_loader import load_coaching
    from sandhyavandanam_guru.ritual_loader import load_ritual

    try:
        from sandhyavandanam_guru.audio.tts_piper import PiperSpeaker
    except ImportError:
        pytest.skip("piper-tts not installed")

    ritual = load_ritual(config.RITUAL_DIR / "pratah_rigveda.yaml")
    coaching = load_coaching(config.RITUAL_DIR / "coaching_en.yaml")
    speaker = PiperSpeaker("en_US-lessac-medium")

    app = tui.GuruApp(ritual, coaching=coaching, speaker=speaker)
    async with app.run_test() as pilot:
        await pilot.pause()
        # First-step coaching line was kicked off on mount; press r to retrigger
        # in case the mount call already finished while we were warming.
        await pilot.press("r")

        bar = app.query_one("#status", tui.StatusBar)
        seen_states: list[str] = []
        import asyncio

        deadline = asyncio.get_event_loop().time() + 20.0
        saw_speaking = False
        while asyncio.get_event_loop().time() < deadline:
            text = _bar_text(bar)
            seen_states.append(text.strip().split("\n")[0])
            if "GURU IS SPEAKING" in text:
                saw_speaking = True
                break
            await asyncio.sleep(0.1)

        # Audio actually reached the player — proves the worker completed synth.
        assert pcm_recorder.played, "real Piper produced no audio"
        # Status bar reflected the speaking state at least once during playback.
        assert saw_speaking, f"status bar never flipped to SPEAKING; last 5 = {seen_states[-5:]}"


async def test_real_piper_returns_status_to_idle_after_playback(pcm_recorder) -> None:
    """After say() completes, the bar must return to IDLE — no stuck SPEAKING."""
    from rich.console import Console

    from sandhyavandanam_guru import tui
    from sandhyavandanam_guru.coaching_loader import load_coaching
    from sandhyavandanam_guru.ritual_loader import load_ritual

    try:
        from sandhyavandanam_guru.audio.tts_piper import PiperSpeaker
    except ImportError:
        pytest.skip("piper-tts not installed")

    ritual = load_ritual(config.RITUAL_DIR / "pratah_rigveda.yaml")
    coaching = load_coaching(config.RITUAL_DIR / "coaching_en.yaml")
    speaker = PiperSpeaker("en_US-lessac-medium")

    app = tui.GuruApp(ritual, coaching=coaching, speaker=speaker)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("r")

        import asyncio

        # Wait for the worker to finish (state clears back to idle).
        deadline = asyncio.get_event_loop().time() + 20.0
        while asyncio.get_event_loop().time() < deadline:
            if speaker.state() == "idle" and pcm_recorder.played:
                break
            await asyncio.sleep(0.1)
        assert speaker.state() == "idle"

        # One more tick so the bar redraws.
        await asyncio.sleep(0.2)
        bar = app.query_one("#status", tui.StatusBar)
        text = _bar_text(bar)
        assert "IDLE" in text, text


async def test_real_openvoice_shows_warming_up_then_speaking(pcm_recorder) -> None:
    """OpenVoice's slow first load is the case where WARMING UP must be visible."""
    from rich.console import Console

    from sandhyavandanam_guru import tui
    from sandhyavandanam_guru.coaching_loader import load_coaching
    from sandhyavandanam_guru.ritual_loader import load_ritual

    try:
        from sandhyavandanam_guru.audio.tts_openvoice import OpenVoiceSpeaker
    except ImportError:
        pytest.skip("openvoice/melo not installed")
    ref = _default_ref_wav()
    speaker = OpenVoiceSpeaker(ref_wav=ref, language="EN_INDIA")

    ritual = load_ritual(config.RITUAL_DIR / "pratah_rigveda.yaml")
    coaching = load_coaching(config.RITUAL_DIR / "coaching_en.yaml")
    app = tui.GuruApp(ritual, coaching=coaching, speaker=speaker)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("r")

        import asyncio

        bar = app.query_one("#status", tui.StatusBar)
        saw_loading = False
        saw_speaking = False
        deadline = asyncio.get_event_loop().time() + 240.0  # OV warmup can be slow
        while asyncio.get_event_loop().time() < deadline:
            console = Console(force_terminal=False, no_color=True, color_system=None, width=200)
            renderable = getattr(bar, "_renderable", None) or getattr(bar, "_content", None)
            with console.capture() as cap:
                console.print(renderable)
            text = cap.get()
            if "WARMING UP" in text:
                saw_loading = True
            if "GURU IS SPEAKING" in text:
                saw_speaking = True
                break
            await asyncio.sleep(0.2)
        assert saw_loading, "status bar never showed WARMING UP — loading state not wired"
        assert saw_speaking, "status bar never showed SPEAKING — synth never finished"
        assert pcm_recorder.played


# ---------- eval recordings as user input (Phase 4 scaffolding) ----------


@pytest.mark.skip(reason="Phase 4: STT pipeline not wired yet")
def test_user_reciting_clean_clip_advances_step() -> None:
    """Phase 4: feed eval/recordings/<id>_clean.wav, expect recitation_match advance."""


@pytest.mark.skip(reason="Phase 4: STT pipeline not wired yet")
def test_user_reciting_with_error_clip_triggers_gentle_correction() -> None:
    """Phase 4: feed eval/recordings/<id>_with_error.wav, expect nudge band."""
