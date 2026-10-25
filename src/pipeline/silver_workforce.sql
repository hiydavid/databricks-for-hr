-- Silver workforce inputs. Snapshot rows stay append-only; the *_current
-- materialized view keeps the latest snapshot per natural key.

CREATE OR REFRESH STREAMING TABLE silver_workers
COMMENT 'Typed worker snapshot rows, one row per generator snapshot append.'
AS SELECT
  worker_id,
  NULLIF(first_name, '') AS first_name,
  NULLIF(last_name, '') AS last_name,
  NULLIF(work_email, '') AS work_email,
  NULLIF(phone, '') AS phone,
  NULLIF(home_postal_code, '') AS home_postal_code,
  CAST(NULLIF(hire_date, '') AS DATE) AS hire_date,
  NULLIF(employment_type, '') AS employment_type,
  NULLIF(manager_id, '') AS manager_id,
  title,
  CAST(NULLIF(is_manager, '') AS BOOLEAN) AS is_manager,
  NULLIF(hire_job_id, '') AS hire_job_id,
  NULLIF(hire_manager_id, '') AS hire_manager_id,
  job_id,
  CAST(NULLIF(job_level, '') AS INT) AS job_level,
  site_id,
  team_id,
  NULLIF(work_mode, '') AS work_mode,
  status,
  CAST(NULLIF(termination_date, '') AS DATE) AS termination_date,
  NULLIF(termination_type, '') AS termination_type,
  CAST(NULLIF(updated_date, '') AS DATE) AS updated_date,
  NULLIF(business_line, '') AS business_line,
  NULLIF(region, '') AS region,
  source_file_path,
  ingest_ts
FROM STREAM(bronze_workers)
WHERE worker_id IS NOT NULL;

CREATE OR REFRESH MATERIALIZED VIEW silver_workers_current
COMMENT 'Latest worker snapshot per worker. Retail Banking labels are recovered from the org unit.'
AS WITH latest AS (
  SELECT * FROM silver_workers
  QUALIFY ROW_NUMBER() OVER (PARTITION BY worker_id ORDER BY updated_date DESC, ingest_ts DESC) = 1
)
SELECT
  l.worker_id, l.first_name, l.last_name, l.work_email, l.phone, l.home_postal_code,
  l.hire_date, l.employment_type, l.manager_id, l.title, l.is_manager,
  l.hire_job_id, l.hire_manager_id, l.job_id, l.job_level, l.site_id, l.team_id,
  l.work_mode, l.status, l.termination_date, l.termination_type, l.updated_date,
  COALESCE(
    CASE WHEN l.business_line IN ('Consumer Banking','Operations','Wealth Management','Technology','Commercial Banking','Corporate Functions')
         THEN l.business_line END,
    o.business_line) AS business_line,
  COALESCE(l.region, s.region) AS region,
  o.org_unit_name AS team_name,
  s.org_unit_name AS site_name,
  s.city AS site_city,
  s.state AS site_state,
  s.site_type
FROM latest l
LEFT JOIN silver_org_units o ON l.team_id = o.org_unit_id
LEFT JOIN silver_org_units s ON l.site_id = s.org_unit_id;

CREATE OR REFRESH STREAMING TABLE silver_compensation
COMMENT 'Typed compensation events.'
AS SELECT
  comp_event_id, worker_id,
  CAST(NULLIF(effective_date, '') AS DATE) AS effective_date,
  CAST(NULLIF(base_salary, '') AS INT) AS base_salary,
  NULLIF(change_reason, '') AS change_reason,
  NULLIF(business_line, '') AS business_line,
  NULLIF(region, '') AS region
FROM STREAM(bronze_compensation)
WHERE comp_event_id IS NOT NULL;

CREATE OR REFRESH STREAMING TABLE silver_performance_reviews
COMMENT 'Typed annual performance reviews with optional manager comments.'
AS SELECT
  review_id, worker_id,
  CAST(NULLIF(review_year, '') AS INT) AS review_year,
  CAST(NULLIF(rating, '') AS INT) AS rating,
  NULLIF(reviewer_id, '') AS reviewer_id,
  CAST(NULLIF(review_date, '') AS DATE) AS review_date,
  NULLIF(manager_comment, '') AS manager_comment,
  NULLIF(business_line, '') AS business_line,
  NULLIF(region, '') AS region
FROM STREAM(bronze_performance_reviews)
WHERE review_id IS NOT NULL;

CREATE OR REFRESH STREAMING TABLE silver_engagement_responses
COMMENT 'Typed quarterly engagement survey responses with optional comments.'
AS SELECT
  response_id, worker_id, wave_id,
  CAST(NULLIF(wave_date, '') AS DATE) AS wave_date,
  CAST(NULLIF(engagement_index, '') AS DOUBLE) AS engagement_index,
  CAST(NULLIF(q_manager, '') AS DOUBLE) AS q_manager,
  CAST(NULLIF(q_workload, '') AS DOUBLE) AS q_workload,
  CAST(NULLIF(q_growth, '') AS DOUBLE) AS q_growth,
  CAST(NULLIF(q_recommend, '') AS DOUBLE) AS q_recommend,
  NULLIF(comment, '') AS comment,
  NULLIF(business_line, '') AS business_line,
  NULLIF(region, '') AS region
FROM STREAM(bronze_engagement_responses)
WHERE response_id IS NOT NULL;

CREATE OR REFRESH STREAMING TABLE silver_exit_interviews
COMMENT 'Typed voluntary exit interviews with free-text comments.'
AS SELECT
  exit_interview_id, worker_id,
  CAST(NULLIF(termination_date, '') AS DATE) AS termination_date,
  CAST(NULLIF(interview_date, '') AS DATE) AS interview_date,
  NULLIF(comment, '') AS comment,
  NULLIF(business_line, '') AS business_line,
  NULLIF(region, '') AS region,
  site_id,
  team_id
FROM STREAM(bronze_exit_interviews)
WHERE exit_interview_id IS NOT NULL;
