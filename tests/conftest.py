import pytest

from generate.cli import run

NUM_EMPLOYEES = 500
SEED = 42


@pytest.fixture(scope="session")
def seed_dir(tmp_path_factory):
    out = tmp_path_factory.mktemp("seed")
    run("seed", NUM_EMPLOYEES, SEED, str(out))
    return str(out)
