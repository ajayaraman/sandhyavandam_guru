from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel


class Coaching(BaseModel):
    lines: dict[str, str]

    def for_step(self, step_id: str) -> str:
        return (self.lines.get(step_id) or "").strip()


def load_coaching(path: str | Path) -> Coaching:
    raw = yaml.safe_load(Path(path).read_text())
    return Coaching.model_validate(raw)
