from __future__ import annotations

import threading
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import numpy as np

# 5 ms linear fade at clip edges. Removes the click you get when sd.stop()
# truncates mid-cycle and when sd.play() starts at a non-zero sample.
_FADE_MS = 5


def _fade_edges(pcm: "np.ndarray", sample_rate: int) -> "np.ndarray":
    import numpy as np

    n = int(sample_rate * _FADE_MS / 1000)
    if pcm.size < 2 * n or n < 8:
        return pcm
    out = pcm.astype(np.float32, copy=True)
    ramp = np.linspace(0.0, 1.0, n, dtype=np.float32)
    out[:n] *= ramp
    out[-n:] *= ramp[::-1]
    return out.astype(pcm.dtype)


class Player:
    """Single-stream cancellable PCM player on top of sounddevice.

    Only one clip plays at a time. Calling play() while another clip is active
    interrupts it (used for barge-in and replay).

    `latency="high"` requests a larger audio buffer from PortAudio. The default
    is tiny and underruns over Bluetooth (e.g. AirPods, Bose QC45) on macOS,
    which makes playback sound stuttery and stop-and-start. High latency
    typically gives ~50-100 ms of headroom, smooth playback, and is invisible
    to a coach voice context.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()

    def play(self, pcm: "np.ndarray", sample_rate: int, block: bool = False) -> None:
        import sounddevice as sd

        pcm = _fade_edges(pcm, sample_rate)
        with self._lock:
            sd.stop()
            sd.play(pcm, sample_rate, latency="high")
        if block:
            sd.wait()

    def stop(self) -> None:
        import sounddevice as sd

        sd.stop()

    def wait(self) -> None:
        import sounddevice as sd

        sd.wait()
