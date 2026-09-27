import os
<<<<<<< Updated upstream
import tempfile

import pytest

# The app keeps its SQLite file and uploads relative to the working directory
# and creates them when app.main is imported, so tests point both somewhere
# disposable first (and import app.main only inside fixtures).
_workdir = tempfile.mkdtemp(prefix="veer-tests-")
os.environ["DATABASE_URL"] = f"sqlite:///{_workdir}/test.db"


@pytest.fixture(scope="session", autouse=True)
def isolated_workdir():
    previous = os.getcwd()
    os.chdir(_workdir)
    yield _workdir
    os.chdir(previous)
=======
import subprocess
import tempfile
from pathlib import Path

import pytest

# Configure before the app is imported: temp storage + jobs run inline so tests are deterministic.
_TMP = Path(os.environ.get("PYTEST_VB_TMP", Path(tempfile.gettempdir()) / "vb-test"))
os.environ.setdefault("VB_MEDIA_ROOT", str(_TMP / "media"))
os.environ.setdefault("VB_DATABASE_URL", f"sqlite:///{_TMP / 'test.db'}")
os.environ["VB_SYNC_JOBS"] = "true"
os.environ["VB_CLIP_PRESET"] = "ultrafast"


def make_video(path: Path, seconds: float, size: str = "640x360", audio: bool = True) -> Path:
    """Synthetic 'match footage': ffmpeg test pattern with a running timestamp, optional tone."""
    args = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            "-f", "lavfi", "-i", f"testsrc2=size={size}:rate=30:duration={seconds}"]
    if audio:
        args += ["-f", "lavfi", "-i", f"sine=frequency=440:duration={seconds}", "-c:a", "aac"]
    args += ["-c:v", "libx264", "-preset", "ultrafast", "-g", "150", "-pix_fmt", "yuv420p", str(path)]
    subprocess.run(args, check=True)
    return path


@pytest.fixture(scope="session")
def footage(tmp_path_factory):
    d = tmp_path_factory.mktemp("footage")
    return {
        "hd": make_video(d / "match_hd.mp4", 20, "640x360", audio=True),
        "sd_silent": make_video(d / "match_sd.mov", 10, "320x240", audio=False),
    }


@pytest.fixture()
def client():
    import shutil

    shutil.rmtree(_TMP, ignore_errors=True)
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as c:
        yield c
>>>>>>> Stashed changes
