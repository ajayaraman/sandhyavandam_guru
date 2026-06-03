from __future__ import annotations

from typing import Protocol

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import Footer, Header, Static

from .coaching_loader import Coaching
from .ritual_loader import Ritual, Step


class Speaker(Protocol):
    def say(self, text: str) -> None: ...
    def stop(self) -> None: ...
    def is_speaking(self) -> bool: ...


class StatusBar(Static):
    """Live indicator for guru-speaking / student-listening states.

    Frames cycle to give the impression of an animated waveform — mirrors what
    voice-conversation apps show during TTS playback.
    """

    WAVE_FRAMES = [
        "▁▂▃▄▅▆▇█▇▆▅▄▃▂",
        "▂▃▄▅▆▇█▇▆▅▄▃▂▁",
        "▃▄▅▆▇█▇▆▅▄▃▂▁▂",
        "▄▅▆▇█▇▆▅▄▃▂▁▂▃",
        "▅▆▇█▇▆▅▄▃▂▁▂▃▄",
        "▆▇█▇▆▅▄▃▂▁▂▃▄▅",
        "▇█▇▆▅▄▃▂▁▂▃▄▅▆",
        "█▇▆▅▄▃▂▁▂▃▄▅▆▇",
    ]
    PULSE_FRAMES = ["●○○", "○●○", "○○●", "○●○"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._state = "idle"
        self._frame = 0
        self.render_now()

    def set_state(self, state: str) -> None:
        if state != self._state:
            self._state = state
            self._frame = 0
        self.render_now()

    def tick(self) -> None:
        self._frame += 1
        self.render_now()

    def render_now(self) -> None:
        if self._state == "speaking":
            wave = self.WAVE_FRAMES[self._frame % len(self.WAVE_FRAMES)]
            self.update(
                f"[bold green]◉[/] [green]guru is speaking[/]  "
                f"[yellow]{wave}[/]   "
                f"[dim]s · silence    r · replay[/]"
            )
        elif self._state == "listening":
            pulse = self.PULSE_FRAMES[self._frame % len(self.PULSE_FRAMES)]
            self.update(
                f"[bold cyan]🎤[/] [cyan]now speak the mantra[/]  "
                f"[yellow]{pulse}[/]   "
                f"[dim]space when done[/]"
            )
        else:
            self.update(
                "[dim]○ idle[/]   "
                "[dim]→ next   ← prev   r replay   s silence   q quit[/]"
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


class SanskritPanel(Static):
    def render_sa(self, step: Step) -> None:
        self.update(
            f"[bold {GOLD}]संस्कृत · sanskrit[/]\n\n"
            f"[bold {GOLD}]{step.name_sa}[/]\n\n"
            f"[bold {SAFFRON}]मन्त्र · mantra[/]\n"
            f"[{SAFFRON}]{step.mantra_text.strip()}[/]"
        )


class EnglishPanel(Static):
    def render_en(self, step: Step, coaching_line: str) -> None:
        guru = (
            f"[bold {TULSI}]◆ Guru[/]\n[{CREAM}]{coaching_line}[/]\n\n"
            if coaching_line
            else ""
        )
        self.update(
            f"[bold {ASH}]english[/]\n\n"
            f"{guru}"
            f"[bold {GOLD}]{step.name_en}[/]\n\n"
            f"[bold {ASH}]meaning[/]\n[{CREAM}]{step.translation}[/]\n\n"
            f"[bold {TULSI}]posture[/]\n[{CREAM}]{step.posture}[/]\n\n"
            f"[bold {KUMKUM}]action[/]\n[{KUMKUM}]{step.physical_action.strip()}[/]"
        )


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
    #status { height: 1; padding: 0 2; background: $boost; color: $text; }
    """
    BINDINGS = [
        Binding("right,space,n", "next_step", "Next"),
        Binding("left,p", "prev_step", "Prev"),
        Binding("home", "first_step", "First"),
        Binding("end", "last_step", "Last"),
        Binding("r", "replay", "Replay"),
        Binding("s", "silence", "Silence"),
        Binding("q", "quit", "Quit"),
    ]

    def __init__(
        self,
        ritual: Ritual,
        coaching: Coaching | None = None,
        speaker: Speaker | None = None,
    ):
        super().__init__()
        self.ritual = ritual
        self.coaching = coaching
        self.speaker = speaker
        self.index = 0

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
        self._refresh(speak=True)
        # 8 Hz status refresh — fast enough for a fluid waveform, cheap enough
        # for the terminal (one Static update per tick).
        self.set_interval(1 / 8, self._tick_status)

    def _tick_status(self) -> None:
        bar = self.query_one("#status", StatusBar)
        if self.speaker is not None and self.speaker.is_speaking():
            bar.set_state("speaking")
            bar.tick()
        else:
            bar.set_state("idle")

    def _coaching_line(self, step: Step) -> str:
        if self.coaching is None:
            return ""
        return self.coaching.for_step(step.id)

    def _refresh(self, speak: bool = False) -> None:
        step = self.ritual.steps[self.index]
        total = len(self.ritual.steps)
        line = self._coaching_line(step)
        self.query_one("#step_header", StepHeader).render_header(step, self.index, total)
        self.query_one("#sa", SanskritPanel).render_sa(step)
        self.query_one("#en", EnglishPanel).render_en(step, line)
        self.query_one("#sidebar", SidebarView).render_outline(self.ritual, self.index)
        if speak and self.speaker and line:
            self.speaker.say(line)

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

    def action_silence(self) -> None:
        if self.speaker:
            self.speaker.stop()
