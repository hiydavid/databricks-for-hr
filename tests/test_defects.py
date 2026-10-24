"""The deliberate data-quality defects must appear in the raw files."""

from __future__ import annotations

from datetime import date

from .helpers import as_date, read_dataset, read_manifest


def test_defect_counts(seed_dir):
    manifest = read_manifest(seed_dir)
    expected = manifest["defects"]
    events = read_dataset(seed_dir, "worker_events")
    workers = read_dataset(seed_dir, "workers")
    licenses = read_dataset(seed_dir, "licenses")

    keys = [tuple(sorted(e.items())) for e in events]
    duplicates = len(keys) - len(set(keys))
    assert duplicates == expected["duplicate_worker_events"]

    bad_lines = {w["worker_id"] for w in workers if w["business_line"] not in (
        "Consumer Banking", "Operations", "Wealth Management", "Technology",
        "Commercial Banking", "Corporate Functions")}
    assert len(bad_lines) == expected["unknown_business_line"]

    hire = {w["worker_id"]: as_date(w["hire_date"]) for w in workers}
    early = [e for e in events if e["event_type"] == "termination"
             and e["worker_id"] in hire
             and as_date(e["effective_date"]) < hire[e["worker_id"]]]
    assert len(early) == expected["termination_before_hire"]

    bad_licences = [row for row in licenses
                    if as_date(row["expiry_date"]) <= as_date(row["issue_date"])]
    assert len(bad_licences) == expected["license_expiry_before_issue"]


def test_no_defects_in_unrelated_fields(seed_dir):
    events = read_dataset(seed_dir, "worker_events")
    assert all("business_line" in e for e in events)
    assert date.fromisoformat(events[0]["effective_date"])
