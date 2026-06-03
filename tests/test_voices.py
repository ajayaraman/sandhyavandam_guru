from __future__ import annotations

from pathlib import Path

import pytest

from sandhyavandanam_guru.audio import voices


def test_voice_paths_table_has_known_entries() -> None:
    assert "en_US-lessac-medium" in voices.PIPER_VOICE_PATHS
    # Every value is a relative HF path without file extension.
    for v in voices.PIPER_VOICE_PATHS.values():
        assert not v.endswith(".onnx")
        assert not v.startswith("/")


def test_unknown_voice_raises() -> None:
    with pytest.raises(ValueError):
        voices.ensure_piper_voice("bogus-voice")


def test_cache_dir_writable(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    d = voices.piper_cache_dir()
    assert d.exists() and d.is_dir()
    # Idempotent
    assert voices.piper_cache_dir() == d


def test_ensure_voice_skips_download_when_files_present(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    cache = voices.piper_cache_dir()
    voice = "en_US-lessac-medium"
    (cache / f"{voice}.onnx").write_bytes(b"fake")
    (cache / f"{voice}.onnx.json").write_text("{}")

    called: list[str] = []

    def fake_urlretrieve(url: str, dst):  # pragma: no cover - should not run
        called.append(url)

    monkeypatch.setattr(voices.urllib.request, "urlretrieve", fake_urlretrieve)
    onnx, cfg = voices.ensure_piper_voice(voice)
    assert called == []
    assert onnx.exists() and cfg.exists()


def test_ensure_voice_downloads_missing(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    voice = "en_US-lessac-medium"

    urls: list[str] = []

    def fake_urlretrieve(url: str, dst):
        urls.append(url)
        Path(dst).write_bytes(b"fake")

    monkeypatch.setattr(voices.urllib.request, "urlretrieve", fake_urlretrieve)
    onnx, cfg = voices.ensure_piper_voice(voice)
    assert onnx.exists() and cfg.exists()
    assert any(u.endswith(f"{voice}.onnx") for u in urls)
    assert any(u.endswith(f"{voice}.onnx.json") for u in urls)
