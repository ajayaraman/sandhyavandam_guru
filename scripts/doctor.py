"""Check that the local environment is ready to run the guru."""

from __future__ import annotations

import shutil
import sys
import urllib.error
import urllib.request

from sandhyavandanam_guru import config
from sandhyavandanam_guru.settings import load_settings


def check(label: str, ok: bool, detail: str = "") -> bool:
    mark = "✓" if ok else "✗"
    print(f"  {mark} {label}" + (f"   ({detail})" if detail else ""))
    return ok


def main() -> int:
    print("sandhyavandanam-guru doctor\n")
    all_ok = True

    all_ok &= check(
        "Python ≥ 3.11",
        sys.version_info >= (3, 11),
        f"running {sys.version.split()[0]}",
    )
    all_ok &= check(
        "Ritual YAML present",
        (config.RITUAL_DIR / "pratah_rigveda.yaml").exists(),
        str(config.RITUAL_DIR),
    )

    settings = load_settings()
    all_ok &= check("Settings YAML valid", True, "config/default.yaml")

    coach_url = f"{settings.coach_llm.base_url}/models"
    try:
        with urllib.request.urlopen(coach_url, timeout=2) as r:
            coach_ok = r.status == 200
            coach_detail = coach_url
    except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
        coach_ok = False
        coach_detail = f"{coach_url}: {e}"
    check(f"Coach LLM reachable ({settings.coach_llm.model})", coach_ok, coach_detail)

    check("`ollama` CLI on PATH (optional)", shutil.which("ollama") is not None)
    check(
        f"Mantra bank present (optional) — {config.MANTRA_DIR}",
        config.MANTRA_DIR.exists() and any(config.MANTRA_DIR.glob("*.wav")),
    )

    print("\nReady." if all_ok else "\nFix the ✗ items above before running the audio pipeline.")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
