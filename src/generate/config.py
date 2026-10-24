"""Static configuration plus the sizing rules quoted in README.md and PATTERNS.md.

Every count in the docs is quoted at 5,000 employees (``BASE_N``). ``scale``
maps one of those counts onto an arbitrary ``--num-employees`` value, with a
floor so the planted patterns stay statistically detectable in the small
500-employee test run.
"""

from __future__ import annotations

BASE_N = 5000

DATASETS = [
    "org_units",
    "jobs",
    "pay_bands",
    "workers",
    "worker_events",
    "compensation",
    "performance_reviews",
    "engagement_responses",
    "exit_interviews",
    "licenses",
    "training_assignments",
    "requisitions",
    "candidates",
    "productivity",
    "site_events",
]

BUSINESS_LINES = [
    "Consumer Banking",
    "Operations",
    "Wealth Management",
    "Technology",
    "Commercial Banking",
    "Corporate Functions",
]

LINE_SHARE = {
    "Consumer Banking": 0.36,
    "Operations": 0.20,
    "Wealth Management": 0.14,
    "Technology": 0.12,
    "Commercial Banking": 0.10,
    "Corporate Functions": 0.08,
}

REGIONS = ["Northeast", "Southeast", "Midwest", "West"]

REGION_CITIES = {
    "Northeast": [("Boston", "MA"), ("New York", "NY"), ("Philadelphia", "PA"), ("Hartford", "CT")],
    "Southeast": [("Charlotte", "NC"), ("Atlanta", "GA"), ("Miami", "FL"), ("Nashville", "TN")],
    "Midwest": [("Columbus", "OH"), ("Chicago", "IL"), ("Minneapolis", "MN"), ("Detroit", "MI")],
    "West": [("Phoenix", "AZ"), ("Denver", "CO"), ("Seattle", "WA"), ("San Francisco", "CA")],
}

# job_family: (title, family, level, is_people_manager, is_licensed_role, license_type)
JOB_TITLES = {
    "Consumer Banking": [
        ("Teller", "Branch", 1, False, False, None),
        ("Personal Banker", "Branch", 2, False, False, None),
        ("Branch Manager", "Branch", 4, True, False, None),
        ("Contact Center Representative", "Contact Center", 1, False, False, None),
        ("Contact Center Team Manager", "Contact Center", 4, True, False, None),
        ("Contact Center Director", "Contact Center", 5, True, False, None),
    ],
    "Operations": [
        ("Loan Operations Processor", "Operations", 1, False, False, None),
        ("Payments Operations Analyst", "Operations", 2, False, False, None),
        ("Deposit Operations Analyst", "Operations", 2, False, False, None),
        ("Fraud Operations Analyst", "Fraud Operations", 2, False, False, None),
        ("Operations Team Manager", "Operations", 4, True, False, None),
        ("Fraud Operations Team Manager", "Fraud Operations", 4, True, False, None),
        ("Operations Manager", "Operations", 5, True, False, None),
        ("Process Automation Analyst", "Operations", 3, False, False, None),
        ("Process Improvement Analyst", "Operations", 3, False, False, None),
        ("Fraud Data Analyst", "Fraud Operations", 4, False, False, None),
    ],
    "Wealth Management": [
        ("Client Service Associate", "Wealth", 2, False, False, None),
        ("Financial Advisor", "Wealth", 3, False, True, "Series 7"),
        ("Senior Financial Advisor", "Wealth", 4, False, True, "Series 66"),
        ("Wealth Team Manager", "Wealth", 5, True, True, "Series 7"),
    ],
    "Technology": [
        ("Software Engineer", "Technology", 3, False, False, None),
        ("Infrastructure Engineer", "Technology", 3, False, False, None),
        ("Data Engineer", "Data & AI", 3, False, False, None),
        ("Data Scientist", "Data & AI", 4, False, False, None),
        ("Machine Learning Engineer", "Data & AI", 4, False, False, None),
        ("Engineering Manager", "Technology", 5, True, False, None),
    ],
    "Commercial Banking": [
        ("Credit Analyst", "Commercial", 2, False, False, None),
        ("Relationship Manager", "Commercial", 4, False, False, None),
        ("Commercial Team Lead", "Commercial", 5, True, False, None),
    ],
    "Corporate Functions": [
        ("Recruiter", "Corporate", 2, False, False, None),
        ("HR Business Partner", "Corporate", 3, False, False, None),
        ("Financial Analyst", "Corporate", 3, False, False, None),
        ("Risk Analyst", "Corporate", 3, False, False, None),
        ("Compliance Officer", "Corporate", 4, False, True, "State Insurance"),
        ("Corporate Manager", "Corporate", 5, True, False, None),
    ],
}

PREMIUM_LINES = {"Technology", "Wealth Management", "Commercial Banking"}

# pay_band_id -> (min, mid, max)
PAY_BANDS = {
    "PB1": (34000, 42000, 52000),
    "PB2": (48000, 60000, 74000),
    "PB3": (62000, 78000, 96000),
    "PB4": (82000, 104000, 128000),
    "PB5": (108000, 136000, 172000),
    "PB6": (140000, 178000, 224000),
    "PB1H": (40000, 50000, 62000),
    "PB2H": (58000, 72000, 90000),
    "PB3H": (74000, 94000, 118000),
    "PB4H": (98000, 124000, 154000),
    "PB5H": (130000, 164000, 206000),
    "PB6H": (168000, 212000, 268000),
}

WORK_MODES = ["Onsite", "Hybrid", "Remote"]
WORK_MODE_WEIGHTS = {
    "Branch": [0.85, 0.15, 0.0],
    "Contact Center": [1.0, 0.0, 0.0],
    "Operations": [0.6, 0.35, 0.05],
    "Fraud Operations": [0.7, 0.3, 0.0],
    "Wealth": [0.2, 0.7, 0.1],
    "Technology": [0.1, 0.6, 0.3],
    "Data & AI": [0.05, 0.55, 0.4],
    "Commercial": [0.15, 0.7, 0.15],
    "Corporate": [0.1, 0.7, 0.2],
}

EMPLOYMENT_TYPE_WEIGHTS = [("Full-time", 0.9), ("Part-time", 0.07), ("Contractor", 0.03)]

# Annual voluntary attrition by segment; daily hazard is derived in the model.
VOL_ATTRITION_BY_SEGMENT = {
    "Contact Center": 0.20,
    "Fraud Operations": 0.16,
    "Branch": 0.13,
    "Operations": 0.11,
    "Wealth": 0.09,
    "Technology": 0.10,
    "Data & AI": 0.10,
    "Commercial": 0.08,
    "Corporate": 0.07,
}
INVOLUNTARY_ANNUAL = 0.03
RETIREMENT_ANNUAL = 0.02

EXIT_REASONS = [
    "schedule_workload",
    "compensation",
    "career_growth",
    "manager_relationship",
    "relocation_personal",
    "health_burnout",
    "other",
]

# Baseline annual time-to-fill by licensed/non-licensed (P7).
TTF_LICENSED_DAYS = 60
TTF_OTHER_DAYS = 38

LICENSE_TYPES = {
    "Series 7": 3 * 365,
    "Series 66": 3 * 365,
    "NMLS Mortgage Originator": 365,
    "State Insurance": 2 * 365,
}

COURSES = [
    ("AML/BSA", True, "Compliance"),
    ("Fair Lending", True, "Compliance"),
    ("Privacy", True, "Compliance"),
    ("Code of Conduct", True, "Conduct"),
    ("Information Security", True, "Security"),
    ("Anti-Fraud", False, "Compliance"),
    ("Continuing Education", False, "Professional"),
    ("Manager Essentials", False, "Leadership"),
]


def scale(base: int, n: int, floor: int = 1) -> int:
    """Map a 5,000-employee count onto ``n`` employees with a floor."""
    return max(floor, int(round(base * n / BASE_N)))


def defect_counts(n: int) -> dict:
    """Deliberate data-quality defects the pipeline expectations must catch."""
    return {
        "duplicate_worker_events": scale(25, n, 2),
        "unknown_business_line": scale(10, n, 1),
        "termination_before_hire": scale(5, n, 1),
        "license_expiry_before_issue": scale(5, n, 1),
    }


def pattern_sizes(n: int) -> dict:
    """Planted-pattern cohort sizes, scaled from the 5,000-employee values."""
    return {
        "p1_center_size": scale(200, n, 6),
        "p1_managers": 3,
        "p1_spike_multiplier": 2.5,
        "p1_manager_excess_share": 0.6,
        "p1_reason_share": 0.7,
        "p2_count": scale(30, n, 3),
        "p3_wealth_ne_licensed": scale(180, n, 5),
        "p3_expiring": scale(25, n, 2),
        "p4_card_disputes": scale(50, n, 3),
        "p4_fraud_total": scale(150, n, 6),
        "p5_managers": scale(8, n, 2),
        "p6_processing": scale(400, n, 8),
        "p6_open_reqs": scale(25, n, 2),
        "p6_reskill": scale(60, n, 3),
    }


def headcount_by_line(n: int) -> dict:
    counts = {line: int(round(n * share)) for line, share in LINE_SHARE.items()}
    drift = n - sum(counts.values())
    counts["Consumer Banking"] += drift
    return counts
