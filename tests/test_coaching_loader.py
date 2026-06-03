from __future__ import annotations

from pathlib import Path

import pytest

from sandhyavandanam_guru import config
from sandhyavandanam_guru.coaching_loader import Coaching, load_coaching
from sandhyavandanam_guru.ritual_loader import load_ritual


def test_every_step_has_coaching_line() -> None:
    ritual = load_ritual(config.RITUAL_DIR / "pratah_rigveda.yaml")
    coaching = load_coaching(config.RITUAL_DIR / "coaching_en.yaml")
    missing = [s.id for s in ritual.steps if not coaching.for_step(s.id)]
    assert missing == [], f"coaching lines missing for: {missing}"


def test_coaching_lines_are_terse() -> None:
    coaching = load_coaching(Path(config.RITUAL_DIR) / "coaching_en.yaml")
    for sid, line in coaching.lines.items():
        # Keep coaching lines compact — long monologues are not how a guru would speak.
        assert len(line.split()) <= 60, f"{sid} coaching line is too long ({len(line.split())} words)"


def test_for_step_returns_empty_for_unknown_id() -> None:
    coaching = Coaching(lines={"01_aachamanam": "sit"})
    assert coaching.for_step("99_nope") == ""


def test_for_step_strips_whitespace() -> None:
    coaching = Coaching(lines={"01_aachamanam": "   sit and chant   \n"})
    assert coaching.for_step("01_aachamanam") == "sit and chant"


def test_lines_field_required(tmp_path: Path) -> None:
    p = tmp_path / "bad.yaml"
    p.write_text("foo: bar\n")
    with pytest.raises(Exception):
        load_coaching(p)


def test_coaching_lines_match_ritual_step_ids() -> None:
    """No coaching line should reference a step id that doesn't exist."""
    ritual = load_ritual(config.RITUAL_DIR / "pratah_rigveda.yaml")
    coaching = load_coaching(config.RITUAL_DIR / "coaching_en.yaml")
    ritual_ids = {s.id for s in ritual.steps}
    orphans = [sid for sid in coaching.lines if sid not in ritual_ids]
    assert orphans == [], f"orphan coaching ids: {orphans}"
