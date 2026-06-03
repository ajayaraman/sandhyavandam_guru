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

Requires [uv](https://docs.astral.sh/uv/) and macOS / Linux. Pick the tier you want:

### Tier 1 — silent study aid + full unit tests (turn-key)

```bash
git clone https://github.com/ajayaraman/sandhyavandam_guru.git
cd sandhyavandam_guru
uv sync --extra dev
uv run pytest -q          # 95 passed, 30 skipped in <5 s
uv run sgr --no-audio     # the TUI, silent
```

No system deps, no model downloads, no network. Tier 1 is enough to read along.

### Tier 2 — Piper guru voice

```bash
uv sync --extra dev --extra audio
uv run sgr                # Piper synth, first launch downloads a ~60 MB voice
```

### Tier 3 — OpenVoice timbre clone (your own voice as the guru)

```bash
brew install mecab        # macOS (Debian/Ubuntu: sudo apt install mecab libmecab-dev)
uv sync --extra dev --extra audio --extra clone
uv run python scripts/fetch_openvoice.py       # one-time ~1.5 GB download
uv run sgr --voice openvoice
```

Tiers compose: `--extra dev --extra audio --extra clone` gives you everything.

### Quick chooser

| You want… | Run |
|---|---|
| Try the TUI now | `uv sync --extra dev && uv run sgr --no-audio` |
| Hear a generic guru voice | Tier 2 |
| Hear *your* voice as the guru | Tier 3 |
| Run the full integration tests | Tier 3 + `SGR_INTEGRATION=1` |

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

### Unit suite (default — fast, no audio hardware)

```bash
uv run pytest -q
```

~95 tests in under 5 seconds. Heavy deps (`sounddevice`, `piper`, `openvoice`, `melo`,
`torch`) are stubbed via `sys.modules` so the suite runs without a sound card,
model checkpoints, or network. Audio-integration tests (below) skip automatically
unless `SGR_INTEGRATION=1` is set.

Coverage:

- `test_ritual_loader.py` / `test_coaching_loader.py` — YAML schema, 26-step
  coverage, terseness limits.
- `test_settings.py` — default validates, deep-merge, unknown-field rejection,
  bounds on thresholds and `max_clip_s`.
- `test_identity.py` — search-path order, enum + length validation.
- `test_player.py` / `test_voices.py` — sounddevice stub, lock serialisation,
  Piper voice cache idempotency.
- `test_tts_piper.py` / `test_tts_openvoice.py` — synth/play/stop API with
  mocked engines, double-checked load lock, blank-text no-op, graceful failure.
- `test_cli.py` — `_resolve_clone_ref`, `--no-audio` short-circuit, argparse
  overrides reach the TUI.
- `test_tui_render.py` — palette hex/distinctness, status frame cycling,
  sanskrit/english block colours + content.
- `test_tui_app.py` — drives `GuruApp` through Textual's `App.run_test()`
  pilot. Real key events through bindings, rendered widget content read via
  `rich.Console.capture()`. Covers navigation, replay, silence, status-bar
  reactivity (loading / speaking / idle), graceful degradation when
  `speaker=None` or `coaching=None`.

### Audio integration suite (opt-in — real audio, no mocks)

```bash
SGR_INTEGRATION=1 uv run pytest tests/test_audio_integration.py -q
```

These tests load the real Piper and OpenVoice models and capture the PCM that
would have gone to the speaker (via a fake `sounddevice` that records calls
into a numpy buffer). The assertions check that the audio actually exists —
non-zero length, RMS above silence floor, dynamic range — so silent regressions
like the `wave.Error` / missing-`soundfile` ones during Phase 2 would fail loudly.

Coverage:

- `test_piper_synthesize_produces_real_audio` — real Piper synth, asserts the
  PCM is at 22.05 kHz, ≥1 s long, with speech-like RMS.
- `test_piper_say_round_trip_through_app` — drives `PiperSpeaker.say()` and
  asserts audio reached the (intercepted) player.
- `test_openvoice_synthesize_produces_real_audio_in_user_timbre` — real
  OpenVoice synth using one of your `eval/recordings/` clean clips as the
  tone-color reference.
- `test_openvoice_state_transitions_through_loading_then_speaking` —
  asserts the speaker actually reports `state() == "loading"` during warmup
  before flipping to `"speaking"`.
- `test_eval_recording_meets_spt_spec` (parametrised over every
  `*_clean.wav`) — verifies each recording is 16 kHz mono PCM-16 with ≥3 s
  of content, so the Phase 4 STT pipeline can consume them straight.
- `test_eval_recording_has_audible_content` — RMS floor check per clip.
- Phase 4 placeholders (skipped): feed `eval/recordings/<id>_clean.wav` and
  `<id>_with_error.wav` into the recitation-match advance rule.

First OpenVoice run downloads ~1.5 GB of checkpoints; pre-warm with
`uv run python scripts/fetch_openvoice.py` to keep the test fast.

### Run just one suite

```bash
uv run pytest tests/test_tui_app.py -q          # TUI integration only
uv run pytest tests/test_settings.py -q         # config schema only
uv run pytest -k tts -q                         # everything matching "tts"
```

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
