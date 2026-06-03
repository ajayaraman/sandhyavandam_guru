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


class StepHeader(Static):
    def render_header(self, step: Step, index: int, total: int) -> None:
        self.update(
            f"[bold cyan]Step {index + 1} / {total}[/]   "
            f"[bold magenta]{step.name_sa}[/]  ·  [italic]{step.name_en}[/]\n"
            f"[dim]repeat × {step.repeat_count}  ·  advance: {step.advance_rule}[/]"
        )


class SanskritPanel(Static):
    def render_sa(self, step: Step) -> None:
        self.update(
            f"[bold yellow]संस्कृत · sanskrit[/]\n\n"
            f"[bold magenta]{step.name_sa}[/]\n\n"
            f"[bold]Mantra[/]\n[white]{step.mantra_text.strip()}[/]"
        )


class EnglishPanel(Static):
    def render_en(self, step: Step, coaching_line: str) -> None:
        guru = f"[bold green]Guru[/]\n{coaching_line}\n\n" if coaching_line else ""
        self.update(
            f"[bold yellow]english[/]\n\n"
            f"{guru}"
            f"[bold]{step.name_en}[/]\n\n"
            f"[bold]Meaning[/]\n{step.translation}\n\n"
            f"[bold]Posture[/]\n{step.posture}\n\n"
            f"[bold]What to do[/]\n{step.physical_action.strip()}"
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
        yield Footer()

    def on_mount(self) -> None:
        self.title = "Sandhyavandanam Guru"
        self.sub_title = f"{self.ritual.sandhya_kind} sandhya"
        self._refresh(speak=True)

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
