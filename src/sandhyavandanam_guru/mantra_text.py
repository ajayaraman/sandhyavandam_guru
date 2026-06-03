"""Parse mantra_text that interleaves Sanskrit with English action cues.

Some ritual mantras (e.g. gaayatree nyaasam) carry action cues in parentheses:

    saavitrya rushih vishvaamitraha   (touch head)
    niChrudgaayatree cChandaha        (touch upper lip)
    savitaa devataa                   (touch chest)

Feeding that raw to a Hindi/Sanskrit TTS makes the voice say "touch upper lip"
in Hindi, which is jarring. Split:
  - cleaned: just the chantable Sanskrit (no parentheticals)
  - actions: ordered list of the English cues, for the guru to announce in en-IN
"""
from __future__ import annotations

import re
from dataclasses import dataclass

_PAREN_RE = re.compile(r"\(([^)]*)\)")


@dataclass(frozen=True)
class MantraLine:
    sanskrit: str       # the chantable text for this line (no parens)
    action: str | None  # english action cue tied to this line, if any


@dataclass(frozen=True)
class ParsedMantra:
    cleaned: str        # mantra text with parentheticals stripped
    actions: list[str]  # ordered english cues, parens removed, whitespace cleaned
    lines: list[MantraLine]  # per-line (sanskrit, action) — drives the substep queue

    @property
    def action_preamble(self) -> str:
        """One short English sentence the guru can speak before the chant.

        Enumerates the gestures only when the list is short enough to follow
        as audio (≤3); past that, the on-screen action panel is the better
        reference and we just nudge the user to it.
        """
        if not self.actions:
            return ""
        if len(self.actions) == 1:
            return f"As I chant, {self.actions[0]}."
        if len(self.actions) <= 3:
            head, *rest = self.actions
            joined = ", then ".join(rest)
            return f"As I chant each line, {head}, then {joined}."
        return "Follow the gestures shown on screen as I chant each line."


def parse_mantra(text: str) -> ParsedMantra:
    actions: list[str] = []
    parsed_lines: list[MantraLine] = []
    cleaned_lines: list[str] = []
    for raw in (text or "").splitlines():
        paren_actions = [m.group(1).strip() for m in _PAREN_RE.finditer(raw) if m.group(1).strip()]
        no_parens = _PAREN_RE.sub("", raw)
        sanskrit = re.sub(r"\s+", " ", no_parens).strip()
        # drop pure-separator lines like "/" or "||"
        if not sanskrit:
            continue
        action = paren_actions[0] if paren_actions else None
        parsed_lines.append(MantraLine(sanskrit=sanskrit, action=action))
        cleaned_lines.append(sanskrit)
        actions.extend(paren_actions)
    return ParsedMantra(
        cleaned="\n".join(cleaned_lines),
        actions=actions,
        lines=parsed_lines,
    )
