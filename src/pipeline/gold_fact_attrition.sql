CREATE OR REFRESH MATERIALIZED VIEW fact_attrition_event (
  event_id STRING COMMENT 'Worker event id of the termination.',
  worker_id STRING COMMENT 'Employee identifier.',
  termination_date DATE COMMENT 'Last working date.',
  termination_type STRING COMMENT 'voluntary, involuntary or retirement.',
  is_voluntary BOOLEAN COMMENT 'TRUE for voluntary terminations.',
  business_line STRING COMMENT 'Business line at termination.',
  region STRING COMMENT 'Region at termination.',
  site_id STRING COMMENT 'Site org unit id.',
  site_name STRING COMMENT 'Site or office name.',
  site_city STRING COMMENT 'Site city.',
  site_state STRING COMMENT 'Site state.',
  team_id STRING COMMENT 'Team org unit id at termination.',
  team_name STRING COMMENT 'Team org unit name.',
  job_id STRING COMMENT 'Job id at termination.',
  job_title STRING COMMENT 'Job title at termination.',
  job_family STRING COMMENT 'Job family at termination.',
  job_level INT COMMENT 'Job level at termination.',
  is_licensed_role BOOLEAN COMMENT 'TRUE when the job is licensed.',
  manager_id STRING COMMENT 'Manager worker id at termination.',
  hire_date DATE COMMENT 'Original hire date.',
  tenure_months INT COMMENT 'Completed months of tenure at termination.',
  last_promotion_date DATE COMMENT 'Most recent promotion before termination.',
  site_schedule_change_date DATE COMMENT 'Schedule-change date for the site, NULL when none.',
  is_post_schedule_change BOOLEAN COMMENT 'TRUE when the termination is on or after the site schedule change.',
  exit_interview_id STRING COMMENT 'Linked exit interview id.',
  interview_date DATE COMMENT 'Exit interview date.',
  exit_reason STRING COMMENT 'AI-classified exit reason for voluntary leavers.',
  has_exit_interview BOOLEAN COMMENT 'TRUE when an exit interview exists.',
  exit_comment STRING COMMENT 'Free-text exit interview comment.'
)
COMMENT 'One row per termination with type, org context, AI exit reason and schedule-change timing.'
AS WITH terms AS (
  SELECT worker_id, event_id, effective_date AS termination_date, termination_type,
    business_line, region, org_unit_id, job_id, manager_id, last_promotion_date
  FROM silver_worker_history_clean
  WHERE event_type = 'termination' AND __END_AT IS NULL
)
SELECT
  t.event_id, t.worker_id, t.termination_date, t.termination_type,
  t.termination_type = 'voluntary' AS is_voluntary,
  t.business_line, t.region,
  o.site_id, o.site_name, o.city AS site_city, o.state AS site_state,
  t.org_unit_id AS team_id, o.org_unit_name AS team_name,
  t.job_id, j.title AS job_title, j.job_family, j.job_level, j.is_licensed_role,
  t.manager_id, w.hire_date,
  CAST(floor(months_between(t.termination_date, w.hire_date)) AS INT) AS tenure_months,
  t.last_promotion_date,
  o.schedule_change_date AS site_schedule_change_date,
  o.schedule_change_date IS NOT NULL AND t.termination_date >= o.schedule_change_date AS is_post_schedule_change,
  x.exit_interview_id, x.interview_date,
  CASE WHEN t.termination_type = 'voluntary' THEN x.exit_reason END AS exit_reason,
  x.exit_interview_id IS NOT NULL AS has_exit_interview,
  x.comment AS exit_comment
FROM terms t
LEFT JOIN dim_worker w ON t.worker_id = w.worker_id
LEFT JOIN dim_org o ON t.org_unit_id = o.org_unit_id
LEFT JOIN dim_job j ON t.job_id = j.job_id
LEFT JOIN silver_exit_interviews_ai x
  ON t.worker_id = x.worker_id AND t.termination_date = x.termination_date;
