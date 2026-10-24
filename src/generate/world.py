"""The simulated bank: topology, 24 months of workforce history and datasets.

The simulation is day-stepped so ``increment`` mode can resume from `_state/`.
Every worker gets a per-day uniform array seeded from ``(seed, worker_id)`` so
runs are reproducible and daily draws stay stable as the window grows.
"""

from __future__ import annotations

from datetime import date, timedelta

import numpy as np

from . import config as cfg
from . import structure
from .dates import add_days, add_months, days_between, iso
from .names import FIRST_NAMES, LAST_NAMES
from .rng import hash_int, stable_id, sub_rng

PROFILE_SEGMENT = {
    "branch": "Branch",
    "contact_center": "Contact Center",
    "fraud_card_disputes": "Fraud Operations",
    "fraud_other": "Fraud Operations",
    "ops_processing": "Operations",
    "ops_general": "Operations",
    "wealth_ne": "Wealth",
    "wealth_other": "Wealth",
    "tech": "Technology",
    "tech_ai": "Data & AI",
    "commercial": "Commercial",
    "corporate": "Corporate",
}

REASON_WEIGHTS = [
    ("compensation", 0.25),
    ("career_growth", 0.20),
    ("schedule_workload", 0.12),
    ("manager_relationship", 0.15),
    ("relocation_personal", 0.10),
    ("health_burnout", 0.06),
    ("other", 0.12),
]

SPAN = 8

EVENT_ORDER = {
    "initial_state": 0,
    "hire": 1,
    "manager_change": 2,
    "transfer": 3,
    "promotion": 4,
    "job_change": 5,
    "termination": 9,
}


def annual_to_daily(annual: float) -> float:
    return 1.0 - (1.0 - annual) ** (1.0 / 365.0)


def proportional(weights, total: int) -> list:
    s = float(sum(weights))
    if s <= 0 or total <= 0:
        return [0] * len(weights)
    raw = [total * w / s for w in weights]
    floors = [int(x) for x in raw]
    rem = total - sum(floors)
    order = sorted(range(len(weights)), key=lambda i: (-(raw[i] - floors[i]), i))
    for i in order[:rem]:
        floors[i] += 1
    return floors


def _pick(rng: np.random.Generator, options, weights):
    p = np.asarray(weights, dtype=float)
    p = p / p.sum()
    return options[int(rng.choice(len(options), p=p))]


class World:
    def __init__(self, num_employees: int, seed: int, end_date: date,
                 mode: str = "seed", start: date = None, anchor: date = None):
        self.n = int(num_employees)
        self.seed = int(seed)
        self.mode = mode
        self.T = end_date
        self._start = start
        # The seed end date. Pattern dates and slow-changing history are
        # anchored here, never to the current run's end date, so extending the
        # window reproduces the past instead of rewriting it.
        self.anchor = anchor or end_date
        self.sizes = cfg.pattern_sizes(self.n)
        self.defects = cfg.defect_counts(self.n)
        self.jobs_catalog = structure.JobCatalog()
        self.org_units = []
        self.teams = []
        self.teams_by_id = {}
        self.workers = []
        self.workers_by_id = {}
        self.events = []
        self.pending_hires = {}
        self.vacancies = []
        self.vacancies_by_id = {}
        self._u_exit = {}
        self._u_promo = {}
        self._counters = {"worker": 0, "org": 0}
        self.manifest = {}

    def _next(self, kind: str, width: int) -> str:
        self._counters[kind] += 1
        return f"{kind[0].upper()}{self._counters[kind]:0{width}d}"

    def _next_org_id(self) -> str:
        return self._next("org", 5)

    def _next_worker_id(self) -> str:
        return self._next("worker", 6)

    def _backfill_worker_id(self, terminated_id: str, d: date) -> str:
        return f"W{hash_int(self.seed, 'backfill', terminated_id, iso(d)) % 1_000_000_000:09d}"

    # ------------------------------------------------------------------ setup
    def build_static(self):
        self.start = self._start or add_months(self.T, -24)
        self.change_date = add_months(self.anchor, -8)
        self.burnout_start = add_months(self.anchor, -6)
        self.review_cycles = [add_months(self.anchor, -18), add_months(self.anchor, -6)]
        while add_months(self.review_cycles[-1], 12) <= self.T:
            self.review_cycles.append(add_months(self.review_cycles[-1], 12))
        self.waves = [add_months(self.anchor, -3 * (k + 1)) for k in range(8)]
        self.waves = sorted(self.waves + self._forward_months(self.anchor, 3, self.T))
        self.sites = structure.plan_sites(self.n, self.sizes)

        company_id = self._next_org_id()
        self.org_units.append(dict(org_unit_id=company_id, name="Aita Bank", unit_type="company",
                                   parent_org_unit_id="", business_line="", region="",
                                   site_type="", city="", state=""))
        self.line_units = {}
        for line in cfg.BUSINESS_LINES:
            uid = self._next_org_id()
            self.org_units.append(dict(org_unit_id=uid, name=f"{line} Division",
                                       unit_type="business_line", parent_org_unit_id=company_id,
                                       business_line=line, region="", site_type="", city="", state=""))
            self.line_units[line] = uid
        for site in self.sites:
            site["site_id"] = self._next_org_id()
            self.org_units.append(dict(org_unit_id=site["site_id"], name=site["name"],
                                       unit_type="site", parent_org_unit_id=self.line_units[site["line"]],
                                       business_line=site["line"], region=site["region"],
                                       site_type=site["site_type"], city=site["city"], state=site["state"]))
        self.sites_by_id = {s["site_id"]: s for s in self.sites}

    def _forward_months(self, start: date, step: int, end: date) -> list:
        out = []
        cur = add_months(start, step)
        while cur <= end:
            out.append(cur)
            cur = add_months(cur, step)
        return out

    # -------------------------------------------------------------- workforce
    def create_initial_workers(self):
        rng = sub_rng(self.seed, "workforce")
        line_counts = cfg.headcount_by_line(self.n)
        assignments = []
        for line, count in line_counts.items():
            assignments += [line] * count
        order = rng.permutation(len(assignments))
        self.work_order = [assignments[int(i)] for i in order]
        self._make_workers(len(self.work_order), rng, self.start)

    def _make_workers(self, count: int, rng: np.random.Generator, not_before: date):
        for _ in range(count):
            wid = self._next_worker_id()
            first = _pick(rng, FIRST_NAMES, [1.0] * len(FIRST_NAMES))
            last = _pick(rng, LAST_NAMES, [1.0] * len(LAST_NAMES))
            phone = "(" + str(int(rng.integers(200, 999))) + ") " + \
                    str(int(rng.integers(200, 999))) + "-" + f"{int(rng.integers(0, 9999)):04d}"
            postal = f"{int(rng.integers(1000, 99999)):05d}"
            tenure_days = int(rng.integers(30, 365 * 11))
            hire = not_before - timedelta(days=tenure_days)
            emp = _pick(rng, [x for x, _ in cfg.EMPLOYMENT_TYPE_WEIGHTS],
                        [x for _, x in cfg.EMPLOYMENT_TYPE_WEIGHTS])
            w = dict(
                worker_id=wid, first_name=first, last_name=last,
                work_email=f"{first.lower()}.{last.lower()}{int(rng.integers(10, 99))}@aitabank.example",
                phone=phone, home_postal_code=postal, hire_date=iso(hire),
                employment_type=emp,
                line="", region="", site_id="", site_name="", city="", state="",
                team_id="", team_profile="", manager_id="",
                job_id="", title="", job_level=0, is_licensed=False, license_type="",
                work_mode="", salary_factor=1.0, base_salary=0,
                last_promotion_date="", status="active",
                termination_date="", termination_type="",
                exit_reason="", exit_reasons=[],
                p2=False, p3_expiring=False, p6_reskill=False, p6_processing=False,
                is_manager=False, start_index=days_between(self.start, hire), promotions=[],
                _updated=iso(hire), _mgr_history=[(iso(hire), "")],
            )
            self.workers.append(w)
            self.workers_by_id[wid] = w

    def assign_workers(self):
        rng = sub_rng(self.seed, "assign")
        by_line = {line: [] for line in cfg.BUSINESS_LINES}
        for i, w in enumerate(self.workers):
            by_line[self.work_order[i]].append(w)
        for line, ws in by_line.items():
            sites = [s for s in self.sites if s["line"] == line]
            alloc = proportional([s["target_size"] for s in sites], len(ws))
            idx = 0
            for site, cnt in zip(sites, alloc):
                self._assign_site(ws[idx:idx + cnt], site, rng)
                idx += cnt
            if idx < len(ws):
                biggest = max(sites, key=lambda s: s["target_size"])
                self._assign_site(ws[idx:], biggest, rng)

    def _site_profiles(self, site: dict):
        profiles, weights = [], []
        if site["site_type"] == "operations_center":
            card = self.sizes["p4_card_disputes"]
            fraud_total = self.sizes["p4_fraud_total"]
            processing = self.sizes["p6_processing"]
            ops_hc = int(round(self.n * cfg.LINE_SHARE["Operations"]))
            rest = max(1, ops_hc - fraud_total - processing)
            if "fraud_card_disputes" in site["tags"]:
                profiles.append("fraud_card_disputes")
                weights.append(card)
            if "fraud_other" in site["tags"]:
                profiles.append("fraud_other")
                weights.append(max(1, fraud_total - card))
            if "ops_processing" in site["tags"]:
                profiles.append("ops_processing")
                weights.append(processing)
            if "ops_general" in site["tags"]:
                profiles.append("ops_general")
                weights.append(rest)
        else:
            profiles.append(site["profile"])
            weights.append(1)
        return profiles, weights

    def _assign_site(self, workers: list, site: dict, rng: np.random.Generator):
        profiles, weights = self._site_profiles(site)
        alloc = proportional(weights, len(workers))
        idx = 0
        for profile, cnt in zip(profiles, alloc):
            group = workers[idx:idx + cnt]
            idx += cnt
            self._assign_profile(group, site, profile, rng)
        if idx < len(workers):
            self._assign_profile(workers[idx:], site, profiles[0], rng)

    def _assign_profile(self, workers: list, site: dict, profile: str, rng: np.random.Generator):
        if not workers:
            return
        n_teams = max(1, int(round(len(workers) / SPAN)))
        team_mgr_title = _team_manager_title(profile, site["line"])
        director_title = _director_title(profile, site["line"])
        team_ids = []
        for k in range(n_teams):
            tid = self._next_org_id()
            team = dict(team_id=tid, site_id=site["site_id"], profile=profile,
                        line=site["line"], region=site["region"], site_name=site["name"],
                        city=site["city"], state=site["state"], site_type=site["site_type"],
                        members=[], manager_id="",
                        spike_center=("contact_center_spike" in site["tags"]),
                        spike_mgr_team=False,
                        fraud_card=(profile == "fraud_card_disputes"),
                        p5_team=False,
                        wealth_ne=(profile == "wealth_ne"))
            self.teams.append(team)
            self.teams_by_id[tid] = team
            self.org_units.append(dict(org_unit_id=tid, name=f"{site['name']} Team {k + 1}",
                                       unit_type="team", parent_org_unit_id=site["site_id"],
                                       business_line=site["line"], region=site["region"],
                                       site_type=site["site_type"], city=site["city"], state=site["state"]))
            team_ids.append(tid)

        n_mgrs = len(team_ids)
        managers = workers[:n_mgrs]
        members = workers[n_mgrs:]
        for k, (mgr, tid) in enumerate(zip(managers, team_ids)):
            team = self.teams_by_id[tid]
            title = director_title if (k == 0 and n_mgrs > 1) else team_mgr_title
            self._place_worker(mgr, team, site, title=title)
            team["manager_id"] = mgr["worker_id"]
        for k, w in enumerate(members):
            team = self.teams_by_id[team_ids[k % n_teams]]
            self._place_worker(w, team, site)
        for team in (self.teams_by_id[tid] for tid in team_ids):
            for wid in team["members"]:
                w = self.workers_by_id[wid]
                if wid != team["manager_id"] and not w["manager_id"]:
                    w["manager_id"] = team["manager_id"]
                    w["_mgr_history"] = [(w["hire_date"], team["manager_id"])]
        if n_mgrs > 1:
            director_id = self.teams_by_id[team_ids[0]]["manager_id"]
            for tid in team_ids[1:]:
                mgr = self.workers_by_id[self.teams_by_id[tid]["manager_id"]]
                mgr["manager_id"] = director_id
                mgr["_mgr_history"] = [(mgr["hire_date"], director_id)]

    def _place_worker(self, w: dict, team: dict, site: dict, title: str = None):
        rng = sub_rng(self.seed, "place", w["worker_id"])
        profile = team["profile"]
        if title is None:
            opts = structure.SITE_TITLES[profile]
            title = _pick(rng, [o[0] for o in opts], [o[1] for o in opts])
        spec = structure.TITLE_INDEX[(site["line"], title)]
        level = spec[2]
        if not spec[3] and rng.random() < 0.3:
            level = min(6, level + 1)
        w["line"] = site["line"]
        w["region"] = site["region"]
        w["site_id"] = site["site_id"]
        w["site_name"] = site["name"]
        w["city"] = site["city"]
        w["state"] = site["state"]
        w["team_id"] = team["team_id"]
        w["team_profile"] = profile
        w["title"] = title
        w["job_level"] = level
        w["is_manager"] = bool(spec[3])
        w["_initial_is_manager"] = bool(spec[3])
        w["is_licensed"] = bool(spec[4])
        w["license_type"] = spec[5] or ""
        w["job_id"] = self.jobs_catalog.get(site["line"], title, level, site["region"],
                                            created_date=self.start)
        w["_hire_job_id"] = w["job_id"]
        w["work_mode"] = _pick(rng, cfg.WORK_MODES, cfg.WORK_MODE_WEIGHTS[spec[1]])
        band = cfg.PAY_BANDS[self._band_id(site["line"], level)]
        factor = float(rng.uniform(0.88, 1.12))
        w["salary_factor"] = factor
        w["base_salary"] = int(round(band[1] * factor))
        w["_band_mid"] = band[1]
        hire = date.fromisoformat(w["hire_date"])
        gap = days_between(hire, self.start)
        if rng.random() < 0.45 and gap > 400:
            promo = self.start - timedelta(days=int(rng.integers(60, min(1500, gap))))
            w["last_promotion_date"] = iso(promo)
        w["_updated"] = w["hire_date"]
        team["members"].append(w["worker_id"])

    @staticmethod
    def _band_id(line: str, level: int) -> str:
        premium = line in cfg.PREMIUM_LINES
        return f"PB{max(1, min(6, level))}{'H' if premium else ''}"

    # --------------------------------------------------------------- patterns
    def plan_patterns(self):
        rng = sub_rng(self.seed, "patterns")
        self.manifest = dict(num_employees=self.n, seed=self.seed, mode=self.mode,
                             end_date=iso(self.T), start_date=iso(self.start),
                             defects=dict(self.defects), patterns=dict(self.sizes))

        spike_sites = [s["site_id"] for s in self.sites if "contact_center_spike" in s["tags"]]
        control_sites = [s["site_id"] for s in self.sites if "contact_center_control" in s["tags"]]
        spike_teams = sorted([t for t in self.teams if t["spike_center"]], key=lambda t: t["team_id"])
        first = [t for t in spike_teams if t["site_id"] == spike_sites[0]]
        second = [t for t in spike_teams if t["site_id"] == spike_sites[1]]
        chosen = first[:2] + second[:1]
        for t in chosen:
            t["spike_mgr_team"] = True
        # A team of ~8 cannot carry 60% of a centre's excess exits over 8 months
        # without an absurd hazard. The three newly assigned managers each take
        # over a shift-sized group (~15% of the two centres' population).
        spike_pop = sum(len(t["members"]) for t in spike_teams)
        target = max(3, int(round(0.15 * spike_pop)))
        for t in chosen:
            donors = [d for d in spike_teams if d is not t and d["site_id"] == t["site_id"]]
            while len(t["members"]) > target and donors:
                movable = [wid for wid in t["members"]
                           if not self.workers_by_id[wid]["is_manager"]]
                if not movable:
                    break
                donor = max(donors, key=lambda x: (len(x["members"]), x["team_id"]))
                self._move_to_team(movable[-1], t, donor)
            while len(t["members"]) < target and donors:
                donor = max(donors, key=lambda x: (len(x["members"]), x["team_id"]))
                movable = [wid for wid in donor["members"]
                           if not self.workers_by_id[wid]["is_manager"]]
                if not movable:
                    donors = [d for d in donors if d["team_id"] != donor["team_id"]]
                    continue
                self._move_to_team(movable[-1], donor, t)
        s_m = sum(len(t["members"]) for t in chosen)
        s_n = sum(len(t["members"]) for t in spike_teams) - s_m
        m_target = self.sizes["p1_spike_multiplier"]
        ratio = self.sizes["p1_manager_excess_share"] / (1 - self.sizes["p1_manager_excess_share"])
        if s_m <= 0 or s_n <= 0:
            m1 = m2 = m_target
        else:
            k = ratio * s_n / s_m
            s = s_m + s_n
            m1 = (m_target * s - s_m * (1 - k)) / (s_m * k + s_n)
            m2 = 1 + k * (m1 - 1)
        self.p1_m1, self.p1_m2 = m1, m2
        self.manifest["p1_team_ids"] = [t["team_id"] for t in chosen]
        self.manifest["p1_spike_team_ids"] = [t["team_id"] for t in spike_teams]
        self.manifest["p1_control_team_ids"] = [t["team_id"] for t in self.teams
                                                if t["site_id"] in control_sites]

        long_tenure = add_days(self.anchor, -3 * 365 - 60)

        def p2_eligible(w):
            return date.fromisoformat(w["hire_date"]) <= long_tenure

        eligible = sorted([w for w in self.workers if w["team_profile"] == "tech_ai"
                           and not w["is_manager"] and p2_eligible(w)],
                          key=lambda w: w["worker_id"])
        other = sorted([w for w in self.workers if w["team_profile"] != "tech_ai"
                        and w["job_level"] >= 3 and not w["is_manager"]
                        and w["line"] != "Technology" and p2_eligible(w)],
                       key=lambda w: w["worker_id"])
        p2 = eligible[:max(0, self.sizes["p2_count"] - 4)] + other[:4]
        for w in p2:
            w["p2"] = True
            w["salary_factor"] = 0.88
            hire = date.fromisoformat(w["hire_date"])
            promo = add_days(self.anchor, -int(rng.integers(3 * 365 + 30, 6 * 365)))
            w["last_promotion_date"] = iso(max(hire + timedelta(days=30), promo))
        self.manifest["p2_workers"] = [w["worker_id"] for w in p2]

        wealth_ne_licensed = sorted([w for w in self.workers if w["team_profile"] == "wealth_ne"
                                     and w["is_licensed"]], key=lambda w: w["worker_id"])
        expiring = wealth_ne_licensed[:self.sizes["p3_expiring"]]
        for w in expiring:
            w["p3_expiring"] = True
        self.manifest["p3_expiring_workers"] = [w["worker_id"] for w in expiring]
        self.manifest["p3_wealth_ne_licensed"] = [w["worker_id"] for w in wealth_ne_licensed]

        self.manifest["p4_team_ids"] = [t["team_id"] for t in self.teams if t["fraud_card"]]
        self.manifest["fraud_other_team_ids"] = [t["team_id"] for t in self.teams
                                                 if t["profile"] == "fraud_other"]

        managers = sorted([w for w in self.workers if w["is_manager"]
                           and not self.teams_by_id[w["team_id"]]["spike_center"]
                           and not self.teams_by_id[w["team_id"]]["fraud_card"]],
                          key=lambda w: w["worker_id"])
        picks = rng.permutation(len(managers))[:self.sizes["p5_managers"]]
        p5_ids = []
        for i in picks:
            t = self.teams_by_id[managers[int(i)]["team_id"]]
            t["p5_team"] = True
            p5_ids.append(t["team_id"])
        self.manifest["p5_team_ids"] = p5_ids

        processing = sorted([w for w in self.workers
                             if w["team_profile"] in ("ops_processing", "ops_general", "fraud_other")
                             and not w["is_manager"]], key=lambda w: w["worker_id"])
        reskill = processing[:self.sizes["p6_reskill"]]
        for w in reskill:
            w["p6_reskill"] = True
        for w in processing[:self.sizes["p6_processing"]]:
            w["p6_processing"] = True
        self.manifest["p6_reskill_workers"] = [w["worker_id"] for w in reskill]

    def _move_to_team(self, wid: str, donor: dict, team: dict):
        donor["members"].remove(wid)
        team["members"].append(wid)
        w = self.workers_by_id[wid]
        w["team_id"] = team["team_id"]
        w["team_profile"] = team["profile"]
        w["manager_id"] = team["manager_id"]

    # --------------------------------------------------------------- simulate
    def _ensure_arrays(self, w: dict, n_days: int):
        wid = w["worker_id"]
        if wid not in self._u_exit:
            self._u_exit[wid] = sub_rng(self.seed, "exit", wid).random(n_days)
            self._u_promo[wid] = sub_rng(self.seed, "promo", wid).random(n_days)

    def _vol_hazard(self, w: dict, d: date) -> float:
        seg = PROFILE_SEGMENT[w["team_profile"]]
        base = annual_to_daily(cfg.VOL_ATTRITION_BY_SEGMENT[seg])
        team = self.teams_by_id[w["team_id"]]
        mult = 1.0
        if w["p2"] or w["p3_expiring"]:
            mult *= 2.0
        if team["p5_team"]:
            mult *= 0.5
        if team["spike_center"] and d >= self.change_date:
            mult *= self.p1_m2 if team["spike_mgr_team"] else self.p1_m1
        if team["fraud_card"] and d >= self.burnout_start:
            mult *= 1.2
        return base * mult

    def simulate(self):
        n_days = days_between(self.start, self.T) + 1
        for w in self.workers:
            self._ensure_arrays(w, n_days)
        self._initial_state = []
        for w in self.workers:
            if date.fromisoformat(w["hire_date"]) <= self.start:
                self._initial_state.append(dict(
                    worker_id=w["worker_id"], job_id=w["job_id"], org_unit_id=w["team_id"],
                    manager_id=w["manager_id"], business_line=w["line"], region=w["region"],
                    work_mode=w["work_mode"], last_promotion_date=w["last_promotion_date"]))
        invol = annual_to_daily(cfg.INVOLUNTARY_ANNUAL)
        ret = annual_to_daily(cfg.RETIREMENT_ANNUAL)
        workers = self.workers
        for i in range(n_days):
            d = self.start + timedelta(days=i)
            if d == self.change_date:
                self._apply_p1_manager_changes(d)
            for spec in self.pending_hires.pop(iso(d), []):
                self._hire(spec, d)
            for w in workers:
                if w["status"] != "active" or w["start_index"] > i:
                    continue
                u = float(self._u_exit[w["worker_id"]][i])
                h_vol = self._vol_hazard(w, d)
                total = h_vol + invol + ret
                if u >= total:
                    continue
                if u < h_vol:
                    etype = "voluntary"
                elif u < h_vol + invol:
                    etype = "involuntary"
                else:
                    etype = "retirement"
                self._terminate(w, d, etype)
            if d.day == 1:
                for w in workers:
                    if w["status"] != "active" or w["start_index"] > i:
                        continue
                    if float(self._u_promo[w["worker_id"]][i]) < 0.006 \
                            and not w["is_manager"] and w["job_level"] < 6 and not w["p2"]:
                        self._promote(w, d)

    def _event(self, wid: str, event_type: str, d: date, *, manager_id: str = "",
               job_id: str = "", org_unit_id: str = "", termination_type: str = "",
               last_promotion_date: str = "") -> dict:
        w = self.workers_by_id[wid]
        return dict(event_id=stable_id("E", "event", wid, event_type, iso(d), manager_id, job_id),
                    event_seq=EVENT_ORDER.get(event_type, 5),
                    worker_id=wid, event_type=event_type, effective_date=iso(d),
                    job_id=job_id or w["job_id"], org_unit_id=org_unit_id or w["team_id"],
                    manager_id=manager_id, business_line=w["line"], region=w["region"],
                    work_mode=w["work_mode"], termination_type=termination_type,
                    last_promotion_date=last_promotion_date or w["last_promotion_date"])

    def _active_on(self, w: dict, d: date) -> bool:
        if date.fromisoformat(w["hire_date"]) > d:
            return False
        return not w["termination_date"] or date.fromisoformat(w["termination_date"]) > d

    def _set_manager(self, w: dict, manager_id: str, d: date):
        if manager_id and not self._manager_chain_ok(w["worker_id"], manager_id):
            manager_id = ""
        if w["manager_id"] == manager_id:
            return
        w["manager_id"] = manager_id
        w["_mgr_history"].append((iso(d), manager_id))
        w["_updated"] = max(w["_updated"], iso(d))

    def _manager_chain_ok(self, wid: str, manager_id: str) -> bool:
        seen = set()
        cur = manager_id
        while cur:
            if cur == wid or cur in seen:
                return False
            seen.add(cur)
            manager = self.workers_by_id.get(cur)
            if manager is None:
                break
            cur = manager["manager_id"]
        return True

    def _upward_manager(self, manager_id: str, d: date) -> str:
        manager = self.workers_by_id.get(manager_id)
        return manager_id if manager and self._active_on(manager, d) else ""

    def _reassign_reports(self, reports: list, successor: str, d: date):
        for report in reports:
            if report["worker_id"] == successor:
                continue
            self._set_manager(report, successor, d)
            self.events.append(self._event(report["worker_id"], "manager_change", d,
                                           manager_id=successor,
                                           org_unit_id=report["team_id"]))

    def _director_id(self, team: dict, exclude=()) -> str:
        if team["profile"] not in _DIRECTOR_PROFILES:
            return ""
        for peer in sorted((t for t in self.teams if t["site_id"] == team["site_id"]),
                           key=lambda t: t["team_id"]):
            mid = peer["manager_id"]
            if not mid or mid in exclude:
                continue
            mgr = self.workers_by_id.get(mid)
            if mgr and mgr["status"] == "active":
                return mid
        return ""

    def _promote_to_manager(self, wid: str, team: dict, d: date,
                            title: str = None) -> tuple:
        w = self.workers_by_id[wid]
        old = (w["title"], w["job_level"])
        title = title or _team_manager_title(team["profile"], team["line"])
        level = structure.TITLE_INDEX[(team["line"], title)][2]
        w["is_manager"] = True
        w["title"] = title
        w["job_level"] = max(level, w["job_level"])
        w["job_id"] = self.jobs_catalog.get(team["line"], w["title"], w["job_level"],
                                            team["region"], created_date=d)
        w["_updated"] = max(w["_updated"], iso(d))
        w.setdefault("promotions", []).append(dict(date=iso(d), level=w["job_level"],
                                                   job_id=w["job_id"]))
        return old

    def _manager_change_for_team(self, team: dict, new_manager: str, d: date, exclude=()):
        for wid in team["members"]:
            w = self.workers_by_id.get(wid)
            if w is None or wid == new_manager or wid in exclude or not self._active_on(w, d):
                continue
            self._set_manager(w, new_manager, d)
            self.events.append(self._event(wid, "manager_change", d, manager_id=new_manager,
                                           org_unit_id=team["team_id"]))

    def _apply_p1_manager_changes(self, d: date):
        for tid in self.manifest.get("p1_team_ids", []):
            team = self.teams_by_id[tid]
            if not team["spike_mgr_team"]:
                continue
            old_manager = team["manager_id"]
            candidates = sorted([wid for wid in team["members"]
                                 if wid != old_manager
                                 and not self.workers_by_id[wid]["is_manager"]
                                 and self._active_on(self.workers_by_id[wid], d)])
            if not candidates:
                continue
            rng = sub_rng(self.seed, "p1change", tid)
            new_manager = candidates[int(rng.integers(0, len(candidates)))]
            self._promote_to_manager(new_manager, team, d)
            old = self.workers_by_id.get(old_manager)
            director = old["manager_id"] if old and self._active_on(old, d) else ""
            if director in (new_manager, old_manager):
                director = ""
            self._set_manager(self.workers_by_id[new_manager], director, d)
            self.events.append(self._event(new_manager, "manager_change", d,
                                           manager_id=director, org_unit_id=team["team_id"]))
            if old is not None and old["status"] == "active":
                self._set_manager(old, director, d)
                self.events.append(self._event(old_manager, "manager_change", d,
                                               manager_id=director,
                                               org_unit_id=team["team_id"]))
            team["manager_id"] = new_manager
            self._manager_change_for_team(team, new_manager, d, exclude={old_manager})

    def _replace_manager(self, mgr: dict, d: date):
        teams = [t for t in self.teams if t["manager_id"] == mgr["worker_id"]]
        team = teams[0] if teams else self.teams_by_id.get(mgr["team_id"])
        reports = sorted([w for w in self.workers_by_id.values()
                          if w["manager_id"] == mgr["worker_id"]
                          and w["worker_id"] != mgr["worker_id"]
                          and self._active_on(w, d)],
                         key=lambda w: w["worker_id"])
        if not reports and not teams:
            return False
        if not reports:
            interim = self._upward_manager(mgr["manager_id"], d)
            for t in teams:
                t["manager_id"] = interim
                self._manager_change_for_team(t, interim, d)
                self._schedule_manager_hire(t, d)
            return True

        managers = [w for w in reports if w["is_manager"]]
        individual = [w for w in reports if not w["is_manager"]]
        pool = managers or individual
        rng = sub_rng(self.seed, "successor", mgr["worker_id"], iso(d))
        successor = pool[int(rng.integers(0, len(pool)))]["worker_id"]
        successor_was_manager = self.workers_by_id[successor]["is_manager"]
        director_title = _director_title(team["profile"], team["line"]) \
            if mgr["job_level"] >= 5 else None
        old_title, old_level = self._promote_to_manager(
            successor, team, d, title=director_title)
        upward = self._upward_manager(mgr["manager_id"], d)
        self._set_manager(self.workers_by_id[successor], upward, d)
        self.events.append(self._event(successor, "manager_change", d,
                                       manager_id=upward,
                                       org_unit_id=self.workers_by_id[successor]["team_id"]))
        self._reassign_reports(reports, successor, d)
        for t in teams:
            t["manager_id"] = successor
        if not successor_was_manager:
            # The promoted IC leaves a vacancy, not the manager role.
            self._schedule_backfill(successor, d, self.workers_by_id[successor],
                                    title=old_title, level=old_level, is_manager=False,
                                    hiring_manager_id=successor)
        return True

    def _schedule_manager_hire(self, team: dict, d: date):
        rng = sub_rng(self.seed, "manager_backfill", team["team_id"], iso(d))
        title = _team_manager_title(team["profile"], team["line"])
        level = structure.TITLE_INDEX[(team["line"], title)][2]
        hire_date = d + timedelta(days=int(max(7, cfg.TTF_OTHER_DAYS + rng.normal(0, 8))))
        vacancy = self._record_vacancy(
            source_id=f"manager:{team['team_id']}", d=d, hire_date=hire_date,
            team=team, title=title, level=level, manager_id=team["manager_id"],
            is_manager=True, is_licensed=False, license_type="", work_mode="Onsite")
        spec = dict(worker_id=f"W{hash_int(self.seed, 'manager_backfill', team['team_id'], iso(d)) % 1_000_000_000:09d}",
                    line=team["line"], region=team["region"], site_id=team["site_id"],
                    site_name=team["site_name"], city=team["city"], state=team["state"],
                    team_id=team["team_id"], team_profile=team["profile"], title=title,
                    level=level,
                    is_licensed=False, license_type="", work_mode="Onsite",
                    is_manager=True, replaces_manager=True,
                    vacancy_id=vacancy["vacancy_id"] if vacancy else "")
        self.pending_hires.setdefault(iso(hire_date), []).append(spec)

    def _schedule_backfill(self, source_id: str, d: date, w: dict, *, title: str,
                           level: int, is_manager: bool, hiring_manager_id: str = None):
        rng = sub_rng(self.seed, "backfill", source_id, iso(d))
        licensed = bool(w["is_licensed"] and w["license_type"])
        base = cfg.TTF_LICENSED_DAYS if licensed else cfg.TTF_OTHER_DAYS
        hire_date = d + timedelta(days=int(max(7, base + rng.normal(0, 8))))
        team = self.teams_by_id[w["team_id"]]
        vacancy = self._record_vacancy(
            source_id=source_id, d=d, hire_date=hire_date, team=team, title=title,
            level=level, manager_id=hiring_manager_id or w["manager_id"],
            is_manager=is_manager,
            is_licensed=w["is_licensed"], license_type=w["license_type"],
            work_mode=w["work_mode"])
        spec = dict(worker_id=self._backfill_worker_id(source_id, d), line=w["line"],
                    region=w["region"], site_id=w["site_id"], site_name=w["site_name"],
                    city=w["city"], state=w["state"], team_id=w["team_id"],
                    team_profile=w["team_profile"], title=title, level=level,
                    is_licensed=w["is_licensed"], license_type=w["license_type"],
                    work_mode=w["work_mode"], is_manager=is_manager,
                    vacancy_id=vacancy["vacancy_id"] if vacancy else "")
        self.pending_hires.setdefault(iso(hire_date), []).append(spec)

    def _record_vacancy(self, *, source_id: str, d: date, hire_date: date, team: dict,
                        title: str, level: int, manager_id: str, is_manager: bool,
                        is_licensed: bool, license_type: str, work_mode: str):
        probability = 0.50 if is_licensed else 0.15
        rng = sub_rng(self.seed, "vacancy_req", source_id, iso(d),
                      team["team_id"], title, level)
        if rng.random() >= probability:
            return None
        vacancy_id = stable_id("V", "vacancy", source_id, iso(d), team["team_id"],
                               title, level)
        if vacancy_id in self.vacancies_by_id:
            return self.vacancies_by_id[vacancy_id]
        vacancy = dict(
            vacancy_id=vacancy_id, opened_date=iso(d), expected_hire_date=iso(hire_date),
            closed_date="", status="Open", filled_by_worker_id="",
            team_id=team["team_id"], org_unit_id=team["team_id"], manager_id=manager_id,
            job_id=self.jobs_catalog.get(team["line"], title, level, team["region"],
                                         created_date=d),
            title=title, level=level, line=team["line"], region=team["region"],
            site_id=team["site_id"], city=team["city"], state=team["state"],
            is_licensed=is_licensed, license_type=license_type,
            work_mode=work_mode, is_manager=is_manager)
        self.vacancies.append(vacancy)
        self.vacancies_by_id[vacancy_id] = vacancy
        return vacancy

    def _hire(self, spec: dict, d: date):
        rng = sub_rng(self.seed, "hire", spec["worker_id"])
        wid = spec["worker_id"]
        w = dict(
            worker_id=wid, first_name=_pick(rng, FIRST_NAMES, [1.0] * len(FIRST_NAMES)),
            last_name=_pick(rng, LAST_NAMES, [1.0] * len(LAST_NAMES)),
            work_email=f"hire{wid.lower()}@aitabank.example",
            phone="(" + str(int(rng.integers(200, 999))) + ") " +
                  str(int(rng.integers(200, 999))) + "-" + f"{int(rng.integers(0, 9999)):04d}",
            home_postal_code=f"{int(rng.integers(1000, 99999)):05d}", hire_date=iso(d),
            employment_type=_pick(rng, [x for x, _ in cfg.EMPLOYMENT_TYPE_WEIGHTS],
                                  [x for _, x in cfg.EMPLOYMENT_TYPE_WEIGHTS]),
            line=spec["line"], region=spec["region"], site_id=spec["site_id"],
            site_name=spec["site_name"], city=spec["city"], state=spec["state"],
            team_id=spec["team_id"], team_profile=spec["team_profile"], manager_id="",
            job_id="", title=spec["title"], job_level=spec["level"],
            is_licensed=spec["is_licensed"], license_type=spec["license_type"],
            work_mode=spec["work_mode"], salary_factor=1.0, base_salary=0,
            last_promotion_date="", status="active", termination_date="",
            termination_type="", exit_reason="", exit_reasons=[],
            p2=False, p3_expiring=False, p6_reskill=False, p6_processing=False,
            is_manager=spec["is_manager"], start_index=days_between(self.start, d), promotions=[],
            _updated=iso(d), _mgr_history=[(iso(d), "")],
            _initial_is_manager=spec["is_manager"],
        )
        band_mid = cfg.PAY_BANDS[self._band_id(spec["line"], spec["level"])][1]
        factor = float(rng.uniform(0.88, 1.12))
        w["salary_factor"] = factor
        w["base_salary"] = int(round(band_mid * factor))
        w["_band_mid"] = band_mid
        w["job_id"] = self.jobs_catalog.get(spec["line"], spec["title"], spec["level"],
                                            spec["region"], created_date=d)
        w["_hire_job_id"] = w["job_id"]
        team = self.teams_by_id[spec["team_id"]]
        previous_manager = team["manager_id"]
        if spec.get("replaces_manager"):
            director = self._director_id(team, exclude={wid})
            w["manager_id"] = director
            team["manager_id"] = wid
        else:
            w["manager_id"] = previous_manager
        w["_mgr_history"] = [(iso(d), w["manager_id"])]
        team["members"].append(wid)
        self.workers.append(w)
        self.workers_by_id[wid] = w
        self._ensure_arrays(w, days_between(self.start, self.T) + 1)
        self.events.append(self._event(wid, "hire", d, manager_id=w["manager_id"],
                                       job_id=w["job_id"], org_unit_id=team["team_id"]))
        if spec.get("replaces_manager"):
            self._manager_change_for_team(team, wid, d)
        if spec.get("vacancy_id"):
            vacancy = self.vacancies_by_id[spec["vacancy_id"]]
            vacancy.update(status="Filled", filled_by_worker_id=wid, closed_date=iso(d),
                           manager_id=w["manager_id"], org_unit_id=w["team_id"])

    def _terminate(self, w: dict, d: date, etype: str):
        w["status"] = "terminated"
        w["termination_date"] = iso(d)
        w["termination_type"] = etype
        reasons = self._exit_reasons(w, d) if etype == "voluntary" else []
        w["exit_reasons"] = reasons
        w["exit_reason"] = reasons[0] if reasons else ""
        w["_updated"] = max(w["_updated"], iso(d))
        self.events.append(self._event(w["worker_id"], "termination", d,
                                       manager_id=w["manager_id"], termination_type=etype))
        if (any(t["manager_id"] == w["worker_id"] for t in self.teams)
                or any(x["manager_id"] == w["worker_id"] for x in self.workers)):
            self._replace_manager(w, d)
        else:
            self._schedule_backfill(w["worker_id"], d, w, title=w["title"],
                                    level=w["job_level"], is_manager=False)

    def _exit_reasons(self, w: dict, d: date) -> list:
        rng = sub_rng(self.seed, "reason", w["worker_id"])
        team = self.teams_by_id[w["team_id"]]
        if team["spike_center"] and d >= self.change_date \
                and rng.random() < self.sizes["p1_reason_share"]:
            return ["schedule_workload"]
        weights = list(REASON_WEIGHTS)
        if team["fraud_card"] and d >= self.burnout_start:
            weights = [(r, wt * 3 if r == "health_burnout" else wt) for r, wt in weights]
        if w["p3_expiring"]:
            weights = [(r, wt * 2 if r in ("career_growth", "compensation") else wt)
                       for r, wt in weights]
        reasons = [_pick(rng, [r for r, _ in weights], [x for _, x in weights])]
        if rng.random() < 0.25:
            second = _pick(rng, [r for r, _ in weights], [x for _, x in weights])
            if second != reasons[0]:
                reasons.append(second)
        return reasons

    def _promote(self, w: dict, d: date):
        w["job_level"] = min(6, w["job_level"] + 1)
        w["job_id"] = self.jobs_catalog.get(w["line"], w["title"], w["job_level"], w["region"],
                                            created_date=d)
        w["last_promotion_date"] = iso(d)
        w.setdefault("promotions", []).append(dict(date=iso(d), level=w["job_level"],
                                                   job_id=w["job_id"]))
        w["_updated"] = max(w["_updated"], iso(d))
        self.events.append(self._event(w["worker_id"], "promotion", d, job_id=w["job_id"],
                                       last_promotion_date=iso(d)))

    def finalize_events(self):
        initial = [dict(event_id=stable_id("E", "event", s["worker_id"], "initial_state",
                                           iso(self.start), s["manager_id"], s["job_id"]),
                        event_seq=EVENT_ORDER["initial_state"],
                        worker_id=s["worker_id"], event_type="initial_state",
                        effective_date=iso(self.start), job_id=s["job_id"],
                        org_unit_id=s["org_unit_id"], manager_id=s["manager_id"],
                        business_line=s["business_line"], region=s["region"],
                        work_mode=s["work_mode"], termination_type="",
                        last_promotion_date=s["last_promotion_date"])
                   for s in self._initial_state]
        self.events.extend(initial)
        termination_days = {(e["worker_id"], e["effective_date"]) for e in self.events
                            if e["event_type"] == "termination"}
        self.events = [e for e in self.events
                       if not (e["event_type"] == "manager_change"
                               and (e["worker_id"], e["effective_date"]) in termination_days)]
        self.events.sort(key=lambda e: (e["effective_date"], e["worker_id"],
                                        e["event_seq"], e["event_id"]))


def _team_manager_title(profile: str, line: str) -> str:
    mapping = {
        "branch": "Branch Manager",
        "contact_center": "Contact Center Team Manager",
        "ops_processing": "Operations Team Manager",
        "ops_general": "Operations Team Manager",
        "fraud_card_disputes": "Fraud Operations Team Manager",
        "fraud_other": "Fraud Operations Team Manager",
        "wealth_ne": "Wealth Team Manager",
        "wealth_other": "Wealth Team Manager",
        "tech": "Engineering Manager",
        "tech_ai": "Engineering Manager",
        "commercial": "Commercial Team Lead",
        "corporate": "Corporate Manager",
    }
    return mapping[profile]


_DIRECTOR_PROFILES = {
    "contact_center", "ops_processing", "ops_general",
    "fraud_card_disputes", "fraud_other", "tech", "tech_ai",
}


def _director_title(profile: str, line: str) -> str:
    """Title for the most senior team in a site.

    Branches and the smaller offices do not have a separate director level, so
    every manager there carries the same manager title. Reusing the Consumer
    Banking director title for every site put "Contact Center Director" on
    branch managers.
    """
    if profile == "branch":
        return "Branch Manager"
    if profile == "contact_center":
        return "Contact Center Director"
    if profile in ("ops_processing", "ops_general"):
        return "Operations Manager"
    if profile in ("fraud_card_disputes", "fraud_other"):
        return "Fraud Operations Team Manager"
    if profile in ("tech", "tech_ai"):
        return "Engineering Manager"
    if profile == "wealth_ne" or profile == "wealth_other":
        return "Wealth Team Manager"
    if profile == "commercial":
        return "Commercial Team Lead"
    return "Corporate Manager"
