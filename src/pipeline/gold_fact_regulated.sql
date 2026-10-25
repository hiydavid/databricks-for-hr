CREATE OR REFRESH MATERIALIZED VIEW fact_license_status (
  license_id STRING COMMENT 'License identifier.',
  license_event_id STRING COMMENT 'Latest license status event id.',
  worker_id STRING COMMENT 'Employee identifier.',
  license_type STRING COMMENT 'License type, for example Series 7 or NMLS.',
  issue_date DATE COMMENT 'License issue date.',
  expiry_date DATE COMMENT 'License expiry date.',
  status STRING COMMENT 'Current status: Active, Expiring or Expired.',
  status_date DATE COMMENT 'Date of the latest status event.',
  days_to_expiry INT COMMENT 'Days from today to expiry; negative when past expiry.',
  expires_within_60_days BOOLEAN COMMENT 'TRUE when expiry is between today and 60 days out.',
  is_expired BOOLEAN COMMENT 'TRUE when the expiry date has passed or status is Expired.',
  business_line STRING COMMENT 'Business line used for row-level security.',
  region STRING COMMENT 'Region used for row-level security.',
  is_active BOOLEAN COMMENT 'TRUE when the employee is active in the latest worker snapshot.',
  termination_date DATE COMMENT 'Termination date, NULL when the employee is active.',
  site_id STRING COMMENT 'Site org unit id.',
  site_name STRING COMMENT 'Site or office name.',
  site_city STRING COMMENT 'Site city.',
  site_state STRING COMMENT 'Site state.',
  team_id STRING COMMENT 'Team org unit id.',
  team_name STRING COMMENT 'Team org unit name.',
  job_id STRING COMMENT 'Current job id.',
  job_title STRING COMMENT 'Current job title.',
  is_licensed_role BOOLEAN COMMENT 'TRUE when the current job is licensed.',
  manager_id STRING COMMENT 'Current manager worker id.'
)
COMMENT 'One row per license with current status, days to expiry and org context.'
AS SELECT
  l.license_id, l.license_event_id, l.worker_id, l.license_type, l.issue_date, l.expiry_date,
  l.status, l.status_date,
  datediff(l.expiry_date, current_date()) AS days_to_expiry,
  l.expiry_date >= current_date() AND l.expiry_date <= date_add(current_date(), 60) AS expires_within_60_days,
  l.expiry_date < current_date() OR l.status = 'Expired' AS is_expired,
  w.business_line, w.region, w.is_active, w.termination_date,
  l.site_id, o.site_name, o.city AS site_city, o.state AS site_state,
  w.team_id, w.team_name, w.job_id, w.job_title, w.is_licensed_role, w.manager_id
FROM silver_license_current l
LEFT JOIN dim_worker w ON l.worker_id = w.worker_id
LEFT JOIN dim_org o ON l.site_id = o.org_unit_id;

CREATE OR REFRESH MATERIALIZED VIEW fact_training_status (
  assignment_id STRING COMMENT 'Training assignment identifier.',
  assignment_event_id STRING COMMENT 'Latest assignment status event id.',
  worker_id STRING COMMENT 'Employee identifier.',
  course_id STRING COMMENT 'Course identifier.',
  course_name STRING COMMENT 'Course name.',
  is_mandatory BOOLEAN COMMENT 'TRUE for mandatory training.',
  regulatory_topic STRING COMMENT 'Regulatory topic, for example AML/BSA or Fair Lending.',
  assigned_date DATE COMMENT 'Assignment date.',
  due_date DATE COMMENT 'Completion due date.',
  cycle_date DATE COMMENT 'Training cycle date.',
  status STRING COMMENT 'Current status: Assigned or Completed.',
  status_date DATE COMMENT 'Date of the latest status event.',
  completed_date DATE COMMENT 'Completion date; NULL when not completed.',
  is_completed BOOLEAN COMMENT 'TRUE when the assignment is complete.',
  is_overdue BOOLEAN COMMENT 'TRUE when mandatory, incomplete and past due.',
  days_overdue INT COMMENT 'Days past due for overdue assignments, otherwise 0.',
  business_line STRING COMMENT 'Business line used for row-level security.',
  region STRING COMMENT 'Region used for row-level security.',
  is_active BOOLEAN COMMENT 'TRUE when the employee is active in the latest worker snapshot.',
  termination_date DATE COMMENT 'Termination date, NULL when the employee is active.',
  site_id STRING COMMENT 'Site org unit id.',
  site_name STRING COMMENT 'Site or office name.',
  site_city STRING COMMENT 'Site city.',
  site_state STRING COMMENT 'Site state.',
  team_id STRING COMMENT 'Team org unit id.',
  team_name STRING COMMENT 'Team org unit name.',
  job_id STRING COMMENT 'Current job id.',
  job_title STRING COMMENT 'Current job title.',
  manager_id STRING COMMENT 'Current manager worker id.'
)
COMMENT 'One row per training assignment with current status, completion date and overdue flag.'
AS SELECT
  t.assignment_id, t.assignment_event_id, t.worker_id, t.course_id, t.course_name,
  t.is_mandatory, t.regulatory_topic, t.assigned_date, t.due_date, t.cycle_date,
  t.status, t.status_date, t.completed_date,
  t.completed_date IS NOT NULL OR t.status = 'Completed' AS is_completed,
  t.is_mandatory AND t.completed_date IS NULL AND t.status <> 'Completed' AND t.due_date < current_date() AS is_overdue,
  CASE WHEN t.is_mandatory AND t.completed_date IS NULL AND t.status <> 'Completed' AND t.due_date < current_date()
       THEN datediff(current_date(), t.due_date) ELSE 0 END AS days_overdue,
  w.business_line, w.region, w.is_active, w.termination_date,
  t.site_id, o.site_name, o.city AS site_city, o.state AS site_state,
  w.team_id, w.team_name, w.job_id, w.job_title, w.manager_id
FROM silver_training_current t
LEFT JOIN dim_worker w ON t.worker_id = w.worker_id
LEFT JOIN dim_org o ON t.site_id = o.org_unit_id;

CREATE OR REFRESH MATERIALIZED VIEW fact_requisition (
  requisition_id STRING COMMENT 'Requisition identifier.',
  job_id STRING COMMENT 'Job identifier.',
  job_title STRING COMMENT 'Job title.',
  job_family STRING COMMENT 'Job family.',
  job_level INT COMMENT 'Job level.',
  is_licensed_role BOOLEAN COMMENT 'TRUE when the role is licensed.',
  business_line STRING COMMENT 'Business line used for row-level security.',
  region STRING COMMENT 'Region used for row-level security.',
  org_unit_id STRING COMMENT 'Org unit the role belongs to.',
  site_id STRING COMMENT 'Resolved site org unit id.',
  site_name STRING COMMENT 'Site or office name.',
  site_city STRING COMMENT 'Site city.',
  site_state STRING COMMENT 'Site state.',
  hiring_manager_id STRING COMMENT 'Hiring manager worker id.',
  opened_date DATE COMMENT 'Requisition open date.',
  closed_date DATE COMMENT 'Requisition close date; NULL when open.',
  status STRING COMMENT 'Open, Filled or Cancelled.',
  filled_by_worker_id STRING COMMENT 'Worker who filled the requisition.',
  days_to_fill INT COMMENT 'Calendar days from open to close for filled roles.',
  days_open INT COMMENT 'Calendar days open for currently open roles.',
  applied_count INT COMMENT 'Candidates who reached Applied.',
  screening_count INT COMMENT 'Candidates who reached Screening.',
  interview_count INT COMMENT 'Candidates who reached Interview.',
  offer_count INT COMMENT 'Candidates who reached Offer.',
  past_screening_count INT COMMENT 'Candidates who reached Interview or Offer.',
  offer_rate DOUBLE COMMENT 'Offers divided by applications.'
)
COMMENT 'One row per requisition with time to fill, status and candidate funnel counts.'
AS WITH funnel AS (
  SELECT
    requisition_id,
    COUNT(DISTINCT CASE WHEN stage = 'Applied' THEN candidate_id END) AS applied_count,
    COUNT(DISTINCT CASE WHEN stage = 'Screening' THEN candidate_id END) AS screening_count,
    COUNT(DISTINCT CASE WHEN stage = 'Interview' THEN candidate_id END) AS interview_count,
    COUNT(DISTINCT CASE WHEN stage = 'Offer' THEN candidate_id END) AS offer_count,
    COUNT(DISTINCT CASE WHEN stage IN ('Interview', 'Offer') THEN candidate_id END) AS past_screening_count
  FROM silver_candidates
  GROUP BY requisition_id
)
SELECT
  q.requisition_id, q.job_id, j.title AS job_title, j.job_family, j.job_level, j.is_licensed_role,
  q.business_line, q.region, q.org_unit_id, o.site_id, o.site_name, o.city AS site_city, o.state AS site_state,
  q.hiring_manager_id, q.opened_date, q.closed_date, q.status, q.filled_by_worker_id,
  CASE WHEN q.status = 'Filled' THEN datediff(q.closed_date, q.opened_date) END AS days_to_fill,
  CASE WHEN q.status = 'Open' THEN datediff(current_date(), q.opened_date) END AS days_open,
  CAST(COALESCE(f.applied_count, 0) AS INT) AS applied_count,
  CAST(COALESCE(f.screening_count, 0) AS INT) AS screening_count,
  CAST(COALESCE(f.interview_count, 0) AS INT) AS interview_count,
  CAST(COALESCE(f.offer_count, 0) AS INT) AS offer_count,
  CAST(COALESCE(f.past_screening_count, 0) AS INT) AS past_screening_count,
  CASE WHEN COALESCE(f.applied_count, 0) > 0
       THEN COALESCE(f.offer_count, 0) / f.applied_count ELSE 0 END AS offer_rate
FROM silver_requisitions_current q
LEFT JOIN dim_job j ON q.job_id = j.job_id
LEFT JOIN dim_org o ON q.org_unit_id = o.org_unit_id
LEFT JOIN funnel f ON q.requisition_id = f.requisition_id;
