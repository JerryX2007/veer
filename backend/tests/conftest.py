import os
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
