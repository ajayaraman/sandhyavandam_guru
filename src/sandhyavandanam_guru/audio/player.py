from __future__ import annotations

import threading
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import numpy as np


class Player:
    """Single-stream cancellable PCM player on top of sounddevice.

    Only one clip plays at a time. Calling play() while another clip is active
    interrupts it (used for barge-in and replay).
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()

    def play(self, pcm: "np.ndarray", sample_rate: int, block: bool = False) -> None:
        import sounddevice as sd

        with self._lock:
            sd.stop()
            sd.play(pcm, sample_rate)
        if block:
            sd.wait()

    def stop(self) -> None:
        import sounddevice as sd

        sd.stop()

    def wait(self) -> None:
        import sounddevice as sd

        sd.wait()
