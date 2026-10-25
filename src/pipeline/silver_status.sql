-- Silver status histories, snapshots and recruiting inputs.

CREATE OR REFRESH STREAMING TABLE silver_licenses_history (
  CONSTRAINT license_expiry_after_issue EXPECT (expiry_date > issue_date) ON VIOLATION DROP ROW
)
COMMENT 'Typed license status history; rows with expiry before issue are dropped.'
AS SELECT
  license_id, license_event_id, worker_id, license_type,
  CAST(NULLIF(issue_date, '') AS DATE) AS issue_date,
  CAST(NULLIF(expiry_date, '') AS DATE) AS expiry_date,
  status,
  CAST(NULLIF(status_date, '') AS DATE) AS status_date,
  NULLIF(business_line, '') AS business_line,
  NULLIF(region, '') AS region,
  site_id
FROM STREAM(bronze_licenses)
WHERE license_id IS NOT NULL;

CREATE OR REFRESH MATERIALIZED VIEW silver_license_current
COMMENT 'Latest license status row per license_id.'
AS SELECT * FROM silver_licenses_history
QUALIFY ROW_NUMBER() OVER (PARTITION BY license_id ORDER BY status_date DESC, license_event_id DESC) = 1;

CREATE OR REFRESH STREAMING TABLE silver_training_history
COMMENT 'Typed mandatory training status history. Completion date comes from completed_date.'
AS SELECT
  assignment_id, assignment_event_id, worker_id, course_id, course_name,
  CAST(NULLIF(is_mandatory, '') AS BOOLEAN) AS is_mandatory,
  NULLIF(regulatory_topic, '') AS regulatory_topic,
  CAST(NULLIF(assigned_date, '') AS DATE) AS assigned_date,
  CAST(NULLIF(due_date, '') AS DATE) AS due_date,
  CAST(NULLIF(cycle_date, '') AS DATE) AS cycle_date,
  status,
  CAST(NULLIF(status_date, '') AS DATE) AS status_date,
  CAST(NULLIF(completed_date, '') AS DATE) AS completed_date,
  NULLIF(business_line, '') AS business_line,
  NULLIF(region, '') AS region,
  site_id
FROM STREAM(bronze_training_assignments)
WHERE assignment_id IS NOT NULL;

CREATE OR REFRESH MATERIALIZED VIEW silver_training_current
COMMENT 'Latest training status row per assignment_id, with completion taken from completed_date.'
AS SELECT * FROM silver_training_history
QUALIFY ROW_NUMBER() OVER (PARTITION BY assignment_id ORDER BY status_date DESC, assignment_event_id DESC) = 1;

CREATE OR REFRESH STREAMING TABLE silver_requisitions
COMMENT 'Typed requisition snapshot rows.'
AS SELECT
  requisition_id, job_id, org_unit_id,
  NULLIF(hiring_manager_id, '') AS hiring_manager_id,
  CAST(NULLIF(opened_date, '') AS DATE) AS opened_date,
  CAST(NULLIF(closed_date, '') AS DATE) AS closed_date,
  status,
  NULLIF(filled_by_worker_id, '') AS filled_by_worker_id,
  NULLIF(business_line, '') AS business_line,
  NULLIF(region, '') AS region,
  CAST(NULLIF(updated_date, '') AS DATE) AS updated_date,
  ingest_ts
FROM STREAM(bronze_requisitions)
WHERE requisition_id IS NOT NULL;

CREATE OR REFRESH MATERIALIZED VIEW silver_requisitions_current
COMMENT 'Latest requisition snapshot per requisition_id.'
AS SELECT * FROM silver_requisitions
QUALIFY ROW_NUMBER() OVER (PARTITION BY requisition_id ORDER BY updated_date DESC, ingest_ts DESC) = 1;

CREATE OR REFRESH STREAMING TABLE silver_candidates
COMMENT 'Typed candidate stage events, one row per candidate and stage.'
AS SELECT
  candidate_id, requisition_id,
  NULLIF(worker_id, '') AS worker_id,
  stage,
  CAST(NULLIF(stage_date, '') AS DATE) AS stage_date,
  NULLIF(source, '') AS source,
  NULLIF(business_line, '') AS business_line,
  NULLIF(region, '') AS region
FROM STREAM(bronze_candidates)
WHERE candidate_id IS NOT NULL;

CREATE OR REFRESH STREAMING TABLE silver_productivity
COMMENT 'Typed completed worker-week productivity rows.'
AS SELECT
  worker_id,
  CAST(NULLIF(week_start, '') AS DATE) AS week_start,
  CAST(NULLIF(week_end, '') AS DATE) AS week_end,
  CAST(NULLIF(scheduled_hours, '') AS DOUBLE) AS scheduled_hours,
  CAST(NULLIF(overtime_hours, '') AS DOUBLE) AS overtime_hours,
  CAST(NULLIF(output_units, '') AS INT) AS output_units,
  NULLIF(business_line, '') AS business_line,
  NULLIF(region, '') AS region,
  team_id
FROM STREAM(bronze_productivity)
WHERE worker_id IS NOT NULL;
