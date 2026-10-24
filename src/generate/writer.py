"""JSON-lines writing and run state.

Each run writes new files (``<dataset>/<mode>_<yyyymmdd>.jsonl``) and never
edits old ones, so the bronze streaming tables pick up only new data. The
``_state/`` folder records the seed start, the seed end anchor and the last
generated date; ``increment`` rebuilds the same deterministic world from those
parameters. The pipeline never reads it.
"""

from __future__ import annotations

import json
import os
from datetime import date
from typing import Iterable

STATE_FILE = "_state/state.json"
STATE_DIR = "_state"


def _stamp(d: date) -> str:
    return d.strftime("%Y%m%d")


def dataset_path(out_dir: str, dataset: str, mode: str, run_date: date) -> str:
    return os.path.join(out_dir, dataset, f"{mode}_{_stamp(run_date)}.jsonl")


def write_dataset(out_dir: str, dataset: str, mode: str, run_date: date, rows: Iterable[dict]) -> str:
    path = dataset_path(out_dir, dataset, mode, run_date)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, separators=(",", ":"), sort_keys=True))
            fh.write("\n")
    return path


def load_state(out_dir: str) -> dict | None:
    path = os.path.join(out_dir, STATE_FILE)
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def save_state(out_dir: str, state: dict) -> str:
    path = os.path.join(out_dir, STATE_FILE)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(state, fh, separators=(",", ":"), sort_keys=True)
    return path
