# Phase 0.5 — Sanskrit STT shootout

Goal: empirically pick between Whisper-Sanskrit and Gemma 4 E4B audio for the
recitation-match listener, before we wire either one in.

## What you record

A curated 10-mantra set drawn from the ritual, balanced across lengths:

| Bucket | Mantras |
|---|---|
| short  | `m10_asavaadityo`, `m06_achyuta_short`, `m15_nyaasam` |
| medium | `m08_gayatri_arghya`, `m03_sankalpam`, `m22_harihara`, `m24_samarpanam`, `m26_rakshaa` |
| long   | `m05_praashanam_pratah`, `m18_mitrasya_pratah` |

You record each twice (20 clips total): once *clean*, once *with-error*. The
"with-error" clip is where you deliberately introduce a small mistake — drop an
aspirate (`ḥ` → silent), shorten a long vowel (`ā` → `a`), swap a retroflex with
a dental (`ṇ` → `n`), miss a visarga. Keep the rest correct. That gives us the
signal needed for **religious-error recall**: does each ASR actually flag the
mistake, or does it smooth it back into the "right" word?

## How to record

```bash
uv sync --extra dev --extra eval        # one-time
uv run python scripts/record_eval.py --variant clean
uv run python scripts/record_eval.py --variant with_error
```

The script:

- Loads the curated list and the corresponding step from the ritual YAML.
- For each clip, prints the mantra in front of you, then waits for `[Enter]` to start recording.
- Press `[Enter]` again to stop. The clip is saved to `eval/recordings/<mantra_id>_<variant>.wav` (16 kHz mono PCM).
- Writes `eval/recordings/manifest_<variant>.json` with paths, expected text, and durations.

If you mess up a clip, just re-run the script and answer `s`-kip until you reach
the one you want to redo, then record over it.

## What we do with the recordings

A scoring script (added when we wire the ASRs) will:

1. Run Whisper-Sanskrit and Gemma 4 E4B audio on each clip.
2. Normalise both transcripts and the expected text to IAST.
3. Compute, per model:
   - **CER** on the clean clips (lower = better at the easy job).
   - **Religious-error recall** = (number of with-error clips where the model's transcript actually differs from the clean transcript in a religiously-meaningful position) / 10. Higher = better at the *hard* job, which is what we actually need.
   - **Median latency** per clip.
4. Write `docs/stt_decision.md` with the table, the winner, and the default written into `src/sandhyavandanam_guru/config.py`.

## Skip the shootout?

If you don't want to record, the default stays Whisper-Sanskrit (the published
~15 % WER on Vāksañcayaḥ Vedic recitation), and we revisit after Phase 4 if its
quality is poor in practice.
