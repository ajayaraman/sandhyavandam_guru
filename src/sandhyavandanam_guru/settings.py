"""Typed settings loader: default.yaml + optional user/CLI override, validated by Pydantic.

Anything tunable lives in the YAML. config.py is reserved for filesystem path
constants — directories that the code needs to *find*, not knobs the user
might want to *change*.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field

from . import config as _paths


class RitualPaths(BaseModel):
    model_config = ConfigDict(extra="forbid")
    pratah: str
    coaching_en: str


class CoachLLMSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")
    base_url: str
    model: str
    timeout_s: float = Field(gt=0)


class STTSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")
    primary_model: str
    fallback_whisper: str
    max_clip_s: float = Field(gt=0, le=30.0)
    num_ctx: int = Field(ge=512)
    retry_on_empty: int = Field(ge=0, le=5)


class PiperSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")
    voice: str


class OpenVoiceSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")
    language: Literal["EN_INDIA", "EN_US", "EN_BR", "EN_AU", "EN_Default"] = "EN_INDIA"
    clone_ref: str | None = None


class MeloTTSSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")
    language: Literal["EN_INDIA", "EN_US", "EN_BR", "EN_AU", "EN_Default"] = "EN_Default"
    speed: float = Field(gt=0.3, le=2.0, default=1.0)


class TTSSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")
    backend: Literal["piper", "openvoice", "melotts"]
    piper: PiperSettings
    openvoice: OpenVoiceSettings
    melotts: MeloTTSSettings = MeloTTSSettings()


class Thresholds(BaseModel):
    model_config = ConfigDict(extra="forbid")
    similarity_auto_advance: float = Field(ge=0.0, le=1.0)
    similarity_nudge: float = Field(ge=0.0, le=1.0)
    recitation_silence_s: float = Field(gt=0)
    default_silence_s: float = Field(gt=0)


class Settings(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ritual: RitualPaths
    coach_llm: CoachLLMSettings
    stt: STTSettings
    tts: TTSSettings
    thresholds: Thresholds

    def ritual_path(self) -> Path:
        return _paths.PROJECT_ROOT / self.ritual.pratah

    def coaching_path(self) -> Path:
        return _paths.PROJECT_ROOT / self.ritual.coaching_en


DEFAULT_CONFIG_PATH = _paths.PROJECT_ROOT / "config" / "default.yaml"
USER_CONFIG_PATH = _paths.USER_CONFIG_DIR / "config.yaml"


def _deep_merge(base: dict, override: dict) -> dict:
    out = dict(base)
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def load_settings(extra_path: Path | None = None) -> Settings:
    """Load default.yaml, deep-merge user config (if present), then extra_path (if given)."""
    data: dict[str, Any] = yaml.safe_load(DEFAULT_CONFIG_PATH.read_text())
    if USER_CONFIG_PATH.exists():
        data = _deep_merge(data, yaml.safe_load(USER_CONFIG_PATH.read_text()) or {})
    if extra_path is not None:
        data = _deep_merge(data, yaml.safe_load(Path(extra_path).read_text()) or {})
    return Settings.model_validate(data)
