"""Increment mode must extend the seed without rewriting its history."""

from __future__ import annotations

import collections
import json
import os
from datetime import date, timedelta

import pytest

from generate import config as cfg
from generate import datasets
from generate.cli import build_world, run
from generate.dates import add_months, yesterday

from .conftest import NUM_EMPLOYEES, SEED
from .helpers import as_date, read_dataset, read_manifest

SEED_END = date(2026, 6, 30)
INCREMENT_END = date(2026, 7, 14)


def _file(out, dataset, mode, when):
    path = os.path.join(out, dataset, f"{mode}_{when:%Y%m%d}.jsonl")
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def _world(end):
    return build_world(NUM_EMPLOYEES, SEED, "seed", end,
                       start=add_months(SEED_END, -24), anchor=SEED_END)


def test_history_is_reproduced_when_the_window_grows():
    short, _ = datasets.build_rows(_world(SEED_END))
    long, _ = datasets.build_rows(_world(INCREMENT_END))
    cut = SEED_END.isoformat()
    for dataset, field in datasets.DATE_FIELD.items():
        if field is None:
            continue
        short_rows = [r for r in short[dataset] if r.get(field, "") <= cut]
        long_rows = [r for r in long[dataset] if r.get(field, "") <= cut]
        if dataset == "productivity":
            keep = lambda r: as_date(r["week_start"]) + timedelta(days=6) <= SEED_END
            short_rows = [r for r in short_rows if keep(r)]
            long_rows = [r for r in long_rows if keep(r)]
        if dataset == "workers":
            # Worker rows are a state snapshot. Compare only workers that had
            # no event after the cut, so both runs describe the same state.
            changed = {e["worker_id"] for e in long["worker_events"]
                       if e["effective_date"] > cut}
            short_rows = [r for r in short_rows if r["worker_id"] not in changed]
            long_rows = [r for r in long_rows if r["worker_id"] not in changed]
        if dataset == "requisitions":
            # A requisition whose status or fill changes after the cut moves
            # to a later updated_date. Its seed row was correct as of the cut.
            changed = {r["requisition_id"] for r in long[dataset]
                       if r["opened_date"] <= cut and r["updated_date"] > cut}
            short_rows = [r for r in short_rows if r["requisition_id"] not in changed]
            long_rows = [r for r in long_rows if r["requisition_id"] not in changed]
        left = sorted(json.dumps(r, sort_keys=True) for r in short_rows)
        right = sorted(json.dumps(r, sort_keys=True) for r in long_rows)
        assert left == right, dataset


def test_increment_appends_only_new_rows_with_stable_ids(tmp_path):
    out = str(tmp_path / "raw")
    run("seed", NUM_EMPLOYEES, SEED, out, SEED_END)
    run("increment", None, None, out, INCREMENT_END)

    state = json.load(open(os.path.join(out, "_state", "state.json")))
    assert state["anchor_date"] == SEED_END.isoformat()
    assert state["last_date"] == INCREMENT_END.isoformat()

    week = INCREMENT_END.isoformat()
    seed_events = _file(out, "worker_events", "seed", SEED_END)
    inc_events = _file(out, "worker_events", "increment", INCREMENT_END)
    seed_ids = {e["event_id"] for e in seed_events}
    seed_by_id = {e["event_id"]: e for e in seed_events}
    reused = [e for e in inc_events if e["event_id"] in seed_ids]
    # Only the deliberate exact-duplicate defect may reuse an ID.
    assert all(e == seed_by_id[e["event_id"]] for e in reused)
    assert len(reused) <= read_manifest(out)["defects"]["duplicate_worker_events"]

    seed_workers = {w["worker_id"]: w for w in _file(out, "workers", "seed", SEED_END)}
    inc_workers = _file(out, "workers", "increment", INCREMENT_END)
    new_hires = [w for w in inc_workers if w["hire_date"] > SEED_END.isoformat()]
    assert new_hires
    assert not [w for w in new_hires if w["worker_id"] in seed_workers]

    for dataset, field in datasets.DATE_FIELD.items():
        if field is None:
            continue
        rows = _file(out, dataset, "increment", INCREMENT_END)
        assert all(r.get(field, "") > SEED_END.isoformat() for r in rows), dataset

    productivity = _file(out, "productivity", "increment", INCREMENT_END)
    assert productivity
    assert all(as_date(r["week_start"]) + timedelta(days=6) <= INCREMENT_END
               for r in productivity)


def test_increment_keeps_manager_and_compensation_invariants(tmp_path):
    out = str(tmp_path / "raw")
    run("seed", NUM_EMPLOYEES, SEED, out, SEED_END)
    run("increment", None, None, out, INCREMENT_END)

    workers = read_dataset(out, "workers")
    latest = {}
    for w in workers:
        if w["worker_id"] not in latest or w["updated_date"] > latest[w["worker_id"]]["updated_date"]:
            latest[w["worker_id"]] = w
    assert len(latest) == len({w["worker_id"] for w in workers})
    empty = sum(1 for w in latest.values() if not w["manager_id"])
    assert empty / len(latest) < 0.10, empty
    assert not [w for w in latest.values() if w["manager_id"] == w["worker_id"]]

    events = read_dataset(out, "worker_events")
    hire = {w["worker_id"]: as_date(w["hire_date"]) for w in latest.values()}
    changes = [e for e in events if e["event_type"] == "manager_change"]
    assert changes
    assert all(as_date(e["effective_date"]) >= hire[e["worker_id"]] for e in changes)
    by_id = {w["worker_id"]: w for w in latest.values()}
    for e in changes:
        manager = by_id.get(e["manager_id"])
        if manager and manager["termination_date"]:
            assert as_date(manager["termination_date"]) >= as_date(e["effective_date"])

    by_worker = collections.defaultdict(list)
    for row in read_dataset(out, "compensation"):
        by_worker[row["worker_id"]].append(row)
    for rows in by_worker.values():
        rows.sort(key=lambda r: r["effective_date"])
        assert all(b["base_salary"] >= a["base_salary"] for a, b in zip(rows, rows[1:]))
    assert all(as_date(c["effective_date"]) >= hire[c["worker_id"]]
               for c in read_dataset(out, "compensation")
               if c["change_reason"] == "promotion")


def test_licensing_and_recruiting_data_are_complete(tmp_path):
    out = str(tmp_path / "raw")
    run("seed", NUM_EMPLOYEES, SEED, out, SEED_END)

    licences = read_dataset(out, "licenses")
    latest = {}
    for row in licences:
        key = (row["worker_id"], row["license_id"])
        if key not in latest or row["status_date"] > latest[key]["status_date"]:
            latest[key] = row

    def expected_status(row):
        expiry = as_date(row["expiry_date"])
        when = as_date(row["status_date"])
        if when < expiry - timedelta(days=60):
            return "Active"
        if when < expiry:
            return "Expiring"
        return "Expired"

    assert all(row["status"] == expected_status(row) for row in licences)
    expiring = [row for row in latest.values()
                if SEED_END <= as_date(row["expiry_date"]) <= SEED_END + timedelta(days=60)]
    assert expiring
    assert all(row["status"] != "Active" for row in expiring)

    reqs = read_dataset(out, "requisitions")
    assert reqs
    assert all(r["org_unit_id"] and r["hiring_manager_id"] for r in reqs)
    filled = [r for r in reqs if r["status"] == "Filled"]
    assert filled
    assert sum(1 for r in filled if not r["filled_by_worker_id"]) / len(filled) < 0.05

    candidates = read_dataset(out, "candidates")
    assert any(c["worker_id"] for c in candidates)
    by_candidate = collections.defaultdict(list)
    for row in candidates:
        by_candidate[row["candidate_id"]].append(row)
    stage_order = {name: i for i, name in enumerate(
        ["Applied", "Screening", "Interview", "Offer"])}
    for rows in by_candidate.values():
        ordered = sorted(rows, key=lambda c: stage_order[c["stage"]])
        dates = [c["stage_date"] for c in ordered]
        assert dates == sorted(dates)
        assert len(dates) == len(set(dates))

    assert len({r["course_name"] for r in read_dataset(out, "training_assignments")}) == len(cfg.COURSES)


def test_increment_brings_new_survey_wave_and_review_cycle(tmp_path):
    out = str(tmp_path / "raw")
    seed_end = date(2026, 4, 1)
    later = date(2026, 10, 2)
    run("seed", NUM_EMPLOYEES, SEED, out, seed_end)
    run("increment", None, None, out, later)

    surveys = _file(out, "engagement_responses", "increment", later)
    reviews = _file(out, "performance_reviews", "increment", later)
    jobs = _file(out, "jobs", "increment", later)
    training = _file(out, "training_assignments", "increment", later)
    assert surveys and all(r["wave_date"] > seed_end.isoformat() for r in surveys)
    assert reviews and all(r["review_date"] > seed_end.isoformat() for r in reviews)
    assert jobs and all(r["created_date"] > seed_end.isoformat() for r in jobs)
    assert training and all(r["status_date"] > seed_end.isoformat() for r in training)
    assert any(r["cycle_date"] == "2026-10-01" for r in training)

    long_world = build_world(NUM_EMPLOYEES, SEED, "seed", later,
                             start=add_months(seed_end, -24), anchor=seed_end)
    long_rows, _ = datasets.build_rows(long_world)

    def latest(rows, key, date_field):
        out = {}
        for row in rows:
            row_key = row[key]
            if row_key not in out or row[date_field] > out[row_key][date_field]:
                out[row_key] = row
        return out

    got_training = latest(read_dataset(out, "training_assignments"),
                          "assignment_id", "status_date")
    want_training = latest(long_rows["training_assignments"],
                           "assignment_id", "status_date")
    assert got_training == want_training

    got_reqs = latest(read_dataset(out, "requisitions"),
                      "requisition_id", "updated_date")
    want_reqs = {r["requisition_id"]: r for r in long_rows["requisitions"]}
    assert got_reqs == want_reqs

    for dataset in ("productivity", "candidates"):
        accumulated = sorted(json.dumps(r, sort_keys=True)
                             for r in read_dataset(out, dataset))
        expected = sorted(json.dumps(r, sort_keys=True) for r in long_rows[dataset])
        assert accumulated == expected, dataset


def test_training_written_when_cycle_arrives_after_a_short_step(tmp_path):
    out = str(tmp_path / "raw")
    run("seed", NUM_EMPLOYEES, SEED, out, date(2026, 4, 1))
    run("increment", None, None, out, date(2026, 9, 30))
    run("increment", None, None, out, date(2026, 10, 1))

    training = _file(out, "training_assignments", "increment", date(2026, 10, 1))
    reviews = _file(out, "performance_reviews", "increment", date(2026, 10, 1))
    assert training
    assert any(r["cycle_date"] == "2026-10-01" for r in training)
    assert reviews


def test_daily_increments_match_a_long_world(tmp_path):
    out = str(tmp_path / "raw")
    employees = 2000
    run("seed", employees, SEED, out, SEED_END)
    for offset in range(1, 15):
        run("increment", None, None, out, SEED_END + timedelta(days=offset))

    long_world = build_world(employees, SEED, "seed",
                             SEED_END + timedelta(days=14),
                             start=add_months(SEED_END, -24), anchor=SEED_END)
    long_rows, _ = datasets.build_rows(long_world)

    for dataset in ("productivity", "training_assignments", "engagement_responses",
                    "performance_reviews", "compensation", "candidates"):
        accumulated = sorted(json.dumps(r, sort_keys=True)
                             for r in read_dataset(out, dataset))
        expected = sorted(json.dumps(r, sort_keys=True) for r in long_rows[dataset])
        assert accumulated == expected, dataset

    new_reqs = [r for r in read_dataset(out, "requisitions")
                if r["opened_date"] > SEED_END.isoformat()]
    opened_during_window = {r["requisition_id"] for r in new_reqs}
    assert opened_during_window
    assert any(c["requisition_id"] in opened_during_window
               and c["stage_date"] > SEED_END.isoformat()
               for c in read_dataset(out, "candidates"))

    latest = {}
    for row in read_dataset(out, "requisitions"):
        if (row["requisition_id"] not in latest
                or row["updated_date"] > latest[row["requisition_id"]]["updated_date"]):
            latest[row["requisition_id"]] = row
    assert sorted(json.dumps(r, sort_keys=True) for r in latest.values()) == \
        sorted(json.dumps(r, sort_keys=True) for r in long_rows["requisitions"])

    accumulated_licences = read_dataset(out, "licenses")
    broken = {r["license_id"] for r in accumulated_licences
              if r["expiry_date"] <= r["issue_date"]}
    assert sorted(json.dumps(r, sort_keys=True) for r in accumulated_licences
                  if r["license_id"] not in broken) == \
        sorted(json.dumps(r, sort_keys=True) for r in long_rows["licenses"]
               if r["license_id"] not in broken)
    assert _file(out, "productivity", "increment", SEED_END + timedelta(days=4))


def test_cli_caps_end_date_and_rejects_seed_overrides(tmp_path):
    out = str(tmp_path / "raw")
    run("seed", NUM_EMPLOYEES, SEED, out, date(2099, 1, 1))
    state = json.load(open(os.path.join(out, "_state", "state.json")))
    assert state["last_date"] == yesterday().isoformat()

    with pytest.raises(SystemExit):
        run("increment", NUM_EMPLOYEES + 1, None, out, yesterday())
    with pytest.raises(SystemExit):
        run("increment", None, SEED + 1, out, yesterday())
