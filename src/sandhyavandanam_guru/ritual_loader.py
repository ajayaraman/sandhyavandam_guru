from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field

AdvanceRule = Literal["auto", "user_confirm", "recitation_match"]


class Step(BaseModel):
    id: str
    name_sa: str
    name_en: str
    posture: str
    physical_action: str
    mantra_id: str
    mantra_text: str
    translation: str
    repeat_count: int = 1
    advance_rule: AdvanceRule = "user_confirm"


class Ritual(BaseModel):
    sandhya_kind: str
    steps: list[Step] = Field(min_length=1)

    def step_by_id(self, step_id: str) -> Step:
        for s in self.steps:
            if s.id == step_id:
                return s
        raise KeyError(step_id)


def load_ritual(path: str | Path) -> Ritual:
    raw = yaml.safe_load(Path(path).read_text())
    return Ritual.model_validate(raw)
