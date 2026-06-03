"""Player tests — stub sounddevice in sys.modules so we never touch real audio hardware."""
from __future__ import annotations

import sys
import threading
import types
from typing import Any

import numpy as np
import pytest


class _FakeSD:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple, dict]] = []
        self.last_play: tuple[Any, int] | None = None

    def stop(self) -> None:
        self.calls.append(("stop", (), {}))

    def play(self, pcm, sample_rate) -> None:
        self.calls.append(("play", (pcm, sample_rate), {}))
        self.last_play = (pcm, sample_rate)

    def wait(self) -> None:
        self.calls.append(("wait", (), {}))


@pytest.fixture()
def fake_sd(monkeypatch):
    fake = _FakeSD()
    mod = types.ModuleType("sounddevice")
    mod.stop = fake.stop  # type: ignore[attr-defined]
    mod.play = fake.play  # type: ignore[attr-defined]
    mod.wait = fake.wait  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "sounddevice", mod)
    return fake


def test_play_stops_then_plays(fake_sd) -> None:
    from sandhyavandanam_guru.audio.player import Player

    p = Player()
    pcm = np.zeros(10, dtype=np.int16)
    p.play(pcm, 22050)
    ops = [c[0] for c in fake_sd.calls]
    assert ops == ["stop", "play"]
    assert fake_sd.last_play == (pcm, 22050)


def test_play_blocking_calls_wait(fake_sd) -> None:
    from sandhyavandanam_guru.audio.player import Player

    p = Player()
    p.play(np.zeros(4, dtype=np.int16), 16000, block=True)
    assert [c[0] for c in fake_sd.calls] == ["stop", "play", "wait"]


def test_stop_calls_sd_stop(fake_sd) -> None:
    from sandhyavandanam_guru.audio.player import Player

    Player().stop()
    assert [c[0] for c in fake_sd.calls] == ["stop"]


def test_wait_calls_sd_wait(fake_sd) -> None:
    from sandhyavandanam_guru.audio.player import Player

    Player().wait()
    assert [c[0] for c in fake_sd.calls] == ["wait"]


def test_play_serialises_via_lock(fake_sd) -> None:
    """Two concurrent play()s must not interleave the stop/play pair."""
    from sandhyavandanam_guru.audio.player import Player

    p = Player()
    barrier = threading.Barrier(2)

    def worker(tag: int) -> None:
        barrier.wait()
        p.play(np.full(2, tag, dtype=np.int16), 16000)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    ops = [c[0] for c in fake_sd.calls]
    # Two play sequences, each "stop" immediately followed by "play".
    assert ops == ["stop", "play", "stop", "play"]
