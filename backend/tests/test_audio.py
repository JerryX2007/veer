import numpy as np

from app.analysis.audio import analyze_audio
from tests import synthetic


def test_whistles_and_crowd_roars():
    whistles = [2.0, 9.0, 15.0]
    samples = synthetic._audio(20.0, whistles, roars=[10.0], seed=1)
    audio = analyze_audio(samples.astype(np.float32), synthetic.AUDIO_RATE)

    assert len(audio.whistles) == len(whistles)
    for (start, end), truth in zip(audio.whistles, whistles):
        assert abs(start - truth) < 0.1
        assert 0.3 < end - start < 0.7

    loud, peak = audio.excitement(9.5, 14.0)
    quiet, _ = audio.excitement(3.0, 8.0)
    assert loud > 10 and 10.0 <= peak <= 13.0
    assert quiet < 3


def test_no_whistles_in_plain_noise():
    rng = np.random.default_rng(0)
    audio = analyze_audio(rng.normal(0, 0.1, 16000 * 10).astype(np.float32), 16000)
    assert audio.whistles == []


def test_silence_is_handled():
    audio = analyze_audio(np.zeros(100, np.float32), 16000)
    assert not audio.available
    assert audio.excitement(0, 5) == (0.0, 0)
