"""Pure-render tests for the TUI helpers (no Textual mounting needed)."""
from __future__ import annotations

import pytest

from sandhyavandanam_guru import config, tui
from sandhyavandanam_guru.coaching_loader import load_coaching
from sandhyavandanam_guru.ritual_loader import load_ritual


@pytest.fixture(scope="module")
def first_step():
    ritual = load_ritual(config.RITUAL_DIR / "pratah_rigveda.yaml")
    return ritual.steps[0]


@pytest.fixture(scope="module")
def coaching():
    return load_coaching(config.RITUAL_DIR / "coaching_en.yaml")


# --- palette ---


def test_palette_constants_are_hex() -> None:
    for c in (tui.SAFFRON, tui.GOLD, tui.KUMKUM, tui.TULSI, tui.CREAM, tui.ASH):
        assert c.startswith("#") and len(c) == 7
        int(c[1:], 16)


def test_palette_distinct() -> None:
    palette = {tui.SAFFRON, tui.GOLD, tui.KUMKUM, tui.TULSI, tui.CREAM, tui.ASH}
    assert len(palette) == 6


# --- status message ---


def test_status_message_idle() -> None:
    msg = tui.status_message("idle", 0)
    assert "IDLE" in msg
    assert "r replay" in msg


def test_status_message_speaking_uses_wave_frames() -> None:
    msg = tui.status_message("speaking", 0)
    assert "GURU IS SPEAKING" in msg
    assert any(ch in msg for ch in "▁▂▃▄▅▆▇█")


def test_status_message_listening_uses_pulse_frames() -> None:
    msg = tui.status_message("listening", 0)
    assert "YOUR TURN" in msg
    assert any(p in msg for p in tui.StatusBar.PULSE_FRAMES)


def test_status_message_loading_shows_spinner_and_hint() -> None:
    msg = tui.status_message("loading", 3)
    assert "WARMING UP" in msg
    assert any(s in msg for s in tui.StatusBar.SPINNER_FRAMES)
    assert "tts.log" in msg


def test_status_message_frame_cycles_safely() -> None:
    # Random large frame counter must not IndexError.
    for f in [0, 1, 7, 8, 99, 10_000]:
        tui.status_message("speaking", f)
        tui.status_message("listening", f)


def test_set_state_rejects_unknown() -> None:
    bar = tui.StatusBar()
    with pytest.raises(ValueError):
        bar.set_state("recording")


def test_status_bar_set_state_resets_frame() -> None:
    bar = tui.StatusBar()
    bar.tick()
    bar.tick()
    assert bar._frame == 2
    bar.set_state("speaking")
    assert bar._frame == 0


def test_status_bar_tick_advances_frame() -> None:
    bar = tui.StatusBar()
    f0 = bar._frame
    bar.tick()
    assert bar._frame == f0 + 1


# --- sanskrit / english blocks ---


def test_sanskrit_block_uses_saffron_and_gold(first_step) -> None:
    out = tui.sanskrit_block(first_step)
    assert tui.SAFFRON in out
    assert tui.GOLD in out
    assert first_step.name_sa in out
    assert first_step.mantra_text.strip().splitlines()[0] in out


def test_sanskrit_block_includes_mantra_label() -> None:
    from sandhyavandanam_guru.ritual_loader import Step

    step = Step(
        id="x",
        name_sa="test",
        name_en="Test",
        posture="sit",
        physical_action="do x",
        mantra_id="m_x",
        mantra_text="om",
        translation="hi",
    )
    out = tui.sanskrit_block(step)
    assert "मन्त्र" in out


def test_english_block_paints_action_kumkum(first_step) -> None:
    out = tui.english_block(first_step, "")
    # Both the label and the body of the action use kumkum.
    assert out.count(tui.KUMKUM) >= 2
    assert "action" in out


def test_english_block_paints_posture_tulsi(first_step) -> None:
    out = tui.english_block(first_step, "")
    assert tui.TULSI in out
    assert "posture" in out


def test_english_block_omits_guru_when_no_coaching(first_step) -> None:
    out = tui.english_block(first_step, "")
    assert "◆ Guru" not in out


def test_english_block_includes_guru_when_coaching_given(first_step) -> None:
    out = tui.english_block(first_step, "Sit down and breathe.")
    assert "◆ Guru" in out
    assert "Sit down and breathe." in out
    assert tui.TULSI in out
    assert tui.CREAM in out


def test_english_block_separates_sections(first_step, coaching) -> None:
    line = coaching.for_step(first_step.id)
    out = tui.english_block(first_step, line)
    for label in ("meaning", "posture", "action"):
        assert label in out
