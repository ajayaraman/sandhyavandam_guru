# Sandhyavandanam Guru

A terminal coach that walks an initiate through the Rigveda Pratah (morning) Sandhyavandanam,
end-to-end, using the canonical 26 actions from the `bharatiweb.com` v1 PDF.

See `plan.md` for the full design (architecture, model stack, phased delivery).

## Phase 1 (this commit)

What works today is the **silent study-aid TUI**:

- The 26 steps with mantra text, posture, action, and English meaning, encoded in
  `ritual/pratah_rigveda.yaml` as a single source of truth.
- A Textual TUI to walk through them with arrow keys.
- A typed loader + tests.
- A doctor script.

Audio (Piper TTS for the coach, Whisper for listening), the LM Studio coach LLM, and the
mantra audio bank land in later phases — see `plan.md`.

## Install

This project uses [uv](https://docs.astral.sh/uv/). From the project root:

```bash
uv sync --extra dev
```

Add the audio extras (not used in Phase 1) when you reach Phase 2+:

```bash
uv sync --extra dev --extra audio
```

## Run

List the 26 steps without launching the TUI:

```bash
uv run sgr --dry-run
```

Launch the interactive TUI:

```bash
uv run sgr
```

Keys: `→` / `space` / `n` next, `←` / `p` previous, `Home` first, `End` last, `q` quit.

## Test

```bash
uv run pytest -q
```

## Doctor

```bash
uv run python scripts/doctor.py
```

## Phase 0.5 — record the STT eval set

To pick between Whisper-Sanskrit and Gemma 4 E4B audio empirically, record yourself
saying 10 curated mantras, twice (clean + with deliberate small errors). See
`docs/phase_0_5_shootout.md` for the full flow.

```bash
uv sync --extra dev --extra eval
uv run python scripts/record_eval.py --variant clean
uv run python scripts/record_eval.py --variant with_error
```

Recordings land in `eval/recordings/` (gitignored).

Reports on Python version, ritual YAML, LM Studio availability (optional), and the
mantra audio bank (optional, used by later phases).

## Layout

```
sandhyavandanam_guru/
├── plan.md                         # design and phased delivery
├── ritual/pratah_rigveda.yaml      # the 26 actions, canonical
├── src/sandhyavandanam_guru/       # package
│   ├── ritual_loader.py            # YAML → typed Step / Ritual
│   ├── tui.py                      # Textual app
│   ├── cli.py                      # `sgr` entrypoint
│   └── config.py                   # paths, model IDs, thresholds
├── scripts/doctor.py
└── tests/
```

## Mantra audio (later phases)

When the audio bank is built, `.wav` files live in `assets/mantras/<mantra_id>.wav`.
That directory is gitignored: you can drop in a priest's recording with the
matching `mantra_id` filename to override the default Svara-TTS-generated clip.
