"""Same seed and same end date must produce byte-identical files."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from generate.cli import run

from .conftest import NUM_EMPLOYEES, SEED

SRC = Path(__file__).resolve().parents[1] / "src"


def _run(out):
    run("seed", NUM_EMPLOYEES, SEED, out)
    files = {}
    for root, _dirs, names in os.walk(out):
        for name in names:
            if name == "state.json":
                continue
            path = os.path.join(root, name)
            rel = os.path.relpath(path, out)
            with open(path, "rb") as fh:
                files[rel] = fh.read()
    return files


def test_two_runs_are_identical(tmp_path):
    a = _run(str(tmp_path / "a"))
    b = _run(str(tmp_path / "b"))
    assert set(a) == set(b)
    for name in a:
        assert a[name] == b[name], f"{name} differs between runs"


def test_two_processes_are_identical(tmp_path):
    """PYTHONHASHSEED must not leak into IDs or text."""
    outs = []
    for hash_seed in ("1", "2"):
        out = tmp_path / f"p{hash_seed}"
        env = dict(os.environ, PYTHONHASHSEED=hash_seed, PYTHONPATH=str(SRC))
        subprocess.run(
            [sys.executable, "-m", "generate", "--mode", "seed",
             "--num-employees", str(NUM_EMPLOYEES), "--seed", str(SEED),
             "--output", str(out), "--end-date", "2026-06-30"],
            cwd=SRC, env=env, check=True, capture_output=True, text=True,
        )
        outs.append(out)
    files = []
    for out in outs:
        found = {}
        for root, _dirs, names in os.walk(out):
            for name in names:
                if name == "state.json":
                    continue
                path = os.path.join(root, name)
                with open(path, "rb") as fh:
                    found[os.path.relpath(path, out)] = fh.read()
        files.append(found)
    assert set(files[0]) == set(files[1])
    for name in files[0]:
        assert files[0][name] == files[1][name], f"{name} differs between processes"
