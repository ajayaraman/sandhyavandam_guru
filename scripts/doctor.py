"""Check that the local environment is ready to run the guru."""

from __future__ import annotations

import shutil
import sys
import urllib.error
import urllib.request

from sandhyavandanam_guru import config


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

    lm_url = f"{config.LM_STUDIO_BASE_URL}/models"
    try:
        with urllib.request.urlopen(lm_url, timeout=2) as r:
            lm_ok = r.status == 200
            lm_detail = lm_url
    except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
        lm_ok = False
        lm_detail = f"{lm_url}: {e}"
    check("LM Studio reachable (optional)", lm_ok, lm_detail)

    check("`lms` CLI on PATH (optional)", shutil.which("lms") is not None)
    check(
        f"Mantra bank present (optional) — {config.MANTRA_DIR}",
        config.MANTRA_DIR.exists() and any(config.MANTRA_DIR.glob("*.wav")),
    )

    print("\nReady." if all_ok else "\nFix the ✗ items above before running the audio pipeline.")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
