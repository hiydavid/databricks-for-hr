"""Each planted pattern must be detectable in the raw files at 500 employees."""

from __future__ import annotations

from collections import Counter
from datetime import timedelta

from generate import config as cfg

from .helpers import (active_at, as_date, read_dataset, read_manifest,
                      voluntary_exits_after)


def _change_date(seed_dir):
    for e in read_dataset(seed_dir, "site_events"):
        if e["event_type"] == "schedule_change":
            return as_date(e["event_date"])
    raise AssertionError("no schedule_change site event")


def test_p1_contact_center_attrition_spike(seed_dir):
    manifest = read_manifest(seed_dir)
    events = read_dataset(seed_dir, "worker_events")
    change = _change_date(seed_dir)
    spike = set(manifest["p1_spike_team_ids"])
    control = set(manifest["p1_control_team_ids"])

    spike_base = active_at(events, spike, change)
    control_base = active_at(events, control, change)
    spike_exits = voluntary_exits_after(events, spike, change)
    control_exits = voluntary_exits_after(events, control, change)
    assert spike_base and control_base
    spike_rate = len(spike_exits) / len(spike_base)
    control_rate = len(control_exits) / len(control_base)
    # At 500 employees the control site has only a handful of people, so a
    # zero-exit control sample is a small-sample outcome rather than evidence
    # against the pattern. Fall back to the modelled contact-centre baseline.
    elapsed = (as_date(manifest["end_date"]) - change).days / 365.0
    modelled = 1.0 - (1.0 - cfg.VOL_ATTRITION_BY_SEGMENT["Contact Center"]) ** elapsed
    baseline = max(control_rate, modelled)
    assert spike_rate >= 2.0 * baseline, (spike_rate, control_rate, modelled)

    # 70% of post-change exit interviews there give schedule and workload
    gt = read_dataset(seed_dir, "_ground_truth/exit_reasons")
    spike_gt = [g for g in gt if g["team_id"] in spike
                and as_date(g["termination_date"]) > change]
    reasons = Counter(r for g in spike_gt for r in g["reasons"])
    assert reasons
    assert reasons.most_common(1)[0][0] == "schedule_workload"

    # The planted manager change must stay attached to people who leave later.
    workers = {w["worker_id"]: w for w in read_dataset(seed_dir, "workers")}
    changes = {e["worker_id"] for e in events
               if e["event_type"] == "manager_change"
               and as_date(e["effective_date"]) <= change}
    planted = set(manifest["p1_team_ids"])
    leavers = [e for e in voluntary_exits_after(events, planted, change)
               if as_date(workers[e["worker_id"]]["hire_date"]) <= change]
    assert leavers
    assert all(e["worker_id"] in changes for e in leavers)


def test_p2_under_recognised_high_performers(seed_dir):
    manifest = read_manifest(seed_dir)
    workers = {w["worker_id"]: w for w in read_dataset(seed_dir, "workers")}
    reviews = read_dataset(seed_dir, "performance_reviews")
    comp = read_dataset(seed_dir, "compensation")
    jobs = {j["job_id"]: j for j in read_dataset(seed_dir, "jobs")}
    bands = {b["pay_band_id"]: b for b in read_dataset(seed_dir, "pay_bands")}
    end = as_date(manifest["end_date"])

    p2 = manifest["p2_workers"]
    assert len(p2) >= 1
    initial = {e["worker_id"]: e for e in read_dataset(seed_dir, "worker_events")
               if e["event_type"] == "initial_state"}
    for wid in p2:
        ratings = [r["rating"] for r in reviews if r["worker_id"] == wid]
        assert ratings and min(ratings) >= 4
        assert as_date(workers[wid]["hire_date"]) < end
        promo = initial[wid]["last_promotion_date"]
        assert promo and as_date(promo) >= as_date(workers[wid]["hire_date"])
    # salary below 92% of band midpoint
    for wid in p2:
        w = workers[wid]
        band = bands[jobs[w["job_id"]]["pay_band_id"]]
        latest = max((c for c in comp if c["worker_id"] == wid),
                     key=lambda c: c["effective_date"])
        assert latest["base_salary"] < 0.92 * band["band_mid"]


def test_p3_wealth_northeast_licence_gap(seed_dir):
    manifest = read_manifest(seed_dir)
    end = as_date(manifest["end_date"])
    licenses = read_dataset(seed_dir, "licenses")

    def expiring(row):
        return end <= as_date(row["expiry_date"]) <= end + timedelta(days=60)

    ne = [row for row in licenses
          if row["business_line"] == "Wealth Management" and row["region"] == "Northeast"]
    rest = [row for row in licenses
            if row["business_line"] == "Wealth Management" and row["region"] != "Northeast"]
    assert ne and rest
    ne_share = sum(1 for r in ne if expiring(r)) / len(ne)
    rest_share = sum(1 for r in rest if expiring(r)) / len(rest)
    assert ne_share > 0
    assert ne_share >= 3.0 * max(rest_share, 1e-9), (ne_share, rest_share)

    # overdue mandatory training concentrates in Wealth Northeast
    latest_training = {}
    for row in read_dataset(seed_dir, "training_assignments"):
        if as_date(row["status_date"]) > end:
            continue
        key = row["assignment_id"]
        if key not in latest_training or row["status_date"] > latest_training[key]["status_date"]:
            latest_training[key] = row
    training = list(latest_training.values())

    def overdue(row):
        return row["is_mandatory"] and not row["completed_date"] and as_date(row["due_date"]) < end

    ne_mand = [r for r in training if r["business_line"] == "Wealth Management"
               and r["region"] == "Northeast" and r["is_mandatory"]]
    other_mand = [r for r in training if not (r["business_line"] == "Wealth Management"
                                              and r["region"] == "Northeast") and r["is_mandatory"]]
    ne_overdue = sum(1 for r in ne_mand if overdue(r)) / max(1, len(ne_mand))
    other_overdue = sum(1 for r in other_mand if overdue(r)) / max(1, len(other_mand))
    assert ne_overdue >= 2.0 * other_overdue, (ne_overdue, other_overdue)


def test_p4_fraud_operations_burnout(seed_dir):
    manifest = read_manifest(seed_dir)
    card = set(manifest["p4_team_ids"])
    other = set(manifest["fraud_other_team_ids"])
    productivity = read_dataset(seed_dir, "productivity")

    def mean_ot(teams, cutoff):
        vals = [r["overtime_hours"] for r in productivity
                if r["team_id"] in teams and as_date(r["week_start"]) >= cutoff]
        assert vals
        return sum(vals) / len(vals)

    end = as_date(manifest["end_date"])
    card_ot = mean_ot(card, end - timedelta(days=183))
    other_ot = mean_ot(other, end - timedelta(days=183))
    assert card_ot >= 1.5 * other_ot, (card_ot, other_ot)


def test_p5_standout_managers(seed_dir):
    manifest = read_manifest(seed_dir)
    p5 = set(manifest["p5_team_ids"])
    engagement = read_dataset(seed_dir, "engagement_responses")
    assert p5
    events = read_dataset(seed_dir, "worker_events")
    team_of = {}
    for e in events:
        team_of.setdefault(e["worker_id"], e["org_unit_id"])
    p5_index = [r["engagement_index"] for r in engagement if team_of.get(r["worker_id"]) in p5]
    overall = [r["engagement_index"] for r in engagement]
    assert p5_index
    assert sum(p5_index) / len(p5_index) > sum(overall) / len(overall)


def test_p6_generative_ai_exposure(seed_dir):
    from generate.text import ROUTINE_TASK_BANK

    jobs = read_dataset(seed_dir, "jobs")
    texts = " ".join(j["job_description"] for j in jobs).lower()
    for skill in ("sql", "process mapping", "data quality", "excel automation"):
        assert skill in texts
    processing_titles = [j for j in jobs
                         if j["title"] in ("Loan Operations Processor", "Payments Operations Analyst",
                                           "Deposit Operations Analyst")]
    assert processing_titles
    for j in processing_titles:
        hits = sum(1 for task in ROUTINE_TASK_BANK if task in j["job_description"])
        assert hits >= 3, j["job_description"]
    manifest = read_manifest(seed_dir)
    assert len(manifest["p6_reskill_workers"]) >= 1


def test_p7_licensed_hiring_is_slow(seed_dir):
    reqs = read_dataset(seed_dir, "requisitions")
    jobs = {j["job_id"]: j for j in read_dataset(seed_dir, "jobs")}
    licensed, other = [], []
    for r in reqs:
        if not r["closed_date"]:
            continue
        days = (as_date(r["closed_date"]) - as_date(r["opened_date"])).days
        (licensed if jobs[r["job_id"]]["is_licensed_role"] else other).append(days)
    assert licensed and other
    assert sum(licensed) / len(licensed) >= 1.3 * (sum(other) / len(other))
