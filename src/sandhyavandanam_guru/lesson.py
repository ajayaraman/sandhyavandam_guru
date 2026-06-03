"""Per-step substep queue: drive line-by-line guru → student flow within a step.

A step's lesson is a sequence of substeps:
  • "speak"  — guru voice utters an English cue (action / coaching nudge)
  • "chant"  — guru voice chants one Sanskrit line of the mantra
  • "listen" — [Phase 4] open the mic and score the student's repetition

The queue is consumed by the TUI tick loop: pop the next substep when both the
speaker and the chanter are idle. Pauses between lines fall out for free.

Building blocks for Phase 4: a "listen" item slotted after each "chant" turns
the same machinery into call-and-response. Until then, listens are skipped.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Literal

from .mantra_text import ParsedMantra


SubKind = Literal["speak", "chant", "listen"]


@dataclass(frozen=True)
class Substep:
    kind: SubKind
    text: str = ""         # for speak: english cue; for chant: sanskrit line
    mantra_id: str = ""    # for chant: the canonical id (cache key)
    is_line: bool = False  # chant of a single line vs the whole mantra
    line_index: int = 0    # 1-based line number for per-line clips (0 = whole)


def build_lesson(
    coaching_line: str,
    parsed_mantra: ParsedMantra,
    mantra_id: str,
    *,
    announce_per_line_actions: bool,
    call_and_response: bool = False,
    per_line_clips_available: bool = False,
) -> deque[Substep]:
    """Build the substep queue for a single ritual step.

    coaching_line: the base english coaching utterance (may be "").
    parsed_mantra: from parse_mantra(step.mantra_text).
    announce_per_line_actions: speak the action cue tied to each mantra line.
    call_and_response: after each line, slot a "listen" so the student repeats.
    """
    q: deque[Substep] = deque()

    if coaching_line.strip():
        q.append(Substep("speak", text=coaching_line.strip()))

    lines = parsed_mantra.lines
    if not lines:
        return q

    # Single-line mantra with no per-line actions → just chant the whole thing.
    if len(lines) == 1 and lines[0].action is None:
        q.append(Substep("chant", text=lines[0].sanskrit, mantra_id=mantra_id, is_line=False))
        if call_and_response:
            q.append(Substep("listen", text=lines[0].sanskrit, mantra_id=mantra_id, is_line=False))
        return q

    # No per-line clips on disk → don't pretend to play them; play the whole
    # mantra once instead. Otherwise the chanter would fall back to the whole
    # wav N times, playing the same audio repeatedly.
    if not per_line_clips_available:
        full = "\n".join(ln.sanskrit for ln in lines)
        q.append(Substep("chant", text=full, mantra_id=mantra_id, is_line=False))
        if call_and_response:
            q.append(Substep("listen", text=full, mantra_id=mantra_id, is_line=False))
        return q

    for i, ln in enumerate(lines, start=1):
        if announce_per_line_actions and ln.action:
            q.append(Substep("speak", text=ln.action.strip().capitalize() + "."))
        q.append(Substep("chant", text=ln.sanskrit, mantra_id=mantra_id, is_line=True, line_index=i))
        if call_and_response:
            q.append(Substep("listen", text=ln.sanskrit, mantra_id=mantra_id, is_line=True, line_index=i))
    return q
