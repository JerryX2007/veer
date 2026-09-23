"""A synthetic match video with known rallies and highlights, for tests.

The court is seen side-on (net in the middle of the frame), the ball follows
real ballistic arcs between scripted contacts, a few "players" wander about
as distractors, and the soundtrack has crowd noise, referee whistles and
crowd roars. Scale: 30 px per metre in a 640x360 frame (12 m per frame
height), so metre-based thresholds behave as they would on real footage.

Run directly to write a demo file: python -m tests.synthetic out.mp4
"""

import subprocess
import sys
import wave
from dataclasses import dataclass, field
from pathlib import Path

import cv2
import numpy as np

WIDTH, HEIGHT, FPS = 640, 360, 30
PX_PER_M = 30.0
G_PX = 9.81 * PX_PER_M
FLOOR = 330.0
NET_X = 320.0
AUDIO_RATE = 16000


def h(metres: float) -> float:
    """Image y of a point `metres` above the floor."""
    return FLOOR - metres * PX_PER_M


# Contact points (seconds from rally start, x px, y px). The ball flies a
# ballistic arc between consecutive points and is invisible outside them.
def _serve_to_right_attack() -> list[tuple[float, float, float]]:
    return [
        (0.0, 40, h(1.0)),    # in the server's hand
        (0.9, 45, h(2.6)),    # toss comes down, serve struck
        (2.2, 480, h(0.8)),   # serve received on the right
        (3.8, 360, h(2.8)),   # pass reaches the setter
        (5.0, 400, h(3.2)),   # set reaches the hitter, who attacks
    ]


def _serve_to_left_attack() -> list[tuple[float, float, float]]:
    # Mirror image: served from the right, attacked from the left.
    return [(t, WIDTH - x, y) for t, x, y in _serve_to_right_attack()]


@dataclass
class ScriptedRally:
    points: list[tuple[float, float, float]]
    serve_offset: float = 0.9
    highlights: list[tuple[str, float]] = field(default_factory=list)  # (kind, offset)
    crowd_roar: bool = False


def default_script() -> list[ScriptedRally]:
    big_kill = ScriptedRally(
        _serve_to_right_attack() + [
            (5.35, 170, FLOOR),   # spike lands on the left...
            (7.5, 60, FLOOR),     # ...and rebounds ~5.7 m before landing again
            (8.2, 40, FLOOR),
        ],
        highlights=[("big_kill", 5.35)],
        crowd_roar=True,
    )
    save = ScriptedRally(
        _serve_to_right_attack() + [
            (5.35, 150, h(0.3)),  # hard spike dug just off the floor
            (7.0, 250, h(2.6)),   # dig reaches the setter
            (8.2, 230, h(3.2)),   # set, left-side attack
            (8.6, 470, FLOOR),    # ordinary kill, small bounce
            (9.3, 520, FLOOR),
            (9.7, 540, FLOOR),
        ],
        highlights=[("great_save", 5.35)],
    )
    block = ScriptedRally(
        _serve_to_right_attack() + [
            (5.12, 328, h(3.0)),  # attack stuffed at the net...
            (5.6, 370, FLOOR),    # ...straight down on the attacker's side
            (6.3, 395, FLOOR),
            (6.8, 410, FLOOR),
        ],
        highlights=[("shutdown_block", 5.12)],
    )
    plain = ScriptedRally(
        _serve_to_left_attack() + [
            (5.4, 460, FLOOR),    # ordinary kill, nothing special
            (6.1, 510, FLOOR),
            (6.6, 530, FLOOR),
        ],
    )
    crowd_only = ScriptedRally(
        _serve_to_right_attack() + [
            (5.4, 180, FLOOR),
            (6.1, 130, FLOOR),
            (6.6, 110, FLOOR),
        ],
        highlights=[("crowd_reaction", 6.6)],
        crowd_roar=True,
    )
    return [big_kill, save, block, plain, crowd_only]


@dataclass
class TruthRally:
    serve_time: float
    play_end: float
    highlights: list[tuple[str, float]]


@dataclass
class SyntheticMatch:
    path: Path
    duration: float
    rallies: list[TruthRally]
    whistles: list[float]


def _ball_positions(script: list[ScriptedRally], starts: list[float], n_frames: int) -> np.ndarray:
    pos = np.full((n_frames, 2), np.nan)
    for rally, start in zip(script, starts):
        for (t0, x0, y0), (t1, x1, y1) in zip(rally.points, rally.points[1:]):
            dur = t1 - t0
            vx = (x1 - x0) / dur
            vy = (y1 - y0) / dur - 0.5 * G_PX * dur
            f0, f1 = int(np.ceil((start + t0) * FPS)), int(np.floor((start + t1) * FPS))
            for f in range(f0, min(f1, n_frames - 1) + 1):
                s = f / FPS - start - t0
                pos[f] = (x0 + vx * s, y0 + vy * s + 0.5 * G_PX * s * s)
    return pos


def _background() -> np.ndarray:
    img = np.zeros((HEIGHT, WIDTH, 3), np.uint8)
    img[:] = (70, 72, 80)  # wall
    img[int(h(1.2)):] = (120, 160, 190)  # floor
    cv2.line(img, (20, int(FLOOR)), (WIDTH - 20, int(FLOOR)), (240, 240, 240), 2)
    cv2.line(img, (int(NET_X), int(h(2.43))), (int(NET_X), int(h(1.43))), (30, 30, 30), 3)
    cv2.line(img, (int(NET_X) - 3, int(h(2.43))), (int(NET_X) + 3, int(h(2.43))), (250, 250, 250), 2)
    return img


def _draw_players(img: np.ndarray, t: float) -> None:
    # Four players drifting back and forth at ~1 m/s: moving distractors.
    for k, (home, colour) in enumerate([(120, (40, 40, 200)), (230, (40, 40, 200)),
                                        (410, (200, 80, 30)), (520, (200, 80, 30))]):
        x = int(home + 25 * np.sin(0.9 * t + k))
        top = int(FLOOR - 1.8 * PX_PER_M)
        cv2.rectangle(img, (x - 8, top + 10), (x + 8, int(FLOOR) - 20), colour, -1)
        cv2.rectangle(img, (x - 6, int(FLOOR) - 20), (x + 6, int(FLOOR)), (60, 60, 60), -1)
        cv2.circle(img, (x, top + 4), 6, (140, 170, 220), -1)


def _audio(duration: float, whistles: list[float], roars: list[float], seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    n = int(duration * AUDIO_RATE)
    t = np.arange(n) / AUDIO_RATE
    # Crowd murmur: low-passed noise.
    audio = np.convolve(rng.normal(0, 0.05, n), np.ones(8) / 8, mode="same")
    for start in roars:
        a, b = int(start * AUDIO_RATE), min(n, int((start + 3.0) * AUDIO_RATE))
        env = np.sin(np.linspace(0, np.pi, b - a)) ** 0.5
        audio[a:b] += np.convolve(rng.normal(0, 0.5, b - a), np.ones(8) / 8, mode="same") * env
    for start in whistles:
        a, b = int(start * AUDIO_RATE), min(n, int((start + 0.5) * AUDIO_RATE))
        tt = t[a:b]
        freq = 3100 + 40 * np.sin(2 * np.pi * 25 * tt)
        phase = 2 * np.pi * np.cumsum(freq) / AUDIO_RATE
        audio[a:b] += 0.3 * np.sin(phase) + 0.08 * np.sin(2 * phase)
    return np.clip(audio, -1, 1)


def make_match(
    path: Path,
    script: list[ScriptedRally] | None = None,
    lead_in: float = 3.0,
    gap: float = 7.0,
    seed: int = 0,
) -> SyntheticMatch:
    script = script or default_script()
    starts, t = [], lead_in
    for rally in script:
        starts.append(t)
        t += rally.points[-1][0] + gap
    duration = t
    n_frames = int(duration * FPS)

    truth, whistles, roars = [], [], []
    for rally, start in zip(script, starts):
        play_end = start + rally.points[-1][0]
        truth.append(TruthRally(
            serve_time=start + rally.serve_offset,
            play_end=play_end,
            highlights=[(kind, start + offset) for kind, offset in rally.highlights],
        ))
        whistles += [start - 2.5, play_end + 0.8]
        if rally.crowd_roar:
            roars.append(play_end - 0.5)

    path = Path(path)
    wav_path = path.with_suffix(".wav")
    samples = (_audio(duration, whistles, roars, seed) * 32767).astype(np.int16)
    with wave.open(str(wav_path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(AUDIO_RATE)
        w.writeframes(samples.tobytes())

    ball = _ball_positions(script, starts, n_frames)
    background = _background()
    # Sensor noise, cycled from a small bank so rendering stays quick.
    rng = np.random.default_rng(seed)
    noise_bank = [rng.normal(0, 2.0, (HEIGHT, WIDTH, 3)).astype(np.int16) for _ in range(7)]
    cmd = [
        "ffmpeg", "-y", "-v", "error",
        "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{WIDTH}x{HEIGHT}", "-r", str(FPS), "-i", "-",
        "-i", str(wav_path),
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "18", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-shortest", str(path),
    ]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for f in range(n_frames):
        frame = background.copy()
        _draw_players(frame, f / FPS)
        if not np.isnan(ball[f, 0]):
            cv2.circle(frame, (int(round(ball[f, 0])), int(round(ball[f, 1]))), 4, (0, 220, 255), -1)
        frame = np.clip(frame + noise_bank[f % len(noise_bank)], 0, 255).astype(np.uint8)
        proc.stdin.write(frame.tobytes())
    proc.stdin.close()
    if proc.wait() != 0:
        raise RuntimeError("ffmpeg failed to encode the synthetic match")
    wav_path.unlink()
    return SyntheticMatch(path, duration, truth, whistles)


if __name__ == "__main__":
    match = make_match(Path(sys.argv[1] if len(sys.argv) > 1 else "synthetic_match.mp4"))
    print(f"wrote {match.path} ({match.duration:.1f}s)")
    for i, r in enumerate(match.rallies):
        print(f"  rally {i}: serve {r.serve_time:.2f}, play ends {r.play_end:.2f}, highlights {r.highlights}")
