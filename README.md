# Sandhyavandanam Guru

A terminal coach that walks an initiate through the Rigveda Pratah (morning) Sandhyavandanam,
end-to-end, using the canonical 26 actions from the `bharatiweb.com` v1 PDF.

See `plan.md` for the full design (architecture, model stack, phased delivery).

## What's in today

- The 26 ritual steps with mantra, posture, action, and translation, encoded in
  `ritual/pratah_rigveda.yaml`.
- Textual TUI with side-by-side Sanskrit/English panels, a live "guru is speaking"
  status bar, and spiritual colours (saffron for the mantra, kumkum for the action,
  tulsi for posture, gold for the deity-name).
- A guru voice with two backends:
  - **Piper** — small generic English voice, no setup.
  - **OpenVoice v2** — clones your timbre from a short reference clip and renders
    English (Indian) via MeloTTS. Your existing Sanskrit recordings in
    `eval/recordings/` work as the reference; OpenVoice clones timbre only.
- Phase 0.5 STT shootout: Gemma 4 E4B (via Ollama) won over MLX Whisper on
  religious-error recall (1.00 vs 0.80) and CER. See `docs/stt_decision_mlx.md`.

## Install

Requires [uv](https://docs.astral.sh/uv/) and macOS / Linux. From the project root:

```bash
uv sync --extra dev                              # Phase 1 study-aid TUI only
uv sync --extra dev --extra audio                # + Piper guru voice
uv sync --extra dev --extra audio --extra clone  # + OpenVoice timbre clone
```

The clone extras pull MeloTTS, which needs MeCab installed at the system level:

```bash
brew install mecab            # macOS
# sudo apt install mecab libmecab-dev     # Debian/Ubuntu
```

## Configuration

All knobs live in YAML, validated by Pydantic at startup.

```
config/default.yaml                              shipped defaults (read first)
~/.config/sandhyavandanam_guru/config.yaml       optional user overrides (deep-merged)
sgr --config path/to/override.yaml               optional extra overlay
```

The default is the right starting point. Override only what you want to change — partial
files are fine. Schema in `src/sandhyavandanam_guru/settings.py`. Run `sgr` once after editing
to see Pydantic validate every field.

Common knobs:

```yaml
tts:
  backend: openvoice          # piper | openvoice
  openvoice:
    language: EN_INDIA        # EN_INDIA | EN_US | EN_BR | EN_AU | EN_DEFAULT
    clone_ref: null           # path to ref wav; null = auto-pick from eval/recordings
coach_llm:
  base_url: http://localhost:11434/v1
  model: gemma4:e4b
```

## Personal lineage — `identity.yaml`

Step 19 (`samaṣṭi abhivādanam`) asks you to declare your gotra, pravara, sūtra, veda,
and śarman name. This is personal and should never be committed.

```bash
cp identity.example.yaml identity.yaml
$EDITOR identity.yaml
```

`identity.yaml` is gitignored. The app looks for it in:

1. `./identity.yaml` (this repo root) — recommended for a personal install.
2. `~/.config/sandhyavandanam_guru/identity.yaml` — for system-wide.

Until you fill it in, step 19 shows a placeholder.

## Run

```bash
uv run sgr --dry-run                            # list the 26 steps and exit
uv run sgr                                      # full TUI with guru voice
uv run sgr --no-audio                           # silent study-aid mode
uv run sgr --voice openvoice                    # force the cloned voice
uv run sgr --voice openvoice --clone-ref eval/recordings/m08_gayatri_arghya_clean.wav
```

First launch of `--voice openvoice` downloads ~500 MB of OpenVoice + MeloTTS
checkpoints into `~/.cache/sandhyavandanam_guru/openvoice_v2/`. Subsequent runs
are warm.

### Keys

| Key | Action |
|---|---|
| `→` / `space` / `n` | next step (speaks new coaching line) |
| `←` / `p` | previous step |
| `Home` / `End` | first / last step |
| `r` | replay current coaching line |
| `s` | silence (cancel TTS mid-clip) |
| `q` | quit |

## Test

```bash
uv run pytest -q
```

Tests cover the ritual loader, the coaching loader, and the settings schema (default
file validates, deep-merge works, unknown fields rejected, threshold/duration bounds
enforced).

## Doctor

```bash
uv run python scripts/doctor.py
```

Reports on Python version, ritual YAML presence, settings YAML validity, coach LLM
reachability (Ollama at `http://localhost:11434/v1` by default), `ollama` CLI on PATH,
and the mantra audio bank.

## Phase 0.5 — Sanskrit STT shootout

To re-run or extend the shootout:

```bash
uv sync --extra dev --extra eval
uv run python scripts/record_eval.py --variant clean
uv run python scripts/record_eval.py --variant with_error
uv run python scripts/score_eval.py --backend mlx --gemma-model gemma4:e4b \
    --gemma-base-url http://localhost:11434/v1
```

Recordings land in `eval/recordings/` (gitignored). The decision report is written
to `docs/stt_decision_{backend}.md`. See `docs/phase_0_5_shootout.md` for the
methodology.

## Layout

```
sandhyavandanam_guru/
├── plan.md                            # design and phased delivery
├── config/default.yaml                # shipped settings (validated by settings.py)
├── identity.example.yaml              # template for personal lineage
├── ritual/
│   ├── pratah_rigveda.yaml            # the 26 actions, canonical
│   └── coaching_en.yaml               # English guru lines per step
├── src/sandhyavandanam_guru/
│   ├── config.py                      # filesystem path constants only
│   ├── settings.py                    # Pydantic schema for YAML config
│   ├── identity.py                    # typed loader for identity.yaml
│   ├── ritual_loader.py
│   ├── coaching_loader.py
│   ├── tui.py                         # Textual app
│   ├── cli.py                         # `sgr` entrypoint
│   └── audio/
│       ├── player.py                  # cancellable sounddevice wrapper
│       ├── tts_piper.py               # Piper backend
│       └── tts_openvoice.py           # OpenVoice v2 backend
├── scripts/
│   ├── doctor.py
│   ├── record_eval.py
│   └── score_eval.py
└── tests/
```

## Mantra audio (Phase 3)

When the audio bank is built, `.wav` files live in `assets/mantras/<mantra_id>.wav`
(gitignored). You can drop in a priest's recording with the matching filename to
override the generated clip.
