"""Builds the static topology: sites, org units, jobs and pay bands.

Everything here depends only on ``num_employees``; workers are placed onto this
topology by :mod:`generate.world`.
"""

from __future__ import annotations

from . import config as cfg
from .rng import stable_id, sub_rng

TITLE_INDEX = {}
for _line, _titles in cfg.JOB_TITLES.items():
    for _t in _titles:
        TITLE_INDEX[(_line, _t[0])] = (_t[0], _t[1], _t[2], _t[3], _t[4], _t[5])


def _t(line: str, title: str) -> tuple:
    return TITLE_INDEX[(line, title)]


# IC/mgr title options per site profile: (title, weight)
SITE_TITLES = {
    "branch": [
        ("Teller", 0.55),
        ("Personal Banker", 0.45),
    ],
    "contact_center": [
        ("Contact Center Representative", 1.0),
    ],
    "fraud_card_disputes": [
        ("Fraud Operations Analyst", 1.0),
    ],
    "fraud_other": [
        ("Fraud Operations Analyst", 1.0),
    ],
    "ops_processing": [
        ("Loan Operations Processor", 0.45),
        ("Payments Operations Analyst", 0.3),
        ("Deposit Operations Analyst", 0.25),
    ],
    "ops_general": [
        ("Loan Operations Processor", 0.3),
        ("Payments Operations Analyst", 0.4),
        ("Deposit Operations Analyst", 0.3),
    ],
    "wealth_ne": [
        ("Financial Advisor", 0.5),
        ("Senior Financial Advisor", 0.25),
        ("Client Service Associate", 0.25),
    ],
    "wealth_other": [
        ("Financial Advisor", 0.45),
        ("Senior Financial Advisor", 0.2),
        ("Client Service Associate", 0.35),
    ],
    "tech_ai": [
        ("Data Engineer", 0.25),
        ("Data Scientist", 0.4),
        ("Machine Learning Engineer", 0.35),
    ],
    "tech": [
        ("Software Engineer", 0.4),
        ("Infrastructure Engineer", 0.25),
        ("Data Engineer", 0.2),
        ("Data Scientist", 0.15),
    ],
    "commercial": [
        ("Credit Analyst", 0.5),
        ("Relationship Manager", 0.5),
    ],
    "corporate": [
        ("Recruiter", 0.15),
        ("HR Business Partner", 0.2),
        ("Financial Analyst", 0.3),
        ("Risk Analyst", 0.2),
        ("Compliance Officer", 0.15),
    ],
}

def _region_city(region: str, idx: int):
    cities = cfg.REGION_CITIES[region]
    return cities[idx % len(cities)]


def plan_sites(n: int, sizes: dict) -> list[dict]:
    hc = cfg.headcount_by_line(n)
    sites: list[dict] = []

    # --- Consumer Banking: branches + three contact centers -----------------
    centers = [
        ("Contact Center - Charlotte", "Charlotte", "NC", "Southeast", ["contact_center_spike"]),
        ("Contact Center - Phoenix", "Phoenix", "AZ", "West", ["contact_center_spike"]),
        ("Contact Center - Columbus", "Columbus", "OH", "Midwest", ["contact_center_control"]),
    ]
    center_size = sizes["p1_center_size"]
    for name, city, state, region, tags in centers:
        sites.append(dict(name=name, site_type="contact_center", profile="contact_center",
                          line="Consumer Banking", city=city, state=state, region=region,
                          target_size=center_size, tags=tags))
    branch_staff = max(0, hc["Consumer Banking"] - 3 * center_size)
    num_branches = cfg.scale(60, n, 8)
    branch_size = max(1, branch_staff // num_branches)
    regions = cfg.REGIONS
    for i in range(num_branches):
        region = regions[i % len(regions)]
        city, state = _region_city(region, i // len(regions))
        sites.append(dict(name=f"Branch - {city} {i + 1}", site_type="branch", profile="branch",
                          line="Consumer Banking", city=city, state=state, region=region,
                          target_size=branch_size, tags=[]))

    # --- Operations ---------------------------------------------------------
    fraud_total = sizes["p4_fraud_total"]
    card = sizes["p4_card_disputes"]
    processing = sizes["p6_processing"]
    rest = max(0, hc["Operations"] - fraud_total - processing)
    charlotte = card + round(rest * 0.3) + round(processing * 0.35)
    phoenix = (fraud_total - card) + round(rest * 0.3) + round(processing * 0.35)
    columbus = max(1, hc["Operations"] - charlotte - phoenix)
    sites.append(dict(name="Operations Center - Charlotte", site_type="operations_center",
                      profile="ops_mixed", line="Operations", city="Charlotte", state="NC",
                      region="Southeast", target_size=charlotte,
                      tags=["fraud_card_disputes", "ops_processing"]))
    sites.append(dict(name="Operations Center - Phoenix", site_type="operations_center",
                      profile="ops_mixed", line="Operations", city="Phoenix", state="AZ",
                      region="West", target_size=phoenix, tags=["fraud_other", "ops_processing"]))
    sites.append(dict(name="Operations Center - Columbus", site_type="operations_center",
                      profile="ops_mixed", line="Operations", city="Columbus", state="OH",
                      region="Midwest", target_size=columbus, tags=["ops_general", "ops_processing"]))

    # --- Wealth -------------------------------------------------------------
    wealth_ne = sizes["p3_wealth_ne_licensed"]
    wealth_rest = max(0, hc["Wealth Management"] - wealth_ne)
    sites.append(dict(name="Wealth Office - Boston", site_type="wealth_office", profile="wealth_ne",
                      line="Wealth Management", city="Boston", state="MA", region="Northeast",
                      target_size=wealth_ne, tags=["wealth_ne"]))
    others = [("Atlanta", "GA", "Southeast"), ("Chicago", "IL", "Midwest"), ("Denver", "CO", "West")]
    per = max(1, wealth_rest // len(others))
    for city, state, region in others:
        sites.append(dict(name=f"Wealth Office - {city}", site_type="wealth_office",
                          profile="wealth_other", line="Wealth Management", city=city, state=state,
                          region=region, target_size=per, tags=["wealth_other"]))

    # --- Technology ---------------------------------------------------------
    tech_ai = cfg.scale(80, n, 10)
    sites.append(dict(name="Technology Center - San Francisco", site_type="tech_office",
                      profile="tech_ai", line="Technology", city="San Francisco", state="CA",
                      region="West", target_size=tech_ai, tags=["tech_ai"]))
    sites.append(dict(name="Technology Center - New York", site_type="tech_office", profile="tech",
                      line="Technology", city="New York", state="NY", region="Northeast",
                      target_size=max(1, hc["Technology"] - tech_ai), tags=["tech"]))

    # --- Commercial ---------------------------------------------------------
    comm_offices = [("New York", "NY", "Northeast"), ("Chicago", "IL", "Midwest"),
                    ("Atlanta", "GA", "Southeast"), ("Denver", "CO", "West")]
    per = max(1, hc["Commercial Banking"] // len(comm_offices))
    for city, state, region in comm_offices:
        sites.append(dict(name=f"Commercial Office - {city}", site_type="commercial_office",
                          profile="commercial", line="Commercial Banking", city=city, state=state,
                          region=region, target_size=per, tags=["commercial"]))

    # --- Corporate ----------------------------------------------------------
    corp_offices = [("New York", "NY", "Northeast"), ("Charlotte", "NC", "Southeast"),
                    ("Columbus", "OH", "Midwest")]
    per = max(1, hc["Corporate Functions"] // len(corp_offices))
    for city, state, region in corp_offices:
        sites.append(dict(name=f"Corporate Office - {city}", site_type="corporate_office",
                          profile="corporate", line="Corporate Functions", city=city, state=state,
                          region=region, target_size=per, tags=["corporate"]))
    return sites


class JobCatalog:
    def __init__(self):
        self.rows: list[dict] = []
        self._index: dict[tuple, str] = {}

    def get(self, line: str, title: str, level: int, region: str,
            created_date=None) -> str:
        key = (line, title, level, region)
        if key in self._index:
            return self._index[key]
        spec = _t(line, title)
        _, family, base_level, is_mgr, licensed, lic_type = spec
        level = max(1, min(6, level))
        premium = line in cfg.PREMIUM_LINES
        band = f"PB{level}{'H' if premium else ''}"
        job_id = stable_id("J", "job", line, title, level, region, width=10)
        routine = self._is_routine(title, family)
        from . import text as textmod

        rng = sub_rng(20260101, "job_desc", job_id)
        skills = None
        consultative = False
        if title in ("Process Automation Analyst", "Process Improvement Analyst", "Fraud Data Analyst"):
            skills = ["SQL", "process mapping", "data quality", "Excel automation"]
            consultative = True
            routine = False
        elif family == "Data & AI" or line == "Technology":
            skills = ["Python", "SQL", "dashboarding"]
            consultative = True
        desc = textmod.job_description(rng, title, routine=routine, skills=skills, consultative=consultative)
        self.rows.append(dict(
            job_id=job_id, title=title, job_family=family, job_level=level,
            business_line=line, is_people_manager=is_mgr, is_licensed_role=licensed,
            required_license_type=lic_type or "", pay_band_id=band, job_description=desc,
            region=region, created_date=created_date.isoformat() if created_date else "",
        ))
        self._index[key] = job_id
        return job_id

    @staticmethod
    def _is_routine(title: str, family: str) -> bool:
        if title in ("Contact Center Representative", "Loan Operations Processor",
                     "Payments Operations Analyst", "Deposit Operations Analyst",
                     "Fraud Operations Analyst"):
            return True
        return False


def pay_band_rows() -> list[dict]:
    rows = []
    for band_id, (lo, mid, hi) in cfg.PAY_BANDS.items():
        rows.append(dict(pay_band_id=band_id, band_min=lo, band_mid=mid, band_max=hi,
                         effective_date="2024-01-01"))
    return rows
