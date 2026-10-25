-- Bronze for recruiting, regulated workforce, productivity and site events.

CREATE OR REFRESH STREAMING TABLE bronze_exit_interviews
COMMENT 'Raw voluntary exit interviews from the Aita raw volume.'
AS SELECT *,
  _metadata.file_path AS source_file_path,
  _metadata.file_modification_time AS source_file_modified_at,
  current_timestamp() AS ingest_ts
FROM STREAM read_files('${raw_volume}/exit_interviews', format => 'json',
  schemaHints => 'exit_interview_id STRING, worker_id STRING, termination_date STRING, interview_date STRING, comment STRING, business_line STRING, region STRING, site_id STRING, team_id STRING',
  inferColumnTypes => false);

CREATE OR REFRESH STREAMING TABLE bronze_licenses
COMMENT 'Raw license status history from the Aita raw volume.'
AS SELECT *,
  _metadata.file_path AS source_file_path,
  _metadata.file_modification_time AS source_file_modified_at,
  current_timestamp() AS ingest_ts
FROM STREAM read_files('${raw_volume}/licenses', format => 'json',
  schemaHints => 'license_id STRING, license_event_id STRING, worker_id STRING, license_type STRING, issue_date STRING, expiry_date STRING, status STRING, status_date STRING, business_line STRING, region STRING, site_id STRING',
  inferColumnTypes => false);

CREATE OR REFRESH STREAMING TABLE bronze_training_assignments
COMMENT 'Raw mandatory training assignment status history from the Aita raw volume.'
AS SELECT *,
  _metadata.file_path AS source_file_path,
  _metadata.file_modification_time AS source_file_modified_at,
  current_timestamp() AS ingest_ts
FROM STREAM read_files('${raw_volume}/training_assignments', format => 'json',
  schemaHints => 'assignment_id STRING, assignment_event_id STRING, worker_id STRING, course_id STRING, course_name STRING, is_mandatory STRING, regulatory_topic STRING, assigned_date STRING, due_date STRING, cycle_date STRING, status STRING, status_date STRING, completed_date STRING, business_line STRING, region STRING, site_id STRING',
  inferColumnTypes => false);

CREATE OR REFRESH STREAMING TABLE bronze_requisitions
COMMENT 'Raw requisition snapshots from the Aita raw volume.'
AS SELECT *,
  _metadata.file_path AS source_file_path,
  _metadata.file_modification_time AS source_file_modified_at,
  current_timestamp() AS ingest_ts
FROM STREAM read_files('${raw_volume}/requisitions', format => 'json',
  schemaHints => 'requisition_id STRING, job_id STRING, org_unit_id STRING, hiring_manager_id STRING, opened_date STRING, closed_date STRING, status STRING, filled_by_worker_id STRING, business_line STRING, region STRING, updated_date STRING',
  inferColumnTypes => false);

CREATE OR REFRESH STREAMING TABLE bronze_candidates
COMMENT 'Raw candidate stage events from the Aita raw volume.'
AS SELECT *,
  _metadata.file_path AS source_file_path,
  _metadata.file_modification_time AS source_file_modified_at,
  current_timestamp() AS ingest_ts
FROM STREAM read_files('${raw_volume}/candidates', format => 'json',
  schemaHints => 'candidate_id STRING, requisition_id STRING, worker_id STRING, stage STRING, stage_date STRING, source STRING, business_line STRING, region STRING',
  inferColumnTypes => false);

CREATE OR REFRESH STREAMING TABLE bronze_productivity
COMMENT 'Raw completed worker-week productivity rows from the Aita raw volume.'
AS SELECT *,
  _metadata.file_path AS source_file_path,
  _metadata.file_modification_time AS source_file_modified_at,
  current_timestamp() AS ingest_ts
FROM STREAM read_files('${raw_volume}/productivity', format => 'json',
  schemaHints => 'worker_id STRING, week_start STRING, week_end STRING, scheduled_hours STRING, overtime_hours STRING, output_units STRING, business_line STRING, region STRING, team_id STRING',
  inferColumnTypes => false);

CREATE OR REFRESH STREAMING TABLE bronze_site_events
COMMENT 'Raw site events, including contact-centre schedule changes, from the Aita raw volume.'
AS SELECT *,
  _metadata.file_path AS source_file_path,
  _metadata.file_modification_time AS source_file_modified_at,
  current_timestamp() AS ingest_ts
FROM STREAM read_files('${raw_volume}/site_events', format => 'json',
  schemaHints => 'site_event_id STRING, org_unit_id STRING, event_date STRING, event_type STRING, description STRING, business_line STRING, region STRING',
  inferColumnTypes => false);
