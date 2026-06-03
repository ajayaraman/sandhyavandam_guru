"""Coverage tests for the --recording mode.

Verifies that, for every step in the ritual that has a recording on disk:
  • Coaching wav exists at assets/coaching/<step_id>.wav.
  • If any per-line mantra clip exists for a mantra, ALL expected lines exist
    (no gaps that would cause the lesson queue to silently skip a line).
  • The Chanter resolves per-line clips when present and the whole-mantra clip
    when only that exists, and reports has() correctly in both cases.
  • build_lesson() emits one chant substep per recorded line, in order.

These tests are skipped (not failed) when nothing has been recorded yet, so the
suite still passes on a fresh clone.
"""
from __future__ import annotations

import os
from collections import Counter
from pathlib import Path

import pytest

# The two filesystem-coverage tests (coaching wavs / per-line gaps) are opt-in:
# they audit YOUR recorded assets, which a fresh clone of the repo doesn't have.
# Enable with: SGR_CHECK_RECORDINGS=1 uv run pytest
_CHECK_RECORDINGS = os.environ.get("SGR_CHECK_RECORDINGS") == "1"
_disk_only = pytest.mark.skipif(
    not _CHECK_RECORDINGS,
    reason="set SGR_CHECK_RECORDINGS=1 to audit assets/coaching and assets/mantras",
)

from sandhyavandanam_guru import config
from sandhyavandanam_guru.audio.chanter import Chanter
from sandhyavandanam_guru.lesson import build_lesson
from sandhyavandanam_guru.mantra_text import parse_mantra
from sandhyavandanam_guru.ritual_loader import load_ritual

COACHING_DIR = config.PROJECT_ROOT / "assets" / "coaching"
MANTRA_DIR = config.PROJECT_ROOT / "assets" / "mantras"


@pytest.fixture(scope="module")
def ritual():
    return load_ritual(config.PROJECT_ROOT / "ritual" / "pratah_rigveda.yaml")


def _coaching_wavs() -> set[str]:
    if not COACHING_DIR.exists():
        return set()
    return {p.stem for p in COACHING_DIR.glob("*.wav")}


def _mantra_files() -> set[str]:
    if not MANTRA_DIR.exists():
        return set()
    return {p.name for p in MANTRA_DIR.glob("*.wav")}


@_disk_only
def test_coaching_recordings_cover_every_step(ritual) -> None:
    have = _coaching_wavs()
    if not have:
        pytest.skip("no coaching recordings on disk yet")
    missing = [s.id for s in ritual.steps if s.id not in have]
    assert not missing, (
        f"coaching wavs missing for steps: {missing}. "
        f"Run: uv run python scripts/record_coaching.py"
    )


@_disk_only
def test_per_line_recordings_have_no_gaps(ritual) -> None:
    """If any line of a mantra is recorded, all expected lines must be present.

    A mid-mantra gap means the lesson queue would silently skip that line
    (chanter falls back to the whole-mantra wav, which we may not even have).
    """
    files = _mantra_files()
    if not files:
        pytest.skip("no mantra recordings on disk yet")
    indices_by_id: dict[str, set[int]] = {}
    for name in files:
        stem = name[:-4]  # drop .wav
        if "__" not in stem:
            continue
        mid, idx = stem.rsplit("__", 1)
        try:
            indices_by_id.setdefault(mid, set()).add(int(idx))
        except ValueError:
            continue

    # de-dupe mantra_ids in step order
    seen: set[str] = set()
    mantras_by_id: dict[str, str] = {}
    for s in ritual.steps:
        if s.mantra_id in seen:
            continue
        seen.add(s.mantra_id)
        mantras_by_id[s.mantra_id] = s.mantra_text

    problems: list[str] = []
    for mid, idxs in indices_by_id.items():
        if mid not in mantras_by_id:
            continue
        expected = len(parse_mantra(mantras_by_id[mid]).lines)
        full_set = set(range(1, expected + 1))
        missing = sorted(full_set - idxs)
        extras = sorted(idxs - full_set)
        if missing:
            problems.append(f"{mid}: missing lines {missing} (expected 1..{expected})")
        if extras:
            problems.append(f"{mid}: extra clips for lines not in mantra: {extras}")
    assert not problems, "Per-line recording gaps:\n  " + "\n  ".join(problems)


def test_chanter_resolves_per_line_then_whole(tmp_path) -> None:
    # Stub out a tiny bank with two per-line clips and a fallback whole clip.
    (tmp_path / "mX__1.wav").write_bytes(b"line1")
    (tmp_path / "mX__2.wav").write_bytes(b"line2")
    (tmp_path / "mY.wav").write_bytes(b"whole")

    c = Chanter(tmp_path)
    assert c.has("mX") is True       # per-line present
    assert c.has("mY") is True       # whole present
    assert c.has("mZ") is False      # neither
    assert c.has_line_clip("mX", 1) is True
    assert c.has_line_clip("mX", 3) is False
    assert c.has_any_line_clip("mX", 5) is True
    assert c.has_any_line_clip("mY", 5) is False
    assert c.has_any_line_clip("mZ", 5) is False


def test_build_lesson_uses_per_line_when_available() -> None:
    parsed = parse_mantra("line one (touch head)\nline two (touch chest)")
    q = build_lesson(
        coaching_line="do this",
        parsed_mantra=parsed,
        mantra_id="mX",
        announce_per_line_actions=False,
        per_line_clips_available=True,
    )
    kinds = [s.kind for s in q]
    line_indices = [s.line_index for s in q if s.kind == "chant"]
    assert kinds.count("chant") == 2
    assert line_indices == [1, 2]


def test_build_lesson_collapses_when_no_per_line() -> None:
    parsed = parse_mantra("line one\nline two\nline three")
    q = build_lesson(
        coaching_line="do this",
        parsed_mantra=parsed,
        mantra_id="mX",
        announce_per_line_actions=False,
        per_line_clips_available=False,
    )
    chants = [s for s in q if s.kind == "chant"]
    assert len(chants) == 1, "expected single whole-mantra chant when per-line wavs absent"
    assert chants[0].line_index == 0
    assert "line one" in chants[0].text and "line three" in chants[0].text


def test_recorded_speaker_keys_off_coaching_text(tmp_path) -> None:
    """RecordedSpeaker should resolve a coaching line back to <step_id>.wav."""
    from sandhyavandanam_guru.audio.tts_recording import RecordedSpeaker
    from sandhyavandanam_guru.coaching_loader import Coaching

    (tmp_path / "01_x.wav").write_bytes(b"\x00" * 100)
    coaching = Coaching(lines={"01_x": "hello world line"})
    spk = RecordedSpeaker(tmp_path)
    spk.prime(coaching)
    # Resolver should find the wav for the trimmed coaching text.
    assert spk._resolve_path("hello world line") == tmp_path / "01_x.wav"
    assert spk._resolve_path("not a known line") is None


def test_chanter_has_handles_only_per_line_clips(tmp_path) -> None:
    """Reproduces the bug: per-line clips present, whole-mantra missing."""
    (tmp_path / "m01__1.wav").write_bytes(b"x")
    (tmp_path / "m01__2.wav").write_bytes(b"x")
    c = Chanter(tmp_path)
    assert c.has("m01") is True, "Chanter.has should return True when only per-line clips exist"
