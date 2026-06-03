from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from sandhyavandanam_guru import config
from sandhyavandanam_guru.identity import (
    Identity,
    identity_search_paths,
    load_identity,
)


VALID_YAML = textwrap.dedent(
    """
    name: krishna
    gotra: bharadwaaja
    pravara:
      - bhaaradwaaja
      - aangirasa
      - baarhaspatya
    sutra: aashvalaayana
    veda: rigveda
    veda_shaakha: shaakala
    """
)


def test_load_identity_returns_none_when_no_file(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(config, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(config, "USER_CONFIG_DIR", tmp_path / "userconfig")
    assert load_identity() is None


def test_load_identity_from_explicit_path(tmp_path: Path) -> None:
    p = tmp_path / "id.yaml"
    p.write_text(VALID_YAML)
    ident = load_identity(p)
    assert ident is not None
    assert ident.name == "krishna"
    assert ident.gotra == "bharadwaaja"
    assert ident.pravara == ["bhaaradwaaja", "aangirasa", "baarhaspatya"]
    assert ident.veda == "rigveda"


def test_load_identity_prefers_repo_root_over_user_config(tmp_path: Path, monkeypatch) -> None:
    project = tmp_path / "project"
    user = tmp_path / "user"
    project.mkdir()
    user.mkdir()
    monkeypatch.setattr(config, "PROJECT_ROOT", project)
    monkeypatch.setattr(config, "USER_CONFIG_DIR", user)

    (project / "identity.yaml").write_text(VALID_YAML)
    other = VALID_YAML.replace("krishna", "OTHER")
    (user / "identity.yaml").write_text(other)

    ident = load_identity()
    assert ident is not None and ident.name == "krishna"


def test_load_identity_falls_back_to_user_config(tmp_path: Path, monkeypatch) -> None:
    project = tmp_path / "project"
    user = tmp_path / "user"
    project.mkdir()
    user.mkdir()
    monkeypatch.setattr(config, "PROJECT_ROOT", project)
    monkeypatch.setattr(config, "USER_CONFIG_DIR", user)
    (user / "identity.yaml").write_text(VALID_YAML)

    ident = load_identity()
    assert ident is not None and ident.gotra == "bharadwaaja"


def test_invalid_veda_rejected(tmp_path: Path) -> None:
    p = tmp_path / "id.yaml"
    p.write_text(VALID_YAML.replace("rigveda", "MADE_UP_VEDA"))
    with pytest.raises(Exception):
        load_identity(p)


def test_missing_required_field_rejected(tmp_path: Path) -> None:
    p = tmp_path / "id.yaml"
    p.write_text(VALID_YAML.replace("gotra: bharadwaaja\n", ""))
    with pytest.raises(Exception):
        load_identity(p)


def test_pravara_must_have_at_least_one(tmp_path: Path) -> None:
    p = tmp_path / "id.yaml"
    p.write_text(
        textwrap.dedent(
            """
            name: krishna
            gotra: bharadwaaja
            pravara: []
            sutra: aashvalaayana
            veda: rigveda
            veda_shaakha: shaakala
            """
        )
    )
    with pytest.raises(Exception):
        load_identity(p)


def test_pravara_max_length_enforced(tmp_path: Path) -> None:
    p = tmp_path / "id.yaml"
    overlong = "\n".join(f"  - rishi{i}" for i in range(6))
    p.write_text(
        textwrap.dedent(
            f"""
            name: krishna
            gotra: bharadwaaja
            pravara:
            {overlong}
            sutra: aashvalaayana
            veda: rigveda
            veda_shaakha: shaakala
            """
        )
    )
    with pytest.raises(Exception):
        load_identity(p)


def test_unknown_field_rejected(tmp_path: Path) -> None:
    p = tmp_path / "id.yaml"
    p.write_text(VALID_YAML + "\nfavorite_color: saffron\n")
    with pytest.raises(Exception):
        load_identity(p)


def test_search_path_order_with_explicit(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(config, "PROJECT_ROOT", tmp_path / "p")
    monkeypatch.setattr(config, "USER_CONFIG_DIR", tmp_path / "u")
    explicit = tmp_path / "explicit.yaml"
    paths = identity_search_paths(explicit)
    assert paths[0] == explicit
    assert paths[1] == tmp_path / "p" / "identity.yaml"
    assert paths[2] == tmp_path / "u" / "identity.yaml"


def test_identity_model_round_trip() -> None:
    data = {
        "name": "raama",
        "gotra": "kaashyapa",
        "pravara": ["kaashyapa"],
        "sutra": "aashvalaayana",
        "veda": "rigveda",
        "veda_shaakha": "shaakala",
    }
    ident = Identity.model_validate(data)
    assert ident.model_dump() == data
