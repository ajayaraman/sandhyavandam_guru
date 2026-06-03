"""OpenVoiceSpeaker tests — mocked heavyweight imports + urlretrieve."""
from __future__ import annotations

import sys
import types
from pathlib import Path
from typing import Any

import numpy as np
import pytest


@pytest.fixture()
def fake_torch(monkeypatch):
    mod = types.ModuleType("torch")

    class _Backends:
        class _MPS:
            @staticmethod
            def is_available() -> bool:
                return False

        mps = _MPS()

    class _Cuda:
        @staticmethod
        def is_available() -> bool:
            return False

    mod.backends = _Backends  # type: ignore[attr-defined]
    mod.cuda = _Cuda  # type: ignore[attr-defined]
    mod.load = lambda *a, **kw: object()  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "torch", mod)
    return mod


def test_ov_files_table_is_complete() -> None:
    from sandhyavandanam_guru.audio import tts_openvoice as ov

    paths = set(ov.OV_FILES)
    assert "converter/checkpoint.pth" in paths
    assert "converter/config.json" in paths
    assert any(p.startswith("base_speakers/ses/") for p in paths)


def test_best_device_returns_known_value(fake_torch) -> None:
    from sandhyavandanam_guru.audio import tts_openvoice as ov

    assert ov._best_device() in {"cpu", "mps", "cuda"}


def test_best_device_falls_back_when_torch_missing(monkeypatch) -> None:
    monkeypatch.setitem(sys.modules, "torch", None)
    from sandhyavandanam_guru.audio import tts_openvoice as ov

    # Force re-resolution: import-error path returns "cpu".
    assert ov._best_device() == "cpu"


def test_cache_dir_creates(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    from sandhyavandanam_guru.audio import tts_openvoice as ov

    d = ov._openvoice_cache_dir()
    assert d.exists()
    assert d.name == "openvoice_v2"


def test_ensure_checkpoints_downloads_only_missing(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    from sandhyavandanam_guru.audio import tts_openvoice as ov

    cache = ov._openvoice_cache_dir()
    # Pre-create one file so it's skipped.
    (cache / "converter").mkdir(parents=True, exist_ok=True)
    (cache / "converter/config.json").write_text("{}")

    fetched: list[str] = []

    def fake_urlretrieve(url: str, dst):
        fetched.append(url)
        Path(dst).parent.mkdir(parents=True, exist_ok=True)
        Path(dst).write_bytes(b"fake")

    monkeypatch.setattr(ov.urllib.request, "urlretrieve", fake_urlretrieve)
    out = ov._ensure_checkpoints()
    assert out == cache
    # Two of three files were missing.
    assert len(fetched) == len(ov.OV_FILES) - 1
    assert all(u.startswith(ov.OV_BASE) for u in fetched)


def test_is_speaking_starts_false(tmp_path: Path) -> None:
    from sandhyavandanam_guru.audio.tts_openvoice import OpenVoiceSpeaker

    s = OpenVoiceSpeaker(ref_wav=tmp_path / "ref.wav", language="EN_INDIA")
    assert s.is_speaking() is False


def test_say_blank_is_noop(tmp_path: Path) -> None:
    from sandhyavandanam_guru.audio.tts_openvoice import OpenVoiceSpeaker

    s = OpenVoiceSpeaker(ref_wav=tmp_path / "ref.wav", language="EN_INDIA")
    # No imports of openvoice/melo triggered because text is blank.
    s.say("   ")
    assert s.is_speaking() is False


def test_say_logs_error_when_load_fails(tmp_path: Path, monkeypatch) -> None:
    """If model load raises, the worker swallows it and clears speaking flag."""
    import sys
    import types

    # The say() worker calls player.stop() which imports sounddevice; stub it so
    # this test runs even when --extra audio is not installed.
    sd_mod = types.ModuleType("sounddevice")
    sd_mod.stop = lambda: None  # type: ignore[attr-defined]
    sd_mod.play = lambda *a, **kw: None  # type: ignore[attr-defined]
    sd_mod.wait = lambda: None  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "sounddevice", sd_mod)

    from sandhyavandanam_guru.audio.tts_openvoice import OpenVoiceSpeaker

    s = OpenVoiceSpeaker(ref_wav=tmp_path / "ref.wav", language="EN_INDIA")

    def boom() -> None:
        raise RuntimeError("no model")

    monkeypatch.setattr(s, "_ensure_loaded", boom)
    s.say("hello")
    # Worker thread will raise inside _run, log, and clear the flag.
    import time

    deadline = time.time() + 1.5
    while time.time() < deadline:
        if not s.is_speaking():
            break
        time.sleep(0.01)
    assert s.is_speaking() is False
