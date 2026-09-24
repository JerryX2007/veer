"""Audio cues: crowd loudness and referee whistles.

- Crowd loudness is measured in the 100-1800 Hz band, where cheering carries
  most of its energy, so whistles (2-4.5 kHz) don't inflate it.
- A whistle is a loud, sustained, almost pure tone in the 2-4.5 kHz band:
  most of the frame's energy sits in that band, and within it one narrow peak
  towers over the rest. Shoe squeaks are tonal too, but much shorter.
"""

from dataclasses import dataclass, field

import numpy as np

HOP_S = 0.02
WINDOW = 1024
LOUDNESS_BAND = (100.0, 1800.0)
WHISTLE_BAND = (2000.0, 4500.0)
TOTAL_BAND = (100.0, 8000.0)
WHISTLE_MIN_BAND_SHARE = 0.6
WHISTLE_MIN_TONALITY = 15.0  # in-band peak / in-band mean power
WHISTLE_MIN_DURATION = 0.2
WHISTLE_MAX_GAP = 0.06
_EPS = 1e-12


@dataclass
class AudioSignals:
    hop: float = HOP_S
    loudness_db: np.ndarray = field(default_factory=lambda: np.zeros(0))
    baseline_db: float = 0.0
    whistles: list[tuple[float, float]] = field(default_factory=list)

    @property
    def available(self) -> bool:
        return self.loudness_db.size > 0

    def excitement(self, start: float, end: float, smooth_s: float = 0.5) -> tuple[float, float]:
        """Peak loudness above baseline (dB) within [start, end], and its time."""
        if not self.available:
            return 0.0, start
        k = max(1, int(round(smooth_s / self.hop)))
        lo = max(0, int(start / self.hop))
        hi = min(self.loudness_db.size, int(np.ceil(end / self.hop)) + 1)
        if hi - lo < 1:
            return 0.0, start
        # Pad by the smoothing width so the window's edges average real audio.
        pad_lo, pad_hi = max(0, lo - k), min(self.loudness_db.size, hi + k)
        smoothed = np.convolve(self.loudness_db[pad_lo:pad_hi], np.ones(k) / k, mode="same")
        segment = smoothed[lo - pad_lo:hi - pad_lo]
        i = int(np.argmax(segment))
        return float(segment[i] - self.baseline_db), (lo + i) * self.hop


def analyze_audio(samples: np.ndarray, sample_rate: int) -> AudioSignals:
    if samples.size < WINDOW:
        return AudioSignals()

    hop = int(round(HOP_S * sample_rate))
    freqs = np.fft.rfftfreq(WINDOW, 1.0 / sample_rate)
    loud_bins = (freqs >= LOUDNESS_BAND[0]) & (freqs < LOUDNESS_BAND[1])
    whistle_bins = (freqs >= WHISTLE_BAND[0]) & (freqs < WHISTLE_BAND[1])
    total_bins = (freqs >= TOTAL_BAND[0]) & (freqs < TOTAL_BAND[1])
    window = np.hanning(WINDOW).astype(np.float32)

    n_frames = 1 + (samples.size - WINDOW) // hop
    loud = np.empty(n_frames, dtype=np.float32)
    band_share = np.empty(n_frames, dtype=np.float32)
    tonality = np.empty(n_frames, dtype=np.float32)
    band_power = np.empty(n_frames, dtype=np.float32)

    # Chunked so a 2-hour match doesn't need gigabytes for the spectrogram.
    chunk = 4096
    for first in range(0, n_frames, chunk):
        last = min(n_frames, first + chunk)
        idx = (np.arange(first, last) * hop)[:, None] + np.arange(WINDOW)[None, :]
        power = np.abs(np.fft.rfft(samples[idx] * window, axis=1)) ** 2
        in_band = power[:, whistle_bins]
        band_sum = in_band.sum(axis=1)
        loud[first:last] = 10 * np.log10(power[:, loud_bins].mean(axis=1) + _EPS)
        band_share[first:last] = band_sum / (power[:, total_bins].sum(axis=1) + _EPS)
        tonality[first:last] = in_band.max(axis=1) / (in_band.mean(axis=1) + _EPS)
        band_power[first:last] = 10 * np.log10(band_sum + _EPS)

    loud_enough = band_power > np.median(band_power) + 10.0
    is_whistle = (band_share >= WHISTLE_MIN_BAND_SHARE) & (tonality >= WHISTLE_MIN_TONALITY) & loud_enough

    hop_s = hop / sample_rate
    # Frame i is centred half a window after it starts.
    whistles = _group_runs(is_whistle, hop_s, offset=WINDOW / sample_rate / 2)
    return AudioSignals(
        hop=hop_s,
        loudness_db=loud,
        baseline_db=float(np.median(loud)),
        whistles=whistles,
    )


def _group_runs(mask: np.ndarray, hop_s: float, offset: float) -> list[tuple[float, float]]:
    """Turn a per-frame boolean mask into merged (start, end) times."""
    runs = []
    max_gap = max(1, int(round(WHISTLE_MAX_GAP / hop_s)))
    i, n = 0, mask.size
    while i < n:
        if not mask[i]:
            i += 1
            continue
        start = end = i
        j = i + 1
        while j < n and j - end <= max_gap:
            if mask[j]:
                end = j
            j += 1
        runs.append((start, end))
        i = end + 1

    return [
        (round(start * hop_s + offset, 3), round(end * hop_s + offset, 3))
        for start, end in runs
        if (end - start) * hop_s >= WHISTLE_MIN_DURATION
    ]
