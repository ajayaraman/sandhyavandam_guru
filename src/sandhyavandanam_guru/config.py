from __future__ import annotations

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RITUAL_DIR = PROJECT_ROOT / "ritual"
ASSETS_DIR = PROJECT_ROOT / "assets"
MANTRA_DIR = ASSETS_DIR / "mantras"

USER_CONFIG_DIR = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "sandhyavandanam_guru"
USER_DATA_DIR = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share")) / "sandhyavandanam_guru"
SESSIONS_DIR = USER_DATA_DIR / "sessions"
IDENTITY_FILE = USER_CONFIG_DIR / "identity.yaml"

# Coach LLM + STT (Phase 0.5 shootout winner: Gemma 4 E4B via Ollama).
# Ollama is OpenAI-compatible at /v1. LM Studio rejected input_audio; Ollama accepts it.
OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434/v1")
COACH_MODEL = os.environ.get("SGR_COACH_MODEL", "gemma4:e4b")
STT_MODEL = os.environ.get("SGR_STT_MODEL", "gemma4:e4b")
# Gemma 4 audio hard limits (Google spec): 30 s per clip, 25 tokens/s, 16 kHz mono.
# Chunk recitation at line boundaries to stay <=25 s. Raise num_ctx for headroom.
STT_MAX_CLIP_S = 25.0
STT_NUM_CTX = 8192
STT_RETRY_ON_EMPTY = 1  # known intermittent GGML crash in Ollama #15333

# Fallback STT for short utterances ("next", barge-in) — MLX is sub-second on those.
WHISPER_FALLBACK_MODEL = os.environ.get("SGR_WHISPER_MODEL", "mlx-community/whisper-large-v3-mlx")

PIPER_VOICE_EN = os.environ.get("SGR_PIPER_VOICE_EN", "en_US-lessac-medium")

SIMILARITY_AUTO_ADVANCE = 0.85
SIMILARITY_NUDGE = 0.60
RECITATION_SILENCE_S = 1.4
DEFAULT_SILENCE_S = 0.5
LLM_TIMEOUT_S = 8.0
