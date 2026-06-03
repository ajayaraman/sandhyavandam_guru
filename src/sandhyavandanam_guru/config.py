"""Filesystem path constants only. Tunable settings live in config/default.yaml."""
from __future__ import annotations

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RITUAL_DIR = PROJECT_ROOT / "ritual"
ASSETS_DIR = PROJECT_ROOT / "assets"
MANTRA_DIR = ASSETS_DIR / "mantras"
CONFIG_DIR = PROJECT_ROOT / "config"

USER_CONFIG_DIR = (
    Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    / "sandhyavandanam_guru"
)
USER_DATA_DIR = (
    Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share"))
    / "sandhyavandanam_guru"
)
SESSIONS_DIR = USER_DATA_DIR / "sessions"
IDENTITY_FILE = USER_CONFIG_DIR / "identity.yaml"
