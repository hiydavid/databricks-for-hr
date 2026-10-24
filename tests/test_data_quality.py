"""Realism checks that the planted stories depend on."""

from __future__ import annotations

from generate.rng import sub_rng
from generate.text import ROUTINE_TASK_BANK, exit_comment

from .helpers import as_date, read_dataset, read_manifest


def test_manager_coverage_and_no_self_managers(seed_dir):
    workers = read_dataset(seed_dir, "workers")
    assert sum(1 for w in workers if not w["manager_id"]) / len(workers) < 0.10
    assert not [w for w in workers if w["manager_id"] == w["worker_id"]]

    initial = [e for e in read_dataset(seed_dir, "worker_events")
               if e["event_type"] == "initial_state"]
    assert sum(1 for e in initial if not e["manager_id"]) / len(initial) < 0.10

    reviews = read_dataset(seed_dir, "performance_reviews")
    assert sum(1 for r in reviews if not r["reviewer_id"]) / len(reviews) < 0.10

    workers = {w["worker_id"]: w for w in workers}
    for event in read_dataset(seed_dir, "worker_events"):
        if event["event_type"] != "hire" or not event["manager_id"]:
            continue
        manager = workers[event["manager_id"]]
        if manager["termination_date"]:
            assert manager["termination_date"] >= event["effective_date"]


def test_manager_chain_is_acyclic_and_never_reports_to_a_leaver(seed_dir):
    manifest = read_manifest(seed_dir)
    end = as_date(manifest["end_date"])
    latest = {}
    for w in read_dataset(seed_dir, "workers"):
        if w["worker_id"] not in latest or w["updated_date"] > latest[w["worker_id"]]["updated_date"]:
            latest[w["worker_id"]] = w

    def active(w):
        return not w["termination_date"] or as_date(w["termination_date"]) > end

    for wid, worker in latest.items():
        if not active(worker):
            continue
        seen = set()
        current = worker["manager_id"]
        while current:
            assert current != wid, f"{wid} reports to itself"
            assert current not in seen, f"manager cycle at {wid}"
            seen.add(current)
            manager = latest[current]
            assert not manager["termination_date"] or \
                as_date(manager["termination_date"]) > end, \
                f"{wid} reports to terminated {current}"
            current = manager["manager_id"]

    terminations = {w["worker_id"]: w["termination_date"] for w in latest.values()}
    for event in read_dataset(seed_dir, "worker_events"):
        if event["event_type"] == "manager_change":
            assert terminations[event["worker_id"]] != event["effective_date"]


def test_branch_managers_keep_branch_titles(seed_dir):
    org = {u["org_unit_id"]: u for u in read_dataset(seed_dir, "org_units")}
    workers = read_dataset(seed_dir, "workers")
    branch_managers = [w for w in workers
                       if w["business_line"] == "Consumer Banking"
                       and w["is_manager"]
                       and org[w["site_id"]]["site_type"] == "branch"]
    assert branch_managers
    assert all(w["title"] == "Branch Manager" for w in branch_managers)


def test_requisition_fills_match_the_job_and_are_unique(seed_dir):
    workers = {w["worker_id"]: w for w in read_dataset(seed_dir, "workers")}
    filled = [r for r in read_dataset(seed_dir, "requisitions")
              if r["filled_by_worker_id"]]
    assert filled
    assert all(workers[r["filled_by_worker_id"]]["hire_job_id"] == r["job_id"] for r in filled)
    assert all(workers[r["filled_by_worker_id"]]["team_id"] == r["org_unit_id"] for r in filled)
    assert all(workers[r["filled_by_worker_id"]]["hire_manager_id"] == r["hiring_manager_id"]
               for r in filled)
    assert len({r["filled_by_worker_id"] for r in filled}) == len(filled)


def test_candidate_source_is_stable_and_internal_is_labelled(seed_dir):
    by_candidate = {}
    for row in read_dataset(seed_dir, "candidates"):
        by_candidate.setdefault(row["candidate_id"], set()).add(row["source"])
    assert all(len(sources) == 1 for sources in by_candidate.values())
    for row in read_dataset(seed_dir, "candidates"):
        if row["worker_id"]:
            assert row["source"] == "Internal"


def test_training_skips_leavers_and_has_dated_completion(seed_dir):
    workers = {w["worker_id"]: w for w in read_dataset(seed_dir, "workers")}
    training = read_dataset(seed_dir, "training_assignments")
    for row in training:
        worker = workers[row["worker_id"]]
        if worker["termination_date"]:
            assert row["assigned_date"] < worker["termination_date"]
        assert row["status"] in ("Assigned", "Completed")
        assert bool(row["completed_date"]) == (row["status"] == "Completed")
        if row["status"] == "Completed":
            assert row["completed_date"] <= row["status_date"]
            if worker["termination_date"]:
                assert row["completed_date"] < worker["termination_date"]


def test_reskill_cohort_has_skill_comments(seed_dir):
    manifest = read_manifest(seed_dir)
    cohort = set(manifest["p6_reskill_workers"])
    skills = ("SQL", "process mapping", "data quality", "Excel automation")
    mentioned = {
        r["worker_id"] for r in read_dataset(seed_dir, "performance_reviews")
        if r["worker_id"] in cohort and r["manager_comment"]
        and any(skill in r["manager_comment"] for skill in skills)
    }
    assert len(mentioned) / len(cohort) >= 0.50


def test_open_role_descriptions_are_consultative(seed_dir):
    jobs = read_dataset(seed_dir, "jobs")
    open_titles = {"Process Automation Analyst", "Process Improvement Analyst",
                   "Fraud Data Analyst"}
    for job in jobs:
        if job["title"] in open_titles:
            assert not any(task in job["job_description"] for task in ROUTINE_TASK_BANK)
            assert "SQL" in job["job_description"]


def test_survey_comments_are_varied(seed_dir):
    comments = {r["comment"] for r in read_dataset(seed_dir, "engagement_responses")
                if r["comment"]}
    assert len(comments) >= 50


def test_non_contact_centre_exits_do_not_talk_about_calls():
    for i in range(20):
        text = exit_comment(
            sub_rng(42, "exit-text", i), ["schedule_workload"],
            contact_center=False, site="Technology Center - New York",
            year=2026, months=18, burnout=False,
        ).lower()
        assert "call" not in text
        assert "phone" not in text
