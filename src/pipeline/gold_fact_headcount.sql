CREATE OR REFRESH MATERIALIZED VIEW fact_headcount_monthly (
  month_end_date DATE COMMENT 'Calendar month-end snapshot date.',
  worker_id STRING COMMENT 'Employee identifier.',
  business_line STRING COMMENT 'Business line at the snapshot date.',
  region STRING COMMENT 'Region at the snapshot date.',
  site_id STRING COMMENT 'Site org unit id.',
  site_name STRING COMMENT 'Site or office name.',
  site_city STRING COMMENT 'Site city.',
  site_state STRING COMMENT 'Site state.',
  team_id STRING COMMENT 'Team org unit id at the snapshot date.',
  team_name STRING COMMENT 'Team org unit name.',
  job_id STRING COMMENT 'Job id at the snapshot date.',
  job_title STRING COMMENT 'Job title at the snapshot date.',
  job_family STRING COMMENT 'Job family at the snapshot date.',
  job_level INT COMMENT 'Job level at the snapshot date.',
  is_licensed_role BOOLEAN COMMENT 'TRUE when the job is licensed.',
  employment_type STRING COMMENT 'Full-time, part-time or contractor.',
  work_mode STRING COMMENT 'Onsite, hybrid or remote.',
  manager_id STRING COMMENT 'Manager worker id at the snapshot date.',
  hire_date DATE COMMENT 'Original hire date.',
  termination_date DATE COMMENT 'Termination date, NULL when active.',
  tenure_months INT COMMENT 'Completed months of tenure at month-end.',
  site_schedule_change_date DATE COMMENT 'Schedule-change date for the site, NULL when none.',
  headcount INT COMMENT 'Headcount contribution: always 1 for an active employee.'
)
COMMENT 'One row per active employee per calendar month-end, using point-in-time SCD2 state.'
AS WITH months AS (
  SELECT month_end AS month_end_date,
    cast(month_end AS TIMESTAMP) + INTERVAL 1 DAY - INTERVAL 1 SECOND AS snapshot_ts
  FROM dim_date
  WHERE is_month_end AND month_end <= current_date()
),
versions AS (
  SELECT worker_id, business_line, region, org_unit_id, job_id, manager_id, work_mode,
    __START_AT, __END_AT
  FROM silver_worker_history_clean
  WHERE event_type <> 'termination'
)
SELECT
  m.month_end_date, v.worker_id, v.business_line, v.region,
  o.site_id, o.site_name, o.city AS site_city, o.state AS site_state,
  v.org_unit_id AS team_id, o.org_unit_name AS team_name,
  v.job_id, j.title AS job_title, j.job_family, j.job_level, j.is_licensed_role,
  w.employment_type, v.work_mode, v.manager_id, w.hire_date, w.termination_date,
  CAST(floor(months_between(m.month_end_date, w.hire_date)) AS INT) AS tenure_months,
  o.schedule_change_date AS site_schedule_change_date,
  1 AS headcount
FROM months m
JOIN versions v
  ON v.__START_AT <= m.snapshot_ts
 AND (v.__END_AT > m.snapshot_ts OR v.__END_AT IS NULL)
LEFT JOIN dim_worker w ON v.worker_id = w.worker_id
LEFT JOIN dim_org o ON v.org_unit_id = o.org_unit_id
LEFT JOIN dim_job j ON v.job_id = j.job_id;
