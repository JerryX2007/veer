import pytest

from app.media import clipper, ffmpeg


def test_padded_window_clamps_to_video():
    w = clipper.padded_window(0.5, 5.0, source_duration=6.0, pad_before=1.0, pad_after=1.5)
    assert (w.start, w.end) == (0.0, 6.0)


def test_padded_window_rejects_bad_ranges():
    with pytest.raises(ValueError):
        clipper.padded_window(5, 5, 10)
    with pytest.raises(ValueError):
        clipper.padded_window(30, 35, 10)


def test_probe(footage):
    info = ffmpeg.probe(footage["hd"])
    assert (info.width, info.height) == (640, 360)
    assert info.has_audio and info.fps == 30
    assert info.duration == pytest.approx(20, abs=0.1)
    assert not ffmpeg.probe(footage["sd_silent"]).has_audio


def test_cut_is_frame_accurate_and_normalised(footage, tmp_path):
    # Source keyframes are every 5s; a stream-copy cut at 7.3s would start at 5s. Re-encoding must not.
    out = clipper.cut_clip(footage["hd"], clipper.Window(7.3, 11.8), tmp_path / "c.mp4", source_has_audio=True)
    info = ffmpeg.probe(out)
    assert info.duration == pytest.approx(4.5, abs=0.1)
    assert info.has_audio and info.fps == 30


def test_silent_source_gets_audio_track(footage, tmp_path):
    out = clipper.cut_clip(footage["sd_silent"], clipper.Window(1, 3), tmp_path / "s.mp4", source_has_audio=False)
    info = ffmpeg.probe(out)
    assert info.has_audio
    assert info.duration == pytest.approx(2, abs=0.1)


def test_reel_stream_copy_same_size(footage, tmp_path):
    a = clipper.cut_clip(footage["hd"], clipper.Window(1, 3), tmp_path / "a.mp4", source_has_audio=True)
    b = clipper.cut_clip(footage["hd"], clipper.Window(10, 13), tmp_path / "b.mp4", source_has_audio=True)
    reel = clipper.concat_reel([a, b], tmp_path / "reel.mp4")
    assert ffmpeg.probe(reel).duration == pytest.approx(5, abs=0.2)


def test_reel_mixed_sizes_reencodes(footage, tmp_path):
    a = clipper.cut_clip(footage["hd"], clipper.Window(1, 3), tmp_path / "a.mp4", source_has_audio=True)
    b = clipper.cut_clip(footage["hd"], clipper.Window(4, 6), tmp_path / "b.mp4", source_has_audio=True)
    c = clipper.cut_clip(footage["sd_silent"], clipper.Window(1, 3), tmp_path / "c.mp4", source_has_audio=False)
    reel = clipper.concat_reel([a, c, b], tmp_path / "reel.mp4")
    info = ffmpeg.probe(reel)
    assert (info.width, info.height) == (640, 360)  # most common size wins
    assert info.duration == pytest.approx(6, abs=0.2)


def test_thumbnail(footage, tmp_path):
    clip = clipper.cut_clip(footage["hd"], clipper.Window(1, 3), tmp_path / "a.mp4", source_has_audio=True)
    thumb = clipper.thumbnail(clip, 1.0, tmp_path / "t.jpg")
    assert thumb.stat().st_size > 0
