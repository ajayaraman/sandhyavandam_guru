"""PiperSpeaker tests with mocked voice + sounddevice — no audio hardware, no network."""
from __future__ import annotations

import sys
import threading
import time
import types
from typing import Any

import numpy as np
import pytest


class _FakeAudioChunk:
    def __init__(self, samples: np.ndarray) -> None:
        self.audio_int16_array = samples


class _FakeVoiceConfig:
    sample_rate = 22050


class _FakeVoice:
    def __init__(self) -> None:
        self.config = _FakeVoiceConfig()
        self.calls: list[str] = []

    def synthesize(self, text: str):
        self.calls.append(text)
        # 100 samples per word so duration scales with input — keeps the test
        # honest about chunk concatenation.
        for word in text.split():
            yield _FakeAudioChunk(np.full(100, ord(word[0]), dtype=np.int16))


class _FakeSD:
    def __init__(self) -> None:
        self.calls: list[tuple[str, Any]] = []

    def stop(self) -> None:
        self.calls.append(("stop", None))

    def play(self, pcm, sr) -> None:
        self.calls.append(("play", (pcm, sr)))

    def wait(self) -> None:
        self.calls.append(("wait", None))


@pytest.fixture()
def fake_env(monkeypatch):
    fake_sd = _FakeSD()
    sd_mod = types.ModuleType("sounddevice")
    sd_mod.stop = fake_sd.stop  # type: ignore[attr-defined]
    sd_mod.play = fake_sd.play  # type: ignore[attr-defined]
    sd_mod.wait = fake_sd.wait  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "sounddevice", sd_mod)

    fake_voice = _FakeVoice()
    piper_mod = types.ModuleType("piper")
    piper_mod.PiperVoice = types.SimpleNamespace(  # type: ignore[attr-defined]
        load=lambda *a, **kw: fake_voice
    )
    monkeypatch.setitem(sys.modules, "piper", piper_mod)

    # Pretend the voice file is already cached so no download is attempted.
    from sandhyavandanam_guru.audio import voices

    monkeypatch.setattr(
        voices,
        "ensure_piper_voice",
        lambda voice: (object(), object()),
    )
    return fake_sd, fake_voice


def test_synthesize_concatenates_chunks(fake_env) -> None:
    _, fake_voice = fake_env
    from sandhyavandanam_guru.audio.tts_piper import PiperSpeaker

    s = PiperSpeaker("en_US-lessac-medium")
    pcm, sr = s.synthesize("hello world")
    assert sr == 22050
    # Two words × 100 samples each.
    assert pcm.shape == (200,)
    assert pcm.dtype == np.int16
    assert fake_voice.calls == ["hello world"]


def test_synthesize_empty_text_returns_zero_samples(fake_env) -> None:
    from sandhyavandanam_guru.audio.tts_piper import PiperSpeaker

    s = PiperSpeaker("en_US-lessac-medium")
    pcm, sr = s.synthesize("")
    assert pcm.shape == (0,)
    assert pcm.dtype == np.int16
    assert sr == 22050


def test_is_speaking_starts_false(fake_env) -> None:
    from sandhyavandanam_guru.audio.tts_piper import PiperSpeaker

    s = PiperSpeaker("en_US-lessac-medium")
    assert s.is_speaking() is False


def test_say_with_blank_text_is_a_noop(fake_env) -> None:
    fake_sd, fake_voice = fake_env
    from sandhyavandanam_guru.audio.tts_piper import PiperSpeaker

    s = PiperSpeaker("en_US-lessac-medium")
    s.say("   ")
    # Worker thread didn't start because text was empty.
    assert fake_voice.calls == []
    # Nothing played, only the early stop() from previous-clip cancellation is OK to absent.
    assert all(c[0] != "play" for c in fake_sd.calls)


def test_say_launches_worker_and_plays(fake_env) -> None:
    fake_sd, fake_voice = fake_env
    from sandhyavandanam_guru.audio.tts_piper import PiperSpeaker

    s = PiperSpeaker("en_US-lessac-medium")
    s.say("good morning")
    # Wait for the worker to finish synth + play. Worker uses block=True which
    # calls our fake wait() — that returns immediately, so a short poll suffices.
    deadline = time.time() + 2.0
    while time.time() < deadline:
        if any(c[0] == "play" for c in fake_sd.calls):
            break
        time.sleep(0.01)
    assert any(c[0] == "play" for c in fake_sd.calls), fake_sd.calls
    assert "good morning" in fake_voice.calls


def test_stop_calls_player_stop(fake_env) -> None:
    fake_sd, _ = fake_env
    from sandhyavandanam_guru.audio.tts_piper import PiperSpeaker

    s = PiperSpeaker("en_US-lessac-medium")
    s.stop()
    assert any(c[0] == "stop" for c in fake_sd.calls)


def test_is_speaking_clears_after_say_completes(fake_env) -> None:
    from sandhyavandanam_guru.audio.tts_piper import PiperSpeaker

    s = PiperSpeaker("en_US-lessac-medium")
    s.say("hello")
    # Worker is fast in tests; give it a tick to start and clear.
    deadline = time.time() + 1.5
    while time.time() < deadline:
        if not s.is_speaking():
            break
        time.sleep(0.01)
    assert s.is_speaking() is False


def test_voice_loaded_once_under_concurrency(monkeypatch, fake_env) -> None:
    from sandhyavandanam_guru.audio import voices, tts_piper

    load_count = {"n": 0}
    voice_obj = _FakeVoice()
    monkeypatch.setattr(voices, "ensure_piper_voice", lambda v: (object(), object()))

    def fake_load(*a, **kw):
        load_count["n"] += 1
        # Simulate slow load to exercise the double-checked lock.
        time.sleep(0.05)
        return voice_obj

    piper_mod = types.ModuleType("piper")
    piper_mod.PiperVoice = types.SimpleNamespace(load=fake_load)  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "piper", piper_mod)

    s = tts_piper.PiperSpeaker("en_US-lessac-medium")
    threads = [threading.Thread(target=s._ensure_loaded) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert load_count["n"] == 1
