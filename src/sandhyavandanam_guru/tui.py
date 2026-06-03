from __future__ import annotations

from typing import Protocol

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import Footer, Header, Static

import logging as _logging

from . import config as _cfg
from .audio.chanter import Chanter
from .coaching_loader import Coaching
from .lesson import Substep, build_lesson
from .mantra_text import parse_mantra
from .ritual_loader import Ritual, Step

_cfg.USER_DATA_DIR.mkdir(parents=True, exist_ok=True)
_tui_log = _logging.getLogger("sgr.tui")
if not _tui_log.handlers:
    _h = _logging.FileHandler(_cfg.USER_DATA_DIR / "tts.log")
    _h.setFormatter(_logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    _tui_log.addHandler(_h)
    _tui_log.setLevel(_logging.INFO)


class Speaker(Protocol):
    def say(self, text: str) -> None: ...
    def stop(self) -> None: ...
    def is_speaking(self) -> bool: ...
    def state(self) -> str: ...  # "idle" | "loading" | "speaking" | "listening"


class StatusBar(Static):
    """Live indicator for guru-speaking / student-listening states.

    Frames cycle to give the impression of an animated waveform — mirrors what
    voice-conversation apps show during TTS playback.
    """

    WAVE_FRAMES = [
        "▁▂▃▄▅▆▇█▇▆▅▄▃▂▁▂▃▄▅▆▇█▇▆▅▄▃▂",
        "▂▃▄▅▆▇█▇▆▅▄▃▂▁▂▃▄▅▆▇█▇▆▅▄▃▂▁",
        "▃▄▅▆▇█▇▆▅▄▃▂▁▂▃▄▅▆▇█▇▆▅▄▃▂▁▂",
        "▄▅▆▇█▇▆▅▄▃▂▁▂▃▄▅▆▇█▇▆▅▄▃▂▁▂▃",
        "▅▆▇█▇▆▅▄▃▂▁▂▃▄▅▆▇█▇▆▅▄▃▂▁▂▃▄",
        "▆▇█▇▆▅▄▃▂▁▂▃▄▅▆▇█▇▆▅▄▃▂▁▂▃▄▅",
        "▇█▇▆▅▄▃▂▁▂▃▄▅▆▇█▇▆▅▄▃▂▁▂▃▄▅▆",
        "█▇▆▅▄▃▂▁▂▃▄▅▆▇█▇▆▅▄▃▂▁▂▃▄▅▆▇",
    ]
    PULSE_FRAMES = ["●○○○", "○●○○", "○○●○", "○○○●", "○○●○", "○●○○"]
    SPINNER_FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
    VALID_STATES = {"idle", "speaking", "listening", "loading", "chanting"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._state = "idle"
        self._frame = 0
        self.render_now()

    def set_state(self, state: str) -> None:
        if state not in self.VALID_STATES:
            raise ValueError(f"invalid status state: {state!r}")
        if state != self._state:
            self._state = state
            self._frame = 0
        self.render_now()

    def tick(self) -> None:
        self._frame += 1
        self.render_now()

    def render_now(self) -> None:
        self.update(status_message(self._state, self._frame))


def status_message(state: str, frame: int) -> str:
    """Pure helper for StatusBar rendering. Kept testable in isolation."""
    if state == "speaking":
        wave = StatusBar.WAVE_FRAMES[frame % len(StatusBar.WAVE_FRAMES)]
        return (
            f"\n[bold green on grey15]  ◉  GURU IS SPEAKING  [/]"
            f"   [bold yellow]{wave}[/]\n"
            f"  [dim]press[/] [bold]s[/] [dim]to silence    press[/] [bold]r[/] [dim]to replay[/]"
        )
    if state == "listening":
        pulse = StatusBar.PULSE_FRAMES[frame % len(StatusBar.PULSE_FRAMES)]
        return (
            f"\n[bold black on cyan]  🎤  YOUR TURN — RECITE THE MANTRA  [/]"
            f"   [bold yellow]{pulse}[/]\n"
            f"  [dim]press[/] [bold]space[/] [dim]when you're done[/]"
        )
    if state == "chanting":
        wave = StatusBar.WAVE_FRAMES[frame % len(StatusBar.WAVE_FRAMES)]
        return (
            f"\n[bold black on #FF9933]  ॐ  GURU IS CHANTING  [/]"
            f"   [bold yellow]{wave}[/]\n"
            f"  [dim]press[/] [bold]s[/] [dim]to silence    press[/] [bold]m[/] [dim]to replay mantra[/]"
        )
    if state == "loading":
        spin = StatusBar.SPINNER_FRAMES[frame % len(StatusBar.SPINNER_FRAMES)]
        return (
            f"\n[bold black on yellow]  {spin}  GURU IS WARMING UP  [/]"
            f"   [yellow]first run may download model files (~500 MB)[/]\n"
            f"  [dim]tail ~/.local/share/sandhyavandanam_guru/tts.log to watch progress[/]"
        )
    return (
        "\n[bold black on white]  ○  IDLE  [/]"
        "   [dim]→ next   ← prev   r replay   s silence   q quit[/]\n"
        "  [dim]waiting for you to advance[/]"
    )


class StepHeader(Static):
    def render_header(self, step: Step, index: int, total: int) -> None:
        self.update(
            f"[bold cyan]Step {index + 1} / {total}[/]   "
            f"[bold magenta]{step.name_sa}[/]  ·  [italic]{step.name_en}[/]\n"
            f"[dim]repeat × {step.repeat_count}  ·  advance: {step.advance_rule}[/]"
        )


# Palette — drawn from Vedic ritual associations:
#   saffron (#FF9933)   sacred chant, the mantra itself
#   gold    (#D4A017)   the deity / sacred name
#   kumkum  (#C23B22)   physical action / vermillion mark
#   tulsi   (#558B2F)   posture / the leaf-bearing body
#   cream   (#F5E6C8)   meaning / sandalwood paste
#   ash     (#9E9E9E)   subdued labels
SAFFRON = "#FF9933"
GOLD = "#D4A017"
KUMKUM = "#C23B22"
TULSI = "#558B2F"
CREAM = "#F5E6C8"
ASH = "#9E9E9E"


def sanskrit_block(step: Step) -> str:
    return (
        f"[bold {GOLD}]संस्कृत · sanskrit[/]\n\n"
        f"[bold {GOLD}]{step.name_sa}[/]\n\n"
        f"[bold {SAFFRON}]मन्त्र · mantra[/]\n"
        f"[{SAFFRON}]{step.mantra_text.strip()}[/]"
    )


def english_block(step: Step, coaching_line: str) -> str:
    guru = (
        f"[bold {TULSI}]◆ Guru[/]\n[{CREAM}]{coaching_line}[/]\n\n"
        if coaching_line
        else ""
    )
    return (
        f"[bold {ASH}]english[/]\n\n"
        f"{guru}"
        f"[bold {GOLD}]{step.name_en}[/]\n\n"
        f"[bold {ASH}]meaning[/]\n[{CREAM}]{step.translation}[/]\n\n"
        f"[bold {TULSI}]posture[/]\n[{CREAM}]{step.posture}[/]\n\n"
        f"[bold {KUMKUM}]action[/]\n[{KUMKUM}]{step.physical_action.strip()}[/]"
    )


class SanskritPanel(Static):
    def render_sa(self, step: Step) -> None:
        self.update(sanskrit_block(step))


class EnglishPanel(Static):
    def render_en(self, step: Step, coaching_line: str) -> None:
        self.update(english_block(step, coaching_line))


class SidebarView(Static):
    def render_outline(self, ritual: Ritual, current: int) -> None:
        lines = []
        for i, step in enumerate(ritual.steps):
            marker = "▶" if i == current else " "
            style = "bold green" if i == current else "dim"
            lines.append(f"[{style}]{marker} {i + 1:>2}. {step.name_sa}[/]")
        self.update("\n".join(lines))


class GuruApp(App):
    CSS = """
    Screen { layout: vertical; }
    #body { height: 1fr; }
    #sidebar { width: 30; border-right: solid grey; padding: 1; }
    #main { padding: 1 2; }
    #step_header { height: auto; padding-bottom: 1; border-bottom: solid grey; }
    #cols { height: 1fr; padding-top: 1; }
    #sa, #en { width: 1fr; padding: 1 2; border: round grey; }
    #status { height: 4; padding: 0 2; border-top: heavy $accent; }
    """
    BINDINGS = [
        Binding("right,space,n", "next_step", "Next"),
        Binding("left,p", "prev_step", "Prev"),
        Binding("home", "first_step", "First"),
        Binding("end", "last_step", "Last"),
        Binding("r", "replay", "Replay"),
        Binding("m", "replay_mantra", "Mantra"),
        Binding("s", "silence", "Silence"),
        Binding("q", "quit", "Quit"),
    ]

    def __init__(
        self,
        ritual: Ritual,
        coaching: Coaching | None = None,
        speaker: Speaker | None = None,
        chanter: Chanter | None = None,
    ):
        super().__init__()
        self.ritual = ritual
        self.coaching = coaching
        self.speaker = speaker
        self.chanter = chanter if chanter is not None else Chanter(
            _cfg.PROJECT_ROOT / "assets" / "mantras"
        )
        self.index = 0
        from collections import deque
        self._queue: deque[Substep] = deque()
        self._prev_speaker_state = "idle"
        self._prev_chanter_busy = False
        # Per-line action announcements — configurable later via settings.
        self.announce_per_line_actions = True

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        with Horizontal(id="body"):
            yield SidebarView(id="sidebar")
            with Vertical(id="main"):
                yield StepHeader(id="step_header")
                with Horizontal(id="cols"):
                    yield SanskritPanel(id="sa")
                    yield EnglishPanel(id="en")
                yield StatusBar(id="status")
        yield Footer()

    def on_mount(self) -> None:
        self.title = "Sandhyavandanam Guru"
        self.sub_title = f"{self.ritual.sandhya_kind} sandhya"
        if self.speaker is not None and hasattr(self.speaker, "prime"):
            self.speaker.prime(self.coaching)  # type: ignore[attr-defined]
        self._refresh(speak=True)
        # 8 Hz status refresh — fast enough for a fluid waveform, cheap enough
        # for the terminal (one Static update per tick).
        self.set_interval(1 / 8, self._tick_status)

    def _tick_status(self) -> None:
        bar = self.query_one("#status", StatusBar)
        speaker_state = "idle"
        if self.speaker is not None:
            if hasattr(self.speaker, "state"):
                speaker_state = self.speaker.state()
            elif self.speaker.is_speaking():
                speaker_state = "speaking"

        chanter_busy = self.chanter.is_chanting()
        both_idle = speaker_state == "idle" and not chanter_busy
        was_active = (
            self._prev_speaker_state in ("speaking", "loading") or self._prev_chanter_busy
        )
        # Dispatch the next substep when both speaker and chanter go idle
        # (either just transitioned, or queue was filled while already idle).
        if both_idle and self._queue:
            self._dispatch_next()
        self._prev_speaker_state = speaker_state
        self._prev_chanter_busy = chanter_busy

        state = speaker_state
        if state == "idle" and chanter_busy:
            state = "chanting"
        bar.set_state(state)
        if state != "idle":
            bar.tick()

    def _dispatch_next(self) -> None:
        sub = self._queue.popleft()
        _tui_log.info("dispatch %s (%s)", sub.kind, sub.text[:40].replace("\n", " "))
        if sub.kind == "speak":
            if self.speaker:
                self.speaker.say(sub.text)
            return
        if sub.kind == "chant":
            self.chanter.chant(sub.mantra_id, mantra_text=sub.text, line_index=sub.line_index)
            return
        # Phase 4: listen substep — for now a no-op so the lesson advances.
        if sub.kind == "listen":
            return

    def _coaching_line(self, step: Step) -> str:
        if self.coaching is None:
            return ""
        return self.coaching.for_step(step.id)

    def _refresh(self, speak: bool = False) -> None:
        step = self.ritual.steps[self.index]
        total = len(self.ritual.steps)
        coaching = self._coaching_line(step)
        self.query_one("#step_header", StepHeader).render_header(step, self.index, total)
        self.query_one("#sa", SanskritPanel).render_sa(step)
        self.query_one("#en", EnglishPanel).render_en(step, coaching)
        self.query_one("#sidebar", SidebarView).render_outline(self.ritual, self.index)
        # Reset everything from the previous step.
        if self.speaker:
            self.speaker.stop()
        self.chanter.stop()
        self._queue.clear()
        self._prev_speaker_state = "idle"
        self._prev_chanter_busy = False
        if not speak:
            return
        # Build the per-step lesson queue: coaching → (action → chant)*  per line.
        parsed = parse_mantra(step.mantra_text)
        has_chant = self.chanter.has(step.mantra_id)
        per_line_available = has_chant and self.chanter.has_any_line_clip(
            step.mantra_id, len(parsed.lines)
        )
        self._queue = build_lesson(
            coaching_line=coaching,
            parsed_mantra=parsed if has_chant else parse_mantra(""),
            mantra_id=step.mantra_id,
            announce_per_line_actions=self.announce_per_line_actions,
            call_and_response=False,  # Phase 4 will flip this on per advance_rule
            per_line_clips_available=per_line_available,
        )
        # Warm the synth cache while the coaching is spoken so the first chant
        # has zero perceived latency.
        if has_chant:
            self.chanter.prefetch(step.mantra_id, parsed.cleaned)
        _tui_log.info(
            "lesson built: %d substeps for step=%s has_chant=%s",
            len(self._queue), step.id, has_chant,
        )
        # Kick the first substep immediately so the user hears the guru without
        # waiting for the first tick (~125 ms).
        if self._queue:
            self._dispatch_next()

    def action_next_step(self) -> None:
        if self.index < len(self.ritual.steps) - 1:
            self.index += 1
            self._refresh(speak=True)

    def action_prev_step(self) -> None:
        if self.index > 0:
            self.index -= 1
            self._refresh(speak=True)

    def action_first_step(self) -> None:
        self.index = 0
        self._refresh(speak=True)

    def action_last_step(self) -> None:
        self.index = len(self.ritual.steps) - 1
        self._refresh(speak=True)

    def action_replay(self) -> None:
        if self.speaker:
            step = self.ritual.steps[self.index]
            self.speaker.say(self._coaching_line(step))

    def action_replay_mantra(self) -> None:
        step = self.ritual.steps[self.index]
        _tui_log.info(
            "m pressed: step=%s mantra=%s has_wav=%s",
            step.id, step.mantra_id, self.chanter.has(step.mantra_id),
        )
        if self.chanter.has(step.mantra_id):
            self._pending_chant = None
            if self.speaker:
                self.speaker.stop()
            self.chanter.chant(step.mantra_id, mantra_text=parse_mantra(step.mantra_text).cleaned)

    def action_silence(self) -> None:
        if self.speaker:
            self.speaker.stop()
        self._pending_chant = None
        self.chanter.stop()
