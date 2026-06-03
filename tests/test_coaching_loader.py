from __future__ import annotations

from pathlib import Path

from sandhyavandanam_guru import config
from sandhyavandanam_guru.coaching_loader import load_coaching
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
