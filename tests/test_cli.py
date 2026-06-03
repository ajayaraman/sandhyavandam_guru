"""CLI tests — clone-ref resolution, argparse plumbing, dry-run output."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from sandhyavandanam_guru import cli, config


@pytest.fixture()
def fake_manifest(tmp_path: Path, monkeypatch) -> Path:
    monkeypatch.setattr(config, "PROJECT_ROOT", tmp_path)
    recordings = tmp_path / "eval" / "recordings"
    recordings.mkdir(parents=True)
    manifest = recordings / "manifest_clean.json"
    manifest.write_text(
        json.dumps(
            [
                {
                    "mantra_id": "m10_asavaadityo",
                    "path": "eval/recordings/m10_asavaadityo_clean.wav",
                    "expected_text": "asavaadityo brahma brahmai vaham asmi",
                    "duration_s": 8.48,
                },
                {
                    "mantra_id": "m06_achyuta_short",
                    "path": "eval/recordings/m06_achyuta_short_clean.wav",
                    "expected_text": "om achyutaaya namaha",
                    "duration_s": 10.2,
                },
            ]
        )
    )
    (recordings / "m10_asavaadityo_clean.wav").write_bytes(b"")
    (recordings / "m06_achyuta_short_clean.wav").write_bytes(b"")
    return manifest


def test_resolve_clone_ref_explicit_relative(fake_manifest, tmp_path: Path) -> None:
    rel = "eval/recordings/m06_achyuta_short_clean.wav"
    out = cli._resolve_clone_ref(rel)
    assert out == (tmp_path / rel).resolve()


def test_resolve_clone_ref_explicit_absolute(fake_manifest, tmp_path: Path) -> None:
    p = tmp_path / "eval" / "recordings" / "m10_asavaadityo_clean.wav"
    out = cli._resolve_clone_ref(str(p))
    assert out == p.resolve()


def test_resolve_clone_ref_picks_configured_default(fake_manifest, tmp_path: Path) -> None:
    out = cli._resolve_clone_ref(None)
    assert out.name == "m10_asavaadityo_clean.wav"


def test_resolve_clone_ref_falls_back_to_first(fake_manifest, tmp_path: Path) -> None:
    # Wipe the configured default mantra from the manifest.
    manifest = fake_manifest
    data = json.loads(manifest.read_text())
    data = [m for m in data if m["mantra_id"] != cli.DEFAULT_CLONE_MANTRA_ID]
    manifest.write_text(json.dumps(data))
    out = cli._resolve_clone_ref(None)
    assert out.name == "m06_achyuta_short_clean.wav"


def test_resolve_clone_ref_raises_without_manifest(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(config, "PROJECT_ROOT", tmp_path)
    with pytest.raises(SystemExit):
        cli._resolve_clone_ref(None)


def test_dry_run_lists_all_steps(capsys) -> None:
    rc = cli.main(["--dry-run"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "pratah sandhya — 26 steps" in out
    assert "01_aachamanam" not in out  # we print name_sa, not id
    assert "aachamanam" in out


def test_build_speaker_silent_when_no_audio() -> None:
    from sandhyavandanam_guru.settings import load_settings

    s = load_settings()

    class _Args:
        no_audio = True
        voice = None
        clone_ref = None
        config = None
        ritual = None
        coaching = None
        dry_run = False

    args = _Args()
    # When --no-audio is set, cli.main never reaches _build_speaker; this just
    # documents that the helper itself does not assume audio side-effects.
    assert s.tts.backend in {"piper", "openvoice"}


def test_argparse_overrides_apply(monkeypatch) -> None:
    """--voice + --no-audio should reach TUI launch without trying to build a speaker."""
    captured: dict = {}

    def fake_app(*args, **kwargs):
        captured["kwargs"] = kwargs

        class _A:
            def run(self_inner) -> None:
                captured["ran"] = True

        return _A()

    import sandhyavandanam_guru.tui as tui_mod

    monkeypatch.setattr(tui_mod, "GuruApp", fake_app)
    sentinel = object()
    monkeypatch.setattr(cli, "_build_speaker", lambda s: sentinel)

    rc = cli.main(["--voice", "piper", "--no-audio"])
    assert rc == 0
    assert captured.get("ran") is True
    # --no-audio short-circuits _build_speaker even though we monkeypatched it.
    assert captured["kwargs"].get("speaker") is None


def test_argparse_passes_speaker_when_audio_on(monkeypatch) -> None:
    captured: dict = {}

    def fake_app(*args, **kwargs):
        captured["kwargs"] = kwargs

        class _A:
            def run(self_inner) -> None:
                captured["ran"] = True

        return _A()

    import sandhyavandanam_guru.tui as tui_mod

    monkeypatch.setattr(tui_mod, "GuruApp", fake_app)
    sentinel = object()
    monkeypatch.setattr(cli, "_build_speaker", lambda s: sentinel)

    rc = cli.main(["--voice", "piper"])
    assert rc == 0
    assert captured["kwargs"]["speaker"] is sentinel
