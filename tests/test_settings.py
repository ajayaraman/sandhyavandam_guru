from __future__ import annotations

import textwrap
from pathlib import Path

import pytest
import yaml

from sandhyavandanam_guru import config
from sandhyavandanam_guru.settings import (
    DEFAULT_CONFIG_PATH,
    Settings,
    _deep_merge,
    load_settings,
)


def test_default_yaml_loads_and_validates() -> None:
    s = load_settings()
    assert isinstance(s, Settings)
    assert s.coach_llm.base_url.endswith("/v1")
    assert s.tts.backend in {"piper", "openvoice"}
    assert s.stt.max_clip_s <= 30.0  # Gemma audio architectural cap
    assert 0.0 < s.thresholds.similarity_nudge < s.thresholds.similarity_auto_advance <= 1.0


def test_default_paths_point_to_repo_files() -> None:
    s = load_settings()
    assert s.ritual_path().exists()
    assert s.coaching_path().exists()


def test_extra_overlay_deep_merges(tmp_path: Path) -> None:
    overlay = tmp_path / "overlay.yaml"
    overlay.write_text(
        textwrap.dedent(
            """
            tts:
              backend: piper
              openvoice:
                language: EN_US
            stt:
              num_ctx: 12288
            """
        )
    )
    base = load_settings()
    over = load_settings(overlay)
    # Overridden fields change
    assert over.tts.backend == "piper"
    assert over.tts.openvoice.language == "EN_US"
    assert over.stt.num_ctx == 12288
    # Untouched fields preserved from default
    assert over.coach_llm.model == base.coach_llm.model
    assert over.tts.piper.voice == base.tts.piper.voice


def test_unknown_fields_are_rejected(tmp_path: Path) -> None:
    overlay = tmp_path / "bad.yaml"
    overlay.write_text("tts:\n  backend: piper\n  whatever: x\n")
    with pytest.raises(Exception):
        load_settings(overlay)


def test_threshold_bounds_enforced(tmp_path: Path) -> None:
    overlay = tmp_path / "bad.yaml"
    overlay.write_text("thresholds:\n  similarity_auto_advance: 1.5\n")
    with pytest.raises(Exception):
        load_settings(overlay)


def test_max_clip_s_cap_enforced(tmp_path: Path) -> None:
    """Anyone bumping max_clip_s above 30 s would silently lose long mantras."""
    overlay = tmp_path / "bad.yaml"
    overlay.write_text("stt:\n  max_clip_s: 45\n")
    with pytest.raises(Exception):
        load_settings(overlay)


def test_default_yaml_is_pristine_at_repo_root() -> None:
    """Make sure no one accidentally removes the shipped default."""
    assert DEFAULT_CONFIG_PATH == config.CONFIG_DIR / "default.yaml"
    assert DEFAULT_CONFIG_PATH.exists()
    data = yaml.safe_load(DEFAULT_CONFIG_PATH.read_text())
    # The five top-level sections are the contract with the schema.
    assert set(data) == {"ritual", "coach_llm", "stt", "tts", "thresholds"}


def test_deep_merge_only_recurses_into_dicts() -> None:
    base = {"a": {"x": 1, "y": 2}, "b": [1, 2]}
    over = {"a": {"y": 99, "z": 3}, "b": [9]}
    out = _deep_merge(base, over)
    assert out == {"a": {"x": 1, "y": 99, "z": 3}, "b": [9]}
