import numpy as np

from app.analysis.trajectory import GRAVITY, Trajectory, estimate_gravity, find_contacts
from tests import synthetic


def scripted_trajectory(noise_px: float = 1.0, seed: int = 0) -> tuple[Trajectory, list[float]]:
    """The default synthetic match as a ball trajectory, skipping the video."""
    script = synthetic.default_script()
    starts, t = [], 3.0
    for rally in script:
        starts.append(t)
        t += rally.points[-1][0] + 7.0
    pos = synthetic._ball_positions(script, starts, int(t * synthetic.FPS))
    pos += np.random.default_rng(seed).normal(0, noise_px, pos.shape)
    traj = Trajectory(
        fps=synthetic.FPS,
        x=pos[:, 0] / synthetic.HEIGHT,
        y=pos[:, 1] / synthetic.HEIGHT,
        observed=~np.isnan(pos[:, 0]),
        aspect=synthetic.WIDTH / synthetic.HEIGHT,
    )
    contact_times = [start + p[0] for rally, start in zip(script, starts) for p in rally.points[1:-1]]
    return traj, contact_times


TRUE_METRES_PER_FH = synthetic.HEIGHT / synthetic.PX_PER_M  # 12 m


def test_gravity_calibrates_the_scale():
    traj, _ = scripted_trajectory()
    g = GRAVITY / TRUE_METRES_PER_FH
    contacts = find_contacts(traj, g, 4 / TRUE_METRES_PER_FH, 0.2)
    estimated = estimate_gravity(traj, contacts, min_flights=3)
    assert estimated is not None
    assert abs(GRAVITY / estimated - TRUE_METRES_PER_FH) < 0.5


def test_contacts_found_at_scripted_times():
    traj, truth = scripted_trajectory()
    g = GRAVITY / TRUE_METRES_PER_FH
    contacts = find_contacts(traj, g, 4 / TRUE_METRES_PER_FH, 0.2)
    found = [c.time for c in contacts]
    for t in truth:
        assert min(abs(f - t) for f in found) <= 2 / synthetic.FPS, f"no contact near {t:.2f}s"


def test_free_flight_has_no_contacts():
    fps, g = 30, 0.8
    t = np.arange(0, 1.5, 1 / fps)
    x, y = 0.2 + 0.5 * t, 0.5 - 0.6 * t + 0.5 * g * t * t
    traj = Trajectory(fps, x, y, np.ones(t.size, bool), 16 / 9)
    assert find_contacts(traj, g, 0.3, 0.2) == []


def test_contact_speeds_are_measured_within_a_short_flight():
    # Attack -> block is only 0.12 s; its speed must not be blended with the set.
    traj, _ = scripted_trajectory(noise_px=0.5)
    g = GRAVITY / TRUE_METRES_PER_FH
    contacts = find_contacts(traj, g, 4 / TRUE_METRES_PER_FH, 0.2)
    block = min(contacts, key=lambda c: abs(c.time - 40.02))
    speed = block.speed_in() * TRUE_METRES_PER_FH
    assert 17 <= speed <= 23  # scripted attack: ~20 m/s
