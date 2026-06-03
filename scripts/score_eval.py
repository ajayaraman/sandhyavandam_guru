"""Phase 0.5 — score recorded eval clips with each candidate STT.

Runs (1) faster-whisper on every clip with Sanskrit language hint + expected
mantra as initial_prompt, and (2) Gemma 4 E4B audio served by LM Studio via its
OpenAI-compatible chat-completions endpoint (audio attachment).

For each model we compute:
  - CER on the clean clips (lower = better at the easy job).
  - Religious-error recall: fraction of (clean, with_error) pairs where the
    model's two transcripts actually differ (i.e. the model noticed the
    deliberate mispronunciation).
  - Median per-clip latency.

Writes a markdown report at docs/stt_decision.md and picks a winner.

Usage:
    uv sync --extra dev --extra eval --extra shootout
    uv run python scripts/score_eval.py
    uv run python scripts/score_eval.py --skip-gemma      # whisper only
    uv run python scripts/score_eval.py --skip-whisper    # gemma only
"""

from __future__ import annotations

import argparse
import base64
import json
import re
import sys
import time
import unicodedata
from pathlib import Path

from sandhyavandanam_guru import config


# ---------- normalisation + scoring ----------

_DEV_RANGE = (0x0900, 0x097F)


def _has_devanagari(s: str) -> bool:
    return any(_DEV_RANGE[0] <= ord(c) <= _DEV_RANGE[1] for c in s)


def _to_iast(s: str) -> str:
    if not _has_devanagari(s):
        return s
    from indic_transliteration import sanscript
    from indic_transliteration.sanscript import transliterate
    return transliterate(s, sanscript.DEVANAGARI, sanscript.IAST)


def normalize(text: str) -> str:
    """Phonemic-ish normalization so we can compare Whisper's Devanagari or
    diacritical-IAST output against the YAML's home-spun romanization.

    - Devanagari -> IAST
    - Strip diacritics (ā -> a, ṛ -> r, ṣ -> s, ṇ -> n …)
    - Lowercase, strip parentheticals + punctuation
    - Collapse doubled vowels (`aa` -> `a`, `ee` -> `e`) so 'aa'/'ā' match
    """
    t = _to_iast(text)
    t = unicodedata.normalize("NFD", t)
    t = "".join(c for c in t if not unicodedata.combining(c))
    t = t.lower()
    t = re.sub(r"\([^)]*\)", " ", t)
    t = re.sub(r"[|]+", " ", t)
    t = re.sub(r"[^a-z\s]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    t = re.sub(r"([aeiou])\1+", r"\1", t)
    return t


def cer(ref: str, hyp: str) -> float:
    """Character error rate via Levenshtein."""
    ref, hyp = ref.strip(), hyp.strip()
    if not ref:
        return 1.0 if hyp else 0.0
    n, m = len(ref), len(hyp)
    dp = list(range(m + 1))
    for i in range(1, n + 1):
        prev, dp[0] = dp[0], i
        for j in range(1, m + 1):
            cur = dp[j]
            if ref[i - 1] == hyp[j - 1]:
                dp[j] = prev
            else:
                dp[j] = 1 + min(prev, dp[j - 1], dp[j])
            prev = cur
    return dp[m] / n


def median(xs: list[float]) -> float:
    if not xs:
        return float("nan")
    s = sorted(xs)
    return s[len(s) // 2]


# ---------- backends ----------

class WhisperBackend:
    """Common interface around faster-whisper (CPU) and mlx-whisper (Metal)."""

    def __init__(self, kind: str, model_id: str):
        self.kind = kind
        self.model_id = model_id
        if kind == "faster":
            from faster_whisper import WhisperModel
            self._model = WhisperModel(model_id, device="auto", compute_type="auto")
        elif kind == "mlx":
            import mlx_whisper  # noqa: F401  — imported eagerly to fail fast
            self._model = None  # mlx_whisper is functional; no persistent model object
        else:
            raise ValueError(f"unknown whisper backend: {kind}")

    def transcribe(self, wav_path: str, initial_prompt: str) -> str:
        if self.kind == "faster":
            segments, _ = self._model.transcribe(
                wav_path,
                language="sa",
                initial_prompt=initial_prompt,
                beam_size=5,
                vad_filter=False,
            )
            return "".join(s.text for s in segments)
        # mlx
        import mlx_whisper
        result = mlx_whisper.transcribe(
            wav_path,
            path_or_hf_repo=self.model_id,
            language="sa",
            initial_prompt=initial_prompt,
            fp16=True,
        )
        return result.get("text", "")


def run_whisper(backend: WhisperBackend, wav_path: str, expected_text: str) -> tuple[str, float]:
    t0 = time.time()
    text = backend.transcribe(wav_path, expected_text)
    return text, time.time() - t0


def run_gemma_lmstudio(client, model_name: str, wav_path: str) -> tuple[str, float]:
    audio_b64 = base64.b64encode(Path(wav_path).read_bytes()).decode()
    t0 = time.time()
    resp = client.chat.completions.create(
        model=model_name,
        messages=[{
            "role": "user",
            "content": [
                {"type": "text", "text":
                    "Transcribe this Sanskrit chant verbatim in roman transliteration. "
                    "Output only the transcription, no commentary."},
                {"type": "input_audio", "input_audio": {"data": audio_b64, "format": "wav"}},
            ],
        }],
        temperature=0,
        max_tokens=512,
    )
    return resp.choices[0].message.content or "", time.time() - t0


# ---------- main ----------

def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--backend", choices=["faster", "mlx"], default="faster",
                   help="Whisper backend: 'faster' (CPU, faster-whisper) or 'mlx' (Metal, Apple Silicon).")
    p.add_argument("--whisper-model", default=None,
                   help="Whisper model id. Defaults: 'large-v3' for faster, "
                        "'mlx-community/whisper-large-v3-mlx' for mlx.")
    p.add_argument("--gemma-model", default=None,
                   help="Gemma model id served by LM Studio or Ollama "
                        "(default: from config.LM_STUDIO_MODEL).")
    p.add_argument("--gemma-base-url", default=None,
                   help="Override OpenAI-compatible base URL for the Gemma server. "
                        "LM Studio: http://localhost:1234/v1 (default). "
                        "Ollama: http://localhost:11434/v1.")
    p.add_argument("--skip-whisper", action="store_true")
    p.add_argument("--skip-gemma", action="store_true")
    p.add_argument("--out", default=None,
                   help="Report path. Defaults to docs/stt_decision_<backend>.md.")
    args = p.parse_args()

    whisper_model_id = args.whisper_model or (
        "mlx-community/whisper-large-v3-mlx" if args.backend == "mlx" else "large-v3"
    )
    out_rel = args.out or f"docs/stt_decision_{args.backend}.md"

    eval_dir = config.PROJECT_ROOT / "eval" / "recordings"
    clean = json.loads((eval_dir / "manifest_clean.json").read_text())
    werr = json.loads((eval_dir / "manifest_with_error.json").read_text())

    by_id: dict[str, dict] = {}
    for m in clean:
        by_id.setdefault(m["mantra_id"], {})["clean"] = m
    for m in werr:
        by_id.setdefault(m["mantra_id"], {})["with_error"] = m

    whisper_backend = None
    if not args.skip_whisper:
        print(f"Loading whisper backend='{args.backend}' model='{whisper_model_id}' (first run downloads ~3 GB)...")
        whisper_backend = WhisperBackend(args.backend, whisper_model_id)

    gemma_client = None
    gemma_model_name = args.gemma_model or config.LM_STUDIO_MODEL
    gemma_base_url = args.gemma_base_url or config.LM_STUDIO_BASE_URL
    if not args.skip_gemma:
        print(f"Connecting to Gemma server at {gemma_base_url} (model: {gemma_model_name})...")
        from openai import OpenAI
        gemma_client = OpenAI(base_url=gemma_base_url, api_key="not-used")

    rows = []
    total = len(by_id)
    for i, (mid, variants) in enumerate(by_id.items(), 1):
        c = variants.get("clean")
        w = variants.get("with_error")
        if not c:
            continue
        expected_norm = normalize(c["expected_text"])
        c_path = str(config.PROJECT_ROOT / c["path"])
        w_path = str(config.PROJECT_ROOT / w["path"]) if w else None

        row: dict = {
            "mantra_id": mid,
            "length": c["length_bucket"],
            "duration_s": c["duration_s"],
            "expected": expected_norm,
        }
        print(f"[{i}/{total}] {mid}  ({c['length_bucket']}, {c['duration_s']}s)")

        if whisper_backend:
            wt_c, wt_c_lat = run_whisper(whisper_backend, c_path, c["expected_text"])
            wt_c_n = normalize(wt_c)
            row["whisper_clean"] = wt_c_n
            row["whisper_clean_cer"] = cer(expected_norm, wt_c_n)
            row["whisper_clean_lat_s"] = wt_c_lat
            print(f"   whisper clean  CER={row['whisper_clean_cer']:.3f}  {wt_c_lat:.1f}s")
            if w_path:
                wt_w, _ = run_whisper(whisper_backend, w_path, c["expected_text"])
                wt_w_n = normalize(wt_w)
                row["whisper_werr"] = wt_w_n
                row["whisper_detected_error"] = wt_w_n != wt_c_n

        if gemma_client:
            try:
                gt_c, gt_c_lat = run_gemma_lmstudio(gemma_client, gemma_model_name, c_path)
                gt_c_n = normalize(gt_c)
                row["gemma_clean"] = gt_c_n
                row["gemma_clean_cer"] = cer(expected_norm, gt_c_n)
                row["gemma_clean_lat_s"] = gt_c_lat
                print(f"   gemma   clean  CER={row['gemma_clean_cer']:.3f}  {gt_c_lat:.1f}s")
                if w_path:
                    gt_w, _ = run_gemma_lmstudio(gemma_client, gemma_model_name, w_path)
                    gt_w_n = normalize(gt_w)
                    row["gemma_werr"] = gt_w_n
                    row["gemma_detected_error"] = gt_w_n != gt_c_n
            except Exception as e:
                row["gemma_error"] = str(e)
                print(f"   gemma   ERROR: {e}")

        rows.append(row)

    out_path = config.PROJECT_ROOT / out_rel
    write_report(
        out_path,
        rows,
        whisper_model=f"{args.backend}:{whisper_model_id}" if whisper_backend else None,
        gemma_model=gemma_model_name if gemma_client else None,
    )
    print(f"\nReport: {out_path}")
    return 0


def write_report(path: Path, rows: list[dict], *, whisper_model: str | None, gemma_model: str | None) -> None:
    L: list[str] = []
    L.append("# Phase 0.5 — Sanskrit STT shootout results\n")
    L.append(f"Run on {len(rows)} mantra IDs (each: clean + with_error).\n")
    L.append(f"- Whisper model: `{whisper_model}`" if whisper_model else "- Whisper: skipped")
    L.append(f"- Gemma model (LM Studio): `{gemma_model}`" if gemma_model else "- Gemma: skipped")
    L.append("")

    w_summary = g_summary = None
    if whisper_model:
        wcers = [r["whisper_clean_cer"] for r in rows if "whisper_clean_cer" in r]
        wlats = [r["whisper_clean_lat_s"] for r in rows if "whisper_clean_lat_s" in r]
        wpairs = [r for r in rows if "whisper_detected_error" in r]
        wrec = sum(1 for r in wpairs if r["whisper_detected_error"]) / max(1, len(wpairs))
        w_summary = (median(wcers), median(wlats), wrec)
        L += [
            "## Whisper",
            f"- median CER (clean): **{w_summary[0]:.3f}**",
            f"- median latency (s): **{w_summary[1]:.2f}**",
            f"- religious-error recall: **{w_summary[2]:.2f}** ({sum(1 for r in wpairs if r['whisper_detected_error'])}/{len(wpairs)})",
            "",
        ]
    if gemma_model:
        gcers = [r["gemma_clean_cer"] for r in rows if "gemma_clean_cer" in r]
        glats = [r["gemma_clean_lat_s"] for r in rows if "gemma_clean_lat_s" in r]
        gpairs = [r for r in rows if "gemma_detected_error" in r]
        grec = sum(1 for r in gpairs if r["gemma_detected_error"]) / max(1, len(gpairs))
        g_summary = (median(gcers), median(glats), grec)
        L += [
            "## Gemma 4 E4B (LM Studio)",
            f"- median CER (clean): **{g_summary[0]:.3f}**",
            f"- median latency (s): **{g_summary[1]:.2f}**",
            f"- religious-error recall: **{g_summary[2]:.2f}** ({sum(1 for r in gpairs if r['gemma_detected_error'])}/{len(gpairs)})",
            "",
        ]

    L.append("## Per-clip details\n")
    L.append("| mantra | len | dur | W-CER | W-lat | W-err? | G-CER | G-lat | G-err? |")
    L.append("|---|---|---|---|---|---|---|---|---|")
    for r in rows:
        def fmt_err(key: str) -> str:
            if key not in r:
                return "—"
            return "**yes**" if r[key] else "no"
        L.append(
            f"| {r['mantra_id']} | {r['length']} | {r['duration_s']}s "
            f"| {r.get('whisper_clean_cer', float('nan')):.3f} "
            f"| {r.get('whisper_clean_lat_s', float('nan')):.1f}s "
            f"| {fmt_err('whisper_detected_error')} "
            f"| {r.get('gemma_clean_cer', float('nan')):.3f} "
            f"| {r.get('gemma_clean_lat_s', float('nan')):.1f}s "
            f"| {fmt_err('gemma_detected_error')} |"
        )
    L.append("")

    L.append("## Transcripts\n")
    for r in rows:
        L.append(f"### {r['mantra_id']}")
        L.append(f"- **expected:** `{r['expected']}`")
        if "whisper_clean" in r:
            L.append(f"- whisper (clean): `{r['whisper_clean']}`")
            if "whisper_werr" in r:
                L.append(f"- whisper (with_error): `{r['whisper_werr']}`")
        if "gemma_clean" in r:
            L.append(f"- gemma (clean): `{r['gemma_clean']}`")
            if "gemma_werr" in r:
                L.append(f"- gemma (with_error): `{r['gemma_werr']}`")
        if "gemma_error" in r:
            L.append(f"- ⚠ gemma error: `{r['gemma_error']}`")
        L.append("")

    L.append("## Recommendation\n")
    if w_summary and g_summary:
        # Score = religious-error recall first, CER second (lower is better), latency third.
        w_score = (w_summary[2], -w_summary[0], -w_summary[1])
        g_score = (g_summary[2], -g_summary[0], -g_summary[1])
        winner = "Whisper" if w_score >= g_score else "Gemma 4 E4B"
        L += [
            f"**Pick: {winner}.**",
            "",
            "Decision rule: religious-error recall (primary), then CER (tiebreak), then latency.",
        ]
    elif w_summary:
        L.append("Only Whisper measured — defaulting to Whisper.")
    elif g_summary:
        L.append("Only Gemma measured — defaulting to Gemma 4 E4B.")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(L))


if __name__ == "__main__":
    sys.exit(main() or 0)
