"""Shared helpers for reading generator output."""

from __future__ import annotations

import json
import os
from datetime import date, timedelta


def read_dataset(out_dir: str, dataset: str) -> list:
    folder = os.path.join(out_dir, dataset)
    rows = []
    if not os.path.isdir(folder):
        return rows
    for name in sorted(os.listdir(folder)):
        if name.endswith(".jsonl"):
            with open(os.path.join(folder, name), "r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if line:
                        rows.append(json.loads(line))
    return rows


def read_manifest(out_dir: str) -> dict:
    with open(os.path.join(out_dir, "_state", "manifest.json"), "r", encoding="utf-8") as fh:
        return json.load(fh)


def as_date(s: str) -> date:
    return date.fromisoformat(s)


def active_at(events: list, team_ids: set, when: date) -> set:
    """Workers on ``team_ids`` with no termination on or before ``when``."""
    terminated = set()
    members = set()
    for e in events:
        if e["org_unit_id"] in team_ids and as_date(e["effective_date"]) <= when:
            members.add(e["worker_id"])
            if e["event_type"] == "termination":
                terminated.add(e["worker_id"])
    return members - terminated


def voluntary_exits_after(events: list, team_ids: set, when: date) -> list:
    return [e for e in events
            if e["event_type"] == "termination" and e["termination_type"] == "voluntary"
            and e["org_unit_id"] in team_ids and as_date(e["effective_date"]) > when]
