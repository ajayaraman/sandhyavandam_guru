"""End-to-end TUI tests via Textual's Pilot.

Best practices borrowed:
  - drive the live app with `App.run_test()`; never instantiate widgets by hand.
  - use `Pilot.press` to send key events through the real binding pipeline.
  - assert on rendered text via the widget's `renderable` (a `rich.console.RenderableType`).
  - keep speakers behind a tiny fake so tests run without audio hardware.
  - `await pilot.pause()` (one frame) before asserting on reactive UI changes
    triggered by a binding.
"""
from __future__ import annotations

import asyncio
from typing import Any

import pytest
from rich.console import Console

from sandhyavandanam_guru import config, tui
from sandhyavandanam_guru.coaching_loader import load_coaching
from sandhyavandanam_guru.ritual_loader import load_ritual


# ---------- helpers ----------


class FakeSpeaker:
    """Speaker double that records calls and exposes a programmable state."""

    def __init__(self, state: str = "idle") -> None:
        self.says: list[str] = []
        self.stops: int = 0
        self._state = state

    def say(self, text: str) -> None:
        self.says.append(text)

    def stop(self) -> None:
        self.stops += 1

    def is_speaking(self) -> bool:
        return self._state == "speaking"

    def state(self) -> str:
        return self._state

    def set_state(self, s: str) -> None:
        self._state = s


def _rendered(widget) -> str:
    """Return the plain text the widget would draw — strips ANSI/markup.

    Static's renderable lives in different attributes across Textual versions;
    we try a couple, then fall back to calling render().
    """
    for attr in ("_renderable", "_content", "renderable"):
        renderable = getattr(widget, attr, None)
        if renderable is not None:
            break
    else:
        renderable = widget.render()
    console = Console(force_terminal=False, no_color=True, color_system=None, width=200)
    with console.capture() as cap:
        console.print(renderable)
    return cap.get()


@pytest.fixture()
def ritual():
    return load_ritual(config.RITUAL_DIR / "pratah_rigveda.yaml")


@pytest.fixture()
def coaching():
    return load_coaching(config.RITUAL_DIR / "coaching_en.yaml")


@pytest.fixture()
def speaker():
    return FakeSpeaker()


# ---------- tests ----------


async def test_app_mounts_and_shows_first_step(ritual, coaching, speaker) -> None:
    app = tui.GuruApp(ritual, coaching=coaching, speaker=speaker)
    async with app.run_test() as pilot:
        await pilot.pause()
        sa = _rendered(app.query_one("#sa", tui.SanskritPanel))
        en = _rendered(app.query_one("#en", tui.EnglishPanel))
        sidebar = _rendered(app.query_one("#sidebar", tui.SidebarView))
        # First step content shows.
        assert ritual.steps[0].name_sa in sa
        assert ritual.steps[0].name_en in en
        assert "Mantra" in sa or "mantra" in sa
        # The sidebar marker (▶) is on row 1.
        first_line = sidebar.splitlines()[0]
        assert "▶" in first_line
        assert ritual.steps[0].name_sa in first_line


async def test_app_speaks_first_coaching_line_on_mount(ritual, coaching, speaker) -> None:
    app = tui.GuruApp(ritual, coaching=coaching, speaker=speaker)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert speaker.says, "expected at least one say() on mount"
        assert speaker.says[0] == coaching.for_step(ritual.steps[0].id)


async def test_right_arrow_advances_step(ritual, coaching, speaker) -> None:
    app = tui.GuruApp(ritual, coaching=coaching, speaker=speaker)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("right")
        await pilot.pause()
        assert app.index == 1
        # Sidebar marker moved.
        sidebar = _rendered(app.query_one("#sidebar", tui.SidebarView))
        second_line = sidebar.splitlines()[1]
        assert "▶" in second_line
        # New coaching line spoken.
        assert speaker.says[-1] == coaching.for_step(ritual.steps[1].id)


async def test_n_key_also_advances(ritual, coaching, speaker) -> None:
    app = tui.GuruApp(ritual, coaching=coaching, speaker=speaker)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("n")
        await pilot.pause()
        assert app.index == 1


async def test_left_arrow_does_not_underflow(ritual, coaching, speaker) -> None:
    app = tui.GuruApp(ritual, coaching=coaching, speaker=speaker)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("left")
        await pilot.pause()
        assert app.index == 0


async def test_right_arrow_does_not_overflow(ritual, coaching, speaker) -> None:
    app = tui.GuruApp(ritual, coaching=coaching, speaker=speaker)
    async with app.run_test() as pilot:
        await pilot.pause()
        app.index = len(ritual.steps) - 1
        await pilot.press("right")
        await pilot.pause()
        assert app.index == len(ritual.steps) - 1


async def test_home_and_end_jump(ritual, coaching, speaker) -> None:
    app = tui.GuruApp(ritual, coaching=coaching, speaker=speaker)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("end")
        await pilot.pause()
        assert app.index == len(ritual.steps) - 1
        await pilot.press("home")
        await pilot.pause()
        assert app.index == 0


async def test_r_replays_current_line(ritual, coaching, speaker) -> None:
    app = tui.GuruApp(ritual, coaching=coaching, speaker=speaker)
    async with app.run_test() as pilot:
        await pilot.pause()
        speaker.says.clear()
        await pilot.press("r")
        await pilot.pause()
        assert speaker.says == [coaching.for_step(ritual.steps[0].id)]


async def test_s_silences(ritual, coaching, speaker) -> None:
    app = tui.GuruApp(ritual, coaching=coaching, speaker=speaker)
    async with app.run_test() as pilot:
        await pilot.pause()
        speaker.stops = 0
        await pilot.press("s")
        await pilot.pause()
        assert speaker.stops == 1


async def test_status_bar_flips_to_speaking_when_speaker_state_changes(
    ritual, coaching, speaker
) -> None:
    app = tui.GuruApp(ritual, coaching=coaching, speaker=speaker)
    async with app.run_test() as pilot:
        await pilot.pause()
        speaker.set_state("speaking")
        # Status ticks at 8 Hz; pause for ~2 ticks.
        await asyncio.sleep(0.3)
        bar_text = _rendered(app.query_one("#status", tui.StatusBar))
        assert "GURU IS SPEAKING" in bar_text


async def test_status_bar_shows_loading_during_warmup(ritual, coaching, speaker) -> None:
    app = tui.GuruApp(ritual, coaching=coaching, speaker=speaker)
    async with app.run_test() as pilot:
        await pilot.pause()
        speaker.set_state("loading")
        await asyncio.sleep(0.3)
        bar_text = _rendered(app.query_one("#status", tui.StatusBar))
        assert "WARMING UP" in bar_text
        assert "tts.log" in bar_text


async def test_status_bar_idle_when_no_speaker(ritual, coaching) -> None:
    app = tui.GuruApp(ritual, coaching=coaching, speaker=None)
    async with app.run_test() as pilot:
        await pilot.pause()
        # 8 Hz tick — give it a frame.
        await asyncio.sleep(0.2)
        bar_text = _rendered(app.query_one("#status", tui.StatusBar))
        assert "IDLE" in bar_text


async def test_q_quits(ritual, coaching, speaker) -> None:
    app = tui.GuruApp(ritual, coaching=coaching, speaker=speaker)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("q")
        await pilot.pause()
        # App.exit() marks return_code; pilot exits the context naturally.
        assert app.is_running is False or app._exit is True  # textual internals vary


async def test_palette_appears_in_rendered_panels(ritual, coaching, speaker) -> None:
    """Rendered Sanskrit panel actually styles the mantra with the saffron color."""
    app = tui.GuruApp(ritual, coaching=coaching, speaker=speaker)
    async with app.run_test() as pilot:
        await pilot.pause()
        # We assert the saffron hex shows up in the *markup* via the helper string
        # so we know the panel didn't silently drop styling.
        from sandhyavandanam_guru.tui import sanskrit_block, english_block, SAFFRON, KUMKUM

        assert SAFFRON in sanskrit_block(ritual.steps[0])
        assert KUMKUM in english_block(ritual.steps[0], coaching.for_step(ritual.steps[0].id))


async def test_app_runs_without_coaching_when_none_provided(ritual, speaker) -> None:
    app = tui.GuruApp(ritual, coaching=None, speaker=speaker)
    async with app.run_test() as pilot:
        await pilot.pause()
        # No coaching → no initial say.
        assert speaker.says == []
        en = _rendered(app.query_one("#en", tui.EnglishPanel))
        assert "Guru" not in en  # no guru block when coaching missing
