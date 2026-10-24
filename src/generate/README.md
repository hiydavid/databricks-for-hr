# Synthetic HR data generator

Generates HR data for a fictional bank of about 5,000 employees and writes it as JSON lines files to the `genie_workbench_dev_catalog.aita.raw` volume. The pipeline in `src/pipeline/` ingests those files. The generator never writes features, labels or classifications: everything the model and Genie Agents learn comes through the pipeline.

Planted patterns and the questions they answer are in [PATTERNS.md](PATTERNS.md).

## Run modes

| Mode | When | What it writes |
|---|---|---|
| `seed` | Once | Current org, jobs and workforce plus 24 months of history ending yesterday |
| `increment` | First task of `aita_nightly` | Every day after the last generated day, up to yesterday (normally one day) |

```
python -m generate --mode seed      --num-employees 5000 --seed 42 --output /Volumes/genie_workbench_dev_catalog/aita/raw
python -m generate --mode increment --seed 42 --output /Volumes/genie_workbench_dev_catalog/aita/raw
```

- Each run writes new files (`<dataset>/<mode>_<yyyymmdd>.jsonl`) and never edits old ones, so bronze picks up only what's new.
- The increment mode resumes from `_state/` (current workforce and last generated date) written by the previous run. The pipeline does not read `_state/`.
- Randomness is seeded from `(seed, date)`, so the same seed and dates produce identical files.
- Pattern dates are offsets from the seed end date, so the story stays inside the current year whenever the seed runs.
- Plain Python (numpy, pandas). Runs locally against a folder for tests, or as a serverless job task.

## Bank structure

Six business lines across four regions (Northeast, Southeast, Midwest, West).

| Business line | ~Headcount | Sites and roles |
|---|---|---|
| Consumer Banking | 1,800 | ~60 branches; contact centers in Charlotte, Phoenix, Columbus (~200 each) |
| Operations | 1,000 | Payments, deposit and loan operations; fraud operations (~150) |
| Wealth Management | 700 | Licensed advisors in regional offices |
| Technology | 600 | Engineering, infrastructure, AI and data (~80) |
| Commercial Banking | 500 | Relationship managers, credit analysts |
| Corporate Functions | 400 | HR, finance, risk, compliance, legal |

Baseline voluntary attrition is about 12% a year (about 3% in any 90-day window), higher in contact centers and lower in corporate roles.

## Datasets

One folder per dataset. Every employee-level record carries `business_line` and `region`, so row filters and the Watchlist can scope by them.

| Dataset | Grain | Key columns | Free text |
|---|---|---|---|
| `org_units` | Org unit | org_unit_id, name, unit_type, parent_org_unit_id, business_line, region, site_type, city, state | |
| `jobs` | Job | job_id, title, job_family, job_level, business_line, is_people_manager, is_licensed_role, required_license_type, pay_band_id | job_description |
| `pay_bands` | Band | pay_band_id, band_min, band_mid, band_max, effective_date | |
| `workers` | Person | worker_id, first_name, last_name, work_email, phone, home_postal_code, hire_date, employment_type | |
| `worker_events` | Change event | event_id, worker_id, event_type, effective_date, job_id, org_unit_id, manager_id, business_line, region, work_mode, termination_type, last_promotion_date | |
| `compensation` | Pay change | comp_event_id, worker_id, effective_date, base_salary, change_reason | |
| `performance_reviews` | Annual review | review_id, worker_id, review_year, rating (1-5), reviewer_id, review_date | manager_comment (~10%) |
| `engagement_responses` | Survey response | response_id, worker_id, wave_id, wave_date, engagement_index, q_manager, q_workload, q_growth, q_recommend | comment (~25%) |
| `exit_interviews` | Voluntary exit | exit_interview_id, worker_id, termination_date, interview_date | comment |
| `licenses` | License | license_id, worker_id, license_type, issue_date, expiry_date, status | |
| `training_assignments` | Assignment | assignment_id, worker_id, course_id, course_name, is_mandatory, regulatory_topic, assigned_date, due_date, completed_date | |
| `requisitions` | Requisition | requisition_id, job_id, org_unit_id, hiring_manager_id, opened_date, closed_date, status, filled_by_worker_id | |
| `candidates` | Stage change | candidate_id, requisition_id, worker_id (internal only), stage, stage_date, source | |
| `productivity` | Worker-week | worker_id, week_start, scheduled_hours, overtime_hours, output_units | |
| `site_events` | Site event | site_event_id, org_unit_id, event_date, event_type, description | |

Notes:
- `worker_events` carries the full state after each event (hire, transfer, promotion, manager_change, job_change, termination), which silver turns into SCD Type 2 history. The first event per existing employee is an `initial_state` row at the seed start, including `last_promotion_date` from before the history window.
- `termination_type` is voluntary, involuntary or retirement. There is no reason code: exit reasons come only from the exit interview text, classified in the pipeline.
- Personal fields (`first_name`, `last_name`, `work_email`, `phone`, `home_postal_code`) exist so column masks have something to hide. No protected attributes (gender, ethnicity, age, date of birth) are generated.
- Surveys are confidential, not anonymous, so responses link to `worker_id`. A real deployment would aggregate before exposing them.
- Licenses and courses are realistic banking types (Series 7, Series 66, NMLS mortgage originator, state insurance; AML/BSA, fair lending, privacy, code of conduct, continuing education).

## Volumes at 5,000 employees

| Text | Seed (24 months) | Per night |
|---|---|---|
| Exit interview comments | ~1,200 | ~2 |
| Survey comments (8 quarterly waves) | ~7,500 | 0 outside a wave |
| Manager comments (2 review cycles) | ~900 | 0 outside a cycle |
| Job descriptions | ~250 | 0 |

`productivity` is the largest table (~520k worker-weeks); weekly rows are written on Sundays.

## Free text

Comments are assembled from phrase banks in code (opening, one or two reason phrases, a specific detail, closing), with names, sites and shifts filled in. Each reason has 15-30 phrasings, and about a quarter of comments mix two reasons, so classification needs real reading. No LLM is used to write text.

The true exit reason for each interview is written to `_ground_truth/exit_reasons/`, which the pipeline never reads. It is used only to score `ai_classify` accuracy for `evidence/`.

## Planted data quality defects

Small, deliberate counts so pipeline expectations have something to catch:

| Defect | Count (seed) | Expectation |
|---|---|---|
| Duplicate `worker_events` rows | ~0.5% | Deduplicated in silver |
| Unknown `business_line` value | ~10 | Valid business line |
| `termination` before `hire_date` | ~5 | Hire date not after termination |
| License `expiry_date` before `issue_date` | ~5 | Expiry after issue |

## Tests

`pytest` runs the generator at 500 employees into a temp folder and checks that the same seed gives identical output, that every planted pattern is detectable in the raw files (see PATTERNS.md), and that the defect counts match.
