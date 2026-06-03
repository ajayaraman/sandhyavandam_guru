"""Typed loader for the user's personal lineage (step 19 abhivadanam).

Resolution order (first that exists wins):
  1. explicit path passed to load_identity()
  2. ./identity.yaml at the project root (gitignored)
  3. ~/.config/sandhyavandanam_guru/identity.yaml

Step 19 needs gotra / pravara / sutra / veda / name. Until the user fills this
in, the coach will show a placeholder and ask them to set it up.
"""
from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field

from . import config


class Identity(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1)
    gotra: str = Field(min_length=1)
    pravara: list[str] = Field(min_length=1, max_length=5)
    sutra: str = Field(min_length=1)
    veda: Literal["rigveda", "yajurveda", "saamaveda", "atharvaveda"]
    veda_shaakha: str = Field(min_length=1)


def identity_search_paths(explicit: Path | None = None) -> list[Path]:
    paths: list[Path] = []
    if explicit:
        paths.append(Path(explicit))
    paths.append(config.PROJECT_ROOT / "identity.yaml")
    paths.append(config.USER_CONFIG_DIR / "identity.yaml")
    return paths


def load_identity(explicit: Path | None = None) -> Identity | None:
    """Return the user's Identity, or None if no identity file exists yet."""
    for p in identity_search_paths(explicit):
        if p.exists():
            data = yaml.safe_load(p.read_text())
            return Identity.model_validate(data)
    return None
