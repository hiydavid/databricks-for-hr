"""Turn a simulated :class:`~generate.world.World` into dataset row lists."""

from __future__ import annotations

from datetime import timedelta

import numpy as np

from . import config as cfg
from . import structure
from . import text as textmod
from .dates import days_between, iso, iter_weeks
from .rng import hash_int, stable_id, sub_rng

# date field used to filter increment output; None means a static dataset.
DATE_FIELD = {
    "org_units": None,
    "jobs": "created_date",
    "pay_bands": None,
    "workers": "updated_date",
    "worker_events": "effective_date",
    "compensation": "effective_date",
    "performance_reviews": "review_date",
    "engagement_responses": "wave_date",
    "exit_interviews": "termination_date",
    "licenses": "status_date",
    "training_assignments": "status_date",
    "requisitions": "updated_date",
    "candidates": "stage_date",
    "productivity": "week_end",
    "site_events": "event_date",
}

STATIC = {"org_units", "pay_bands"}

OVERTIME_BASE = {
    "branch": 1.5, "contact_center": 4.5, "fraud_card_disputes": 5.5,
    "fraud_other": 3.0, "ops_processing": 2.0, "ops_general": 2.0,
    "wealth_ne": 1.0, "wealth_other": 1.0, "tech": 1.0, "tech_ai": 1.0,
    "commercial": 1.2, "corporate": 1.0,
}

OUTPUT_BASE = {
    "branch": 120, "contact_center": 90, "fraud_card_disputes": 70,
    "fraud_other": 80, "ops_processing": 110, "ops_general": 110,
    "wealth_ne": 60, "wealth_other": 60, "tech": 40, "tech_ai": 35,
    "commercial": 55, "corporate": 50,
}

SCHEDULED_HOURS = {"Full-time": 40, "Part-time": 20, "Contractor": 40}


def _active(w: dict, d) -> bool:
    if w["hire_date"] and d < _date(w["hire_date"]):
        return False
    if w["termination_date"] and d >= _date(w["termination_date"]):
        return False
    return True


def _date(s: str):
    from datetime import date
    return date.fromisoformat(s)


def _band_id(line: str, level: int) -> str:
    premium = line in cfg.PREMIUM_LINES
    return f"PB{max(1, min(6, level))}{'H' if premium else ''}"


def build_rows(world) -> dict:
    rows = {}
    rows["pay_bands"] = structure.pay_band_rows()
    rows["workers"] = _workers(world)
    rows["worker_events"] = list(world.events)
    rows["compensation"], ratings = _compensation(world)
    rows["performance_reviews"] = _performance(world, ratings)
    rows["engagement_responses"] = _engagement(world)
    rows["exit_interviews"], ground_truth = _exits(world)
    rows["licenses"] = _licenses(world)
    rows["training_assignments"] = _training(world)
    rows["requisitions"], rows["candidates"] = _recruiting(world)
    rows["productivity"] = _productivity(world)
    rows["site_events"] = _site_events(world)
    rows["org_units"] = list(world.org_units)
    rows["jobs"] = list(world.jobs_catalog.rows)
    return rows, ground_truth


def _workers(world) -> list:
    out = []
    for w in world.workers:
        out.append(dict(
            worker_id=w["worker_id"], first_name=w["first_name"], last_name=w["last_name"],
            work_email=w["work_email"], phone=w["phone"], home_postal_code=w["home_postal_code"],
            hire_date=w["hire_date"], employment_type=w["employment_type"],
            business_line=w["line"], region=w["region"], site_id=w["site_id"],
            team_id=w["team_id"], job_id=w["job_id"], hire_job_id=w["_hire_job_id"],
            manager_id=w["manager_id"],
            hire_manager_id=w["_mgr_history"][0][1] if w["_mgr_history"] else "",
            work_mode=w["work_mode"], status=w["status"],
            termination_date=w["termination_date"], termination_type=w["termination_type"],
            title=w["title"], job_level=w["job_level"], is_manager=w["is_manager"],
            updated_date=w["_updated"],
        ))
    return out


def _compensation(world):
    out = []
    ratings = {}
    for w in world.workers:
        hire = _date(w["hire_date"])
        band_mid = w.get("_band_mid", 50000)
        salary = int(round(band_mid * w["salary_factor"]))
        start = world.start
        events = [(start if hire <= start else hire, salary,
                   "initial" if hire <= start else "hire")]
        changes = []
        for cycle in world.review_cycles:
            if cycle < hire or not _active(w, cycle):
                continue
            rating = _rating_for(world, w, cycle)
            ratings[(w["worker_id"], iso(cycle))] = rating
            changes.append((cycle, "merit", rating))
        for promo in w.get("promotions", []):
            changes.append((_date(promo["date"]), "promotion", promo["level"]))
        # Apply merit and promotion changes in date order. The old code applied
        # every merit raise first, so a promotion followed by a later-dated
        # merit event could show a salary cut.
        changes.sort(key=lambda c: (c[0], 0 if c[1] == "merit" else 1))
        for d, kind, value in changes:
            if kind == "merit":
                mult = 1.0 if w["p2"] else \
                    {1: 1.0, 2: 1.01, 3: 1.025, 4: 1.04, 5: 1.055}[value]
                salary = int(round(salary * mult))
                reason = "merit"
            else:
                band_mid = cfg.PAY_BANDS[_band_id(w["line"], int(value))][1]
                salary = max(int(round(salary * 1.09)), int(round(band_mid * 0.92)))
                reason = "promotion"
            events.append((d, salary, reason))
        events.sort(key=lambda e: e[0])
        for d, sal, reason in events:
            out.append(dict(comp_event_id=stable_id("C", "comp", w["worker_id"], iso(d), reason),
                            worker_id=w["worker_id"],
                            effective_date=iso(d), base_salary=sal, change_reason=reason,
                            business_line=w["line"], region=w["region"]))
        if events:
            w["base_salary"] = events[-1][1]
    return out, ratings


def _rating_for(world, w, cycle) -> int:
    if w["p2"]:
        return 4 if int(sub_rng(world.seed, "p2rating", w["worker_id"], cycle.year).integers(0, 2)) == 0 else 5
    team = world.teams_by_id[w["team_id"]]
    r = sub_rng(world.seed, "rating", w["worker_id"], cycle.year)
    base = int(r.choice([1, 2, 3, 4, 5], p=[0.03, 0.10, 0.42, 0.33, 0.12]))
    if team["p5_team"] and base < 5 and r.random() < 0.5:
        base += 1
    if team["spike_center"] and base > 1 and r.random() < 0.2:
        base -= 1
    return base


def _manager_at(w: dict, d) -> str:
    manager = ""
    for when, mid in w.get("_mgr_history", []):
        if _date(when) <= d:
            manager = mid
        else:
            break
    return manager


def _performance(world, ratings) -> list:
    out = []
    rng = sub_rng(world.seed, "perf")
    for cycle in world.review_cycles:
        for w in world.workers:
            if not _active(w, cycle):
                continue
            rating = ratings.get((w["worker_id"], iso(cycle)))
            if rating is None:
                continue
            review_id = stable_id("R", "review", w["worker_id"], iso(cycle))
            comment = ""
            force_skill = w["p6_reskill"] or w["p2"]
            if force_skill or rng.random() < 0.10:
                band = "high" if rating >= 4 else ("mid" if rating == 3 else "low")
                skill = None
                if w["p6_reskill"]:
                    band = "high" if rating >= 4 else "mid"
                    skill = _pick_skill(rng, ["SQL", "process mapping", "data quality", "Excel automation"])
                elif w["p2"]:
                    skill = _pick_skill(rng, textmod.MANAGER_COMMENT_SKILLS)
                comment = textmod.manager_comment(rng, w["first_name"], band, skill)
            out.append(dict(review_id=review_id, worker_id=w["worker_id"],
                            review_year=cycle.year, rating=rating,
                            reviewer_id=_manager_at(w, cycle),
                            review_date=iso(cycle), manager_comment=comment,
                            business_line=w["line"], region=w["region"]))
    return out


def _pick_skill(rng, options):
    return options[int(rng.integers(0, len(options)))]


def _engagement(world) -> list:
    out = []
    for wave_idx, wave in enumerate(world.waves):
        wave_id = stable_id("W", "wave", iso(wave), width=8)
        recent = wave_idx >= len(world.waves) - 3
        for w in world.workers:
            if not _active(w, wave):
                continue
            r = sub_rng(world.seed, "eng", w["worker_id"], wave_id)
            if r.random() > 0.75:
                continue
            team = world.teams_by_id[w["team_id"]]
            index = 3.6 + r.normal(0, 0.5)
            q_manager = 3.7 + r.normal(0, 0.5)
            q_workload = 3.5 + r.normal(0, 0.5)
            q_growth = 3.4 + r.normal(0, 0.5)
            q_recommend = 3.8 + r.normal(0, 0.5)
            if w["p2"]:
                q_growth -= 0.9
            if team["spike_center"] and wave >= world.change_date:
                index -= 0.5
                q_workload -= 0.7
            if team["wealth_ne"]:
                index -= 0.4
                q_growth -= 0.3
            if team["fraud_card"] and recent:
                index -= 0.6
                q_workload -= 0.5
            if team["p5_team"]:
                index += 0.5
                q_manager += 0.4
            comment = ""
            if r.random() < 0.25:
                keys = _comment_keys(w, team, recent)
                comment = textmod.survey_comment(r, keys)
            out.append(dict(response_id=stable_id("G", "engagement", w["worker_id"], iso(wave)),
                            worker_id=w["worker_id"],
                            wave_id=wave_id, wave_date=iso(wave),
                            engagement_index=round(float(index), 2),
                            q_manager=round(float(q_manager), 2),
                            q_workload=round(float(q_workload), 2),
                            q_growth=round(float(q_growth), 2),
                            q_recommend=round(float(q_recommend), 2),
                            comment=comment, business_line=w["line"], region=w["region"]))
    return out


def _comment_keys(w, team, recent):
    keys = ["positive"]
    if w["p2"]:
        keys += ["growth_negative", "growth_negative"]
    if team["spike_center"]:
        keys += ["schedule_negative", "workload_negative", "schedule_negative"]
    if team["fraud_card"] and recent:
        keys += ["burnout", "burnout", "burnout", "workload_negative"]
    if team["wealth_ne"]:
        keys += ["workload_negative", "growth_negative"]
    if team["p5_team"]:
        keys += ["manager_positive", "manager_positive"]
    keys += ["manager_negative", "pay_negative"]
    return keys


def _exits(world):
    out = []
    ground_truth = []
    for w in world.workers:
        if w["termination_type"] != "voluntary":
            continue
        td = _date(w["termination_date"])
        reasons = w["exit_reasons"] or ["other"]
        months = max(1, months_since(w, td))
        comment = textmod.exit_comment(sub_rng(world.seed, "exit_comment",
                                               w["worker_id"], iso(td)),
                                       reasons,
                                       contact_center=(w["team_profile"] == "contact_center"),
                                       site=w["site_name"], year=td.year, months=months,
                                       burnout=("health_burnout" in reasons))
        out.append(dict(exit_interview_id=stable_id("X", "exit", w["worker_id"], iso(td)),
                        worker_id=w["worker_id"],
                        termination_date=iso(td), interview_date=iso(td - timedelta(days=3)),
                        comment=comment, business_line=w["line"], region=w["region"],
                        site_id=w["site_id"], team_id=w["team_id"]))
        ground_truth.append(dict(worker_id=w["worker_id"], termination_date=iso(td),
                                 primary_reason=reasons[0], reasons=reasons,
                                 team_id=w["team_id"], site_id=w["site_id"],
                                 business_line=w["line"], region=w["region"]))
    return out, ground_truth


def months_since(w, d) -> int:
    hire = _date(w["hire_date"])
    return (d.year - hire.year) * 12 + (d.month - hire.month)


def _licenses(world) -> list:
    """License issuances plus dated status changes.

    A license row is not a snapshot of the run date: it carries ``status_date``
    so an increment can append the transition to Expiring or Expired without
    rewriting the seed. Renewals are new issuances with their own IDs.
    """
    out = []
    for w in world.workers:
        if not w["is_licensed"] or not w["license_type"]:
            continue
        term = cfg.LICENSE_TYPES.get(w["license_type"], 3 * 365)
        rng = sub_rng(world.seed, "licenses", w["worker_id"])
        if w["p3_expiring"]:
            first_expiry = world.anchor + timedelta(days=int(rng.integers(1, 60)))
            first_issue = first_expiry - timedelta(days=term)
        elif w["team_profile"] == "wealth_ne":
            first_expiry = world.anchor + timedelta(days=int(rng.integers(90, max(91, term - 60))))
            first_issue = first_expiry - timedelta(days=term)
        else:
            first_issue = world.start - timedelta(days=int(rng.integers(0, max(1, term - 1))))
            first_expiry = first_issue + timedelta(days=term)
        issuances = []
        issue = first_issue
        while issue <= world.T and len(issuances) < 10:
            expiry = issue + timedelta(days=term)
            issuances.append((issue, expiry))
            if w["p3_expiring"]:
                # The planted gap is a licence that has not been renewed.
                break
            issue = expiry - timedelta(days=30)
        for issue, expiry in issuances:
            lic_id = stable_id("L", "license", w["worker_id"], w["license_type"], iso(issue))
            cursor = max(issue, world.start)
            if cursor > world.T:
                continue
            rows = [(cursor, _license_status(expiry, cursor))]
            for transition in sorted({expiry - timedelta(days=60), expiry}):
                if cursor < transition <= world.T:
                    rows.append((transition, _license_status(expiry, transition)))
            for when, status in rows:
                out.append(dict(
                    license_id=lic_id,
                    license_event_id=stable_id("LE", "license_event", w["worker_id"],
                                               iso(issue), iso(when)),
                    worker_id=w["worker_id"], license_type=w["license_type"],
                    issue_date=iso(issue), expiry_date=iso(expiry), status=status,
                    status_date=iso(when),
                    business_line=w["line"], region=w["region"], site_id=w["site_id"]))
    return out


def _license_status(expiry, when) -> str:
    if when < expiry - timedelta(days=60):
        return "Active"
    if when < expiry:
        return "Expiring"
    return "Expired"


def _training(world) -> list:
    out = []
    mandatory = [c for c in cfg.COURSES if c[1]]
    optional = [c for c in cfg.COURSES if not c[1]]
    for w in world.workers:
        team = world.teams_by_id[w["team_id"]]
        p_complete = 0.60 if team["wealth_ne"] else 0.92
        for cycle_index, cycle in enumerate(world.review_cycles):
            assigned = cycle - timedelta(days=60)
            if assigned < _date(w["hire_date"]) or not _active(w, assigned):
                continue
            # Rotate the optional courses so all eight appear across cycles.
            chosen_optional = [optional[(2 * cycle_index + k) % len(optional)]
                               for k in range(2)]
            courses = mandatory + chosen_optional
            for course_name, is_mandatory, topic in courses:
                due = assigned + timedelta(days=90)
                r = sub_rng(world.seed, "course", w["worker_id"], course_name, iso(cycle))
                done = (assigned + timedelta(days=int(r.integers(1, 89)))
                        if r.random() < p_complete else None)
                if done is not None and w["termination_date"] \
                        and done >= _date(w["termination_date"]):
                    done = None
                assignment_id = stable_id("A", "assignment", w["worker_id"],
                                          course_name, iso(assigned))
                statuses = [(cycle, "Assigned", "")]
                if done is not None and done <= cycle:
                    statuses = [(cycle, "Completed", iso(done))]
                elif done is not None and done <= world.T:
                    statuses.append((done, "Completed", iso(done)))
                for status_date, status, completed in statuses:
                    out.append(dict(
                        assignment_id=assignment_id,
                        assignment_event_id=stable_id("AE", "assignment_event", assignment_id,
                                                      iso(status_date), status),
                        worker_id=w["worker_id"],
                        course_id=f"CO{hash_int('course', course_name) % 1000:03d}",
                        course_name=course_name, is_mandatory=is_mandatory,
                        regulatory_topic=topic, assigned_date=iso(assigned),
                        due_date=iso(due), cycle_date=iso(cycle),
                        status=status, status_date=iso(status_date),
                        completed_date=completed,
                        business_line=w["line"], region=w["region"], site_id=w["site_id"]))
    return out


OPEN_ROLE_TITLES = [("Process Automation Analyst", "Operations", 3),
                    ("Process Improvement Analyst", "Operations", 3),
                    ("Fraud Data Analyst", "Operations", 4)]


def _recruiting(world):
    reqs = []
    cands = []
    regions = cfg.REGIONS
    for title, line, level in OPEN_ROLE_TITLES:
        for region in regions:
            world.jobs_catalog.get(line, title, level, region, created_date=world.start)

    open_jobs = []
    for i, (title, line, level) in enumerate(OPEN_ROLE_TITLES):
        region = regions[i % len(regions)]
        open_jobs.append(world.jobs_catalog.get(line, title, level, region,
                                                created_date=world.start))
    # Build a fixed catalogue at the seed start. Reading the live catalogue
    # here would make earlier requisitions pick different jobs as later
    # increments create new job rows.
    catalog = []
    for line, titles in cfg.JOB_TITLES.items():
        for title, _family, level, _mgr, _licensed, _lic_type in titles:
            for region in regions:
                jid = world.jobs_catalog.get(line, title, level, region,
                                             created_date=world.start)
                catalog.append(catalog_by_id(world.jobs_catalog.rows, jid))
    all_jobs = {j["job_id"]: j for j in world.jobs_catalog.rows}
    fillable_ids = {w["_hire_job_id"] for w in world.workers
                    if w["hire_date"] <= iso(world.anchor)}
    wealth_jobs = [j for j in catalog
                   if j["business_line"] == "Wealth Management"
                   and j["is_licensed_role"] and j["job_id"] in fillable_ids]
    open_titles = {title for title, _line, _level in OPEN_ROLE_TITLES}
    other_jobs = [j for j in catalog
                  if not (j["business_line"] == "Wealth Management" and j["is_licensed_role"])
                  and j["title"] not in open_titles and j["job_id"] in fillable_ids]
    wealth_jobs = wealth_jobs or [j for j in catalog
                                  if j["business_line"] == "Wealth Management"
                                  and j["is_licensed_role"]]
    other_jobs = other_jobs or [j for j in catalog if j["title"] not in open_titles]

    n_open = world.sizes["p6_open_reqs"]
    plans = []

    # The planted open roles are anchored to the seed end date.
    for i in range(n_open):
        r = sub_rng(world.seed, "open_req", i)
        opened = world.anchor - timedelta(days=int(r.integers(20, 120)))
        job = catalog_by_id(catalog, open_jobs[i % len(open_jobs)])
        plans.append((opened, job, int(r.integers(365, 540)), f"open{i}", "", None))

    # A requisition opens when the vacancy is scheduled, not when the hire
    # lands. Candidate stages therefore fall inside the open window and can be
    # written by the increment that reaches each stage.
    for vacancy in world.vacancies:
        opened = _date(vacancy["opened_date"])
        if opened > world.T:
            continue
        job = all_jobs.get(vacancy["job_id"])
        if job is None:
            continue
        expected = _date(vacancy["expected_hire_date"])
        plans.append((opened, job, days_between(opened, expected),
                      f"vacancy:{vacancy['vacancy_id']}", vacancy["filled_by_worker_id"],
                      vacancy))

    # A small cancelled stream gives expectations something to reject without
    # inflating cancellations when a filler happens to be unavailable.
    seed_vacancies = [v for v in world.vacancies if v["opened_date"] <= iso(world.anchor)]
    cancel_rate = (0.25 * len(seed_vacancies)
                   / max(1, days_between(world.start, world.anchor)))
    for offset in range(days_between(world.start, world.T) + 1):
        d = world.start + timedelta(days=offset)
        r = sub_rng(world.seed, "cancel_req", iso(d))
        if r.random() >= cancel_rate:
            continue
        licensed = r.random() < 0.15
        job = (wealth_jobs[int(r.integers(0, len(wealth_jobs)))] if licensed
               else other_jobs[int(r.integers(0, len(other_jobs)))])
        ttf = cfg.TTF_LICENSED_DAYS if licensed else cfg.TTF_OTHER_DAYS
        plans.append((d, job, int(max(7, ttf + r.normal(0, 8))), f"cancel{offset}", "", None))

    for opened, job, ttf, tag, filled, vacancy in sorted(
            plans, key=lambda p: (p[0], p[1]["job_id"], p[3])):
        if opened > world.T:
            continue
        if vacancy:
            closed = _date(vacancy["closed_date"]) if filled else None
            status = "Filled" if filled else "Open"
            manager_id = vacancy["manager_id"]
            org_unit = vacancy["org_unit_id"]
            fill_date = closed
        else:
            closed = opened + timedelta(days=ttf)
            if closed > world.T:
                status, closed = "Open", None
            else:
                status = "Cancelled"
            manager = _requisition_manager(world, job, opened, tag)
            manager_id = manager["worker_id"] if manager else ""
            org_unit = manager["team_id"] if manager else world.line_units[job["business_line"]]
            fill_date = None
        req_id = stable_id("Q", "requisition", job["job_id"], iso(opened), tag)
        updated = closed or opened
        if fill_date and fill_date > updated:
            updated = fill_date
        reqs.append(dict(requisition_id=req_id, job_id=job["job_id"],
                         org_unit_id=org_unit,
                         hiring_manager_id=manager_id,
                         opened_date=iso(opened),
                         closed_date=iso(closed) if closed else "", status=status,
                         filled_by_worker_id=filled,
                         updated_date=iso(updated),
                         business_line=job["business_line"], region=job["region"]))
        cand_rng = sub_rng(world.seed, "req_candidates", req_id)
        n_cand = (int(cand_rng.integers(3, 13)) if not job["is_licensed_role"]
                  else int(cand_rng.integers(2, 6)))
        _candidates(world, cands, req_id, job, opened, n_cand, close_date=closed)
    return reqs, cands


def catalog_by_id(rows, job_id):
    return next(j for j in rows if j["job_id"] == job_id)


def _requisition_manager(world, job, opened, req_id):
    managers = [w for w in world.workers
                if w.get("_initial_is_manager", w["is_manager"])
                and w["line"] == job["business_line"]
                and _active(w, opened)]
    if not managers:
        return None
    rng = sub_rng(world.seed, "req_manager", req_id)
    return managers[int(rng.integers(0, len(managers)))]


def _candidates(world, cands, req_id, job, opened, n_cand, close_date=None):
    stages = ["Applied", "Screening", "Interview", "Offer"]
    pool = sorted([w for w in world.workers
                   if w["line"] == job["business_line"]
                   and w["region"] == job["region"]
                   and not w.get("_initial_is_manager", w["is_manager"])
                   and w["hire_date"] <= iso(world.start)],
                  key=lambda w: w["worker_id"])
    # The eventual progress is drawn when the requisition opens. Whether a
    # later stage is visible depends only on the run's end date, so an
    # increment reveals the next stage instead of redrawing the pipeline.
    limit = min(world.T, close_date) if close_date else world.T
    for c in range(n_cand):
        rng = sub_rng(world.seed, "candidate", req_id, c)
        progress = int(rng.integers(0, 4))
        if job["is_licensed_role"]:
            progress = min(progress, int(rng.integers(0, 2)))
        offset = 0
        internal = pool and rng.random() < 0.15
        internal_id = ""
        if internal:
            applied = opened + timedelta(days=int(rng.integers(1, 8)))
            w = pool[hash_int("internal", req_id, c) % len(pool)]
            if _active(w, applied):
                internal_id = w["worker_id"]
        source = "Internal" if internal_id else _pick_source(rng)
        for s in range(progress + 1):
            # Cumulative offsets keep the stages in order.
            offset += int(rng.integers(2, 20)) + int(rng.integers(0, 5))
            stage_date = opened + timedelta(days=offset)
            if stage_date > limit:
                break
            cands.append(dict(
                candidate_id=stable_id("N", "candidate", req_id, c),
                requisition_id=req_id, worker_id=internal_id,
                stage=stages[s], stage_date=iso(stage_date),
                source=source,
                business_line=job["business_line"], region=job["region"]))


def _pick_source(rng):
    return ["Referral", "LinkedIn", "Careers Site", "Agency"][int(rng.integers(0, 4))]


def _productivity(world) -> list:
    out = []
    # Only write weeks that have finished by T. A week starting on T would
    # contain days the generator has not simulated yet.
    weeks = [ws for ws in iter_weeks(world.start, world.T)
             if ws + timedelta(days=6) <= world.T]
    for ws in weeks:
        for w in world.workers:
            if not _active(w, ws):
                continue
            team = world.teams_by_id[w["team_id"]]
            r = sub_rng(world.seed, "prod", w["worker_id"], iso(ws))
            base_ot = OVERTIME_BASE[team["profile"]]
            mult = 1.0
            if team["spike_center"] and ws >= world.change_date:
                mult *= 1.4
            if team["fraud_card"] and ws >= world.burnout_start:
                mult *= 1.6
            if team["wealth_ne"]:
                mult *= 1.25
            ot = max(0.0, base_ot * mult + r.normal(0, 1.2))
            sched = SCHEDULED_HOURS[w["employment_type"]]
            ot = round(min(ot, sched * 0.6), 1)
            out.append(dict(worker_id=w["worker_id"], week_start=iso(ws),
                            week_end=iso(ws + timedelta(days=6)),
                            scheduled_hours=sched, overtime_hours=ot,
                            output_units=int(round(OUTPUT_BASE[team["profile"]] * (1 + r.normal(0, 0.15)))),
                            business_line=w["line"], region=w["region"], team_id=w["team_id"]))
    return out


def _site_events(world) -> list:
    out = []
    for site in world.sites:
        if "contact_center_spike" in site["tags"]:
            out.append(dict(site_event_id=stable_id("S", "site", site["site_id"],
                                                    "schedule_change", iso(world.change_date)),
                            org_unit_id=site["site_id"],
                            event_date=iso(world.change_date), event_type="schedule_change",
                            description=f"Contact centre schedule change: rotating shifts "
                                        f"introduced at {site['name']}.",
                            business_line=site["line"], region=site["region"]))
    rng = sub_rng(world.seed, "siteevents")
    extras = [("system_migration", "Core banking platform upgrade window"),
              ("office_refresh", "Site refresh and desk reconfiguration"),
              ("policy_update", "Updated contact handling policy issued")]
    for event_type, description in extras:
        site = world.sites[int(rng.integers(0, len(world.sites)))]
        span = max(31, days_between(world.start, world.anchor) - 30)
        d = world.start + timedelta(days=int(rng.integers(30, span)))
        out.append(dict(site_event_id=stable_id("S", "site", site["site_id"],
                                                event_type, iso(d)),
                        org_unit_id=site["site_id"],
                        event_date=iso(d), event_type=event_type, description=description,
                        business_line=site["line"], region=site["region"]))
    return out


# ---------------------------------------------------------------- defects
def apply_defects(world, rows, ground_truth, rng):
    defects = world.defects
    events = rows["worker_events"]

    # duplicate events: exact copies so silver can dedupe
    n = min(defects["duplicate_worker_events"], len(events))
    idx = rng.permutation(len(events))[:n]
    for i in idx:
        events.append(dict(events[int(i)]))

    # unknown business line
    unsigned = [w for w in world.workers]
    picks = rng.permutation(len(unsigned))[:defects["unknown_business_line"]]
    bad_ids = {unsigned[int(i)]["worker_id"] for i in picks}
    for row in rows["workers"]:
        if row["worker_id"] in bad_ids:
            row["business_line"] = "Retail Banking"
    for row in events:
        if row["worker_id"] in bad_ids:
            row["business_line"] = "Retail Banking"

    # termination before hire
    terminated = [w for w in world.workers if w["termination_date"]]
    picks = rng.permutation(len(terminated))[:defects["termination_before_hire"]]
    for i in picks:
        w = terminated[int(i)]
        d = _date(w["hire_date"]) - timedelta(days=int(rng.integers(5, 40)))
        events.append(dict(event_id=stable_id("E", "defect", w["worker_id"], "termination_before_hire"),
                           event_seq=9,
                           worker_id=w["worker_id"],
                           event_type="termination", effective_date=iso(d), job_id=w["job_id"],
                           org_unit_id=w["team_id"], manager_id=w["manager_id"],
                           business_line=w["line"], region=w["region"], work_mode=w["work_mode"],
                           termination_type="voluntary", last_promotion_date=""))

    # license expiry before issue
    licenses = rows["licenses"]
    if licenses:
        n = min(defects["license_expiry_before_issue"], len(licenses))
        idx = rng.permutation(len(licenses))[:n]
        for i in idx:
            row = licenses[int(i)]
            row["expiry_date"] = iso(_date(row["issue_date"]) - timedelta(days=int(rng.integers(1, 90))))
            row["status"] = "Expired"
