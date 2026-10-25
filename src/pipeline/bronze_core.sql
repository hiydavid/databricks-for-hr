-- Bronze: append-only JSONL ingestion, one streaming table per source folder.
-- All source columns are typed as STRING here; silver performs the casts so
-- that empty strings can be converted to NULL in one place.

CREATE OR REFRESH STREAMING TABLE bronze_org_units
COMMENT 'Raw org_units JSONL rows from the Aita raw volume.'
AS SELECT *,
  _metadata.file_path AS source_file_path,
  _metadata.file_modification_time AS source_file_modified_at,
  current_timestamp() AS ingest_ts
FROM STREAM read_files('${raw_volume}/org_units', format => 'json',
  schemaHints => 'org_unit_id STRING, name STRING, unit_type STRING, parent_org_unit_id STRING, business_line STRING, region STRING, site_type STRING, city STRING, state STRING',
  inferColumnTypes => false);

CREATE OR REFRESH STREAMING TABLE bronze_pay_bands
COMMENT 'Raw pay_bands JSONL rows from the Aita raw volume.'
AS SELECT *,
  _metadata.file_path AS source_file_path,
  _metadata.file_modification_time AS source_file_modified_at,
  current_timestamp() AS ingest_ts
FROM STREAM read_files('${raw_volume}/pay_bands', format => 'json',
  schemaHints => 'pay_band_id STRING, band_min STRING, band_mid STRING, band_max STRING, effective_date STRING',
  inferColumnTypes => false);

CREATE OR REFRESH STREAMING TABLE bronze_jobs
COMMENT 'Raw jobs JSONL rows from the Aita raw volume.'
AS SELECT *,
  _metadata.file_path AS source_file_path,
  _metadata.file_modification_time AS source_file_modified_at,
  current_timestamp() AS ingest_ts
FROM STREAM read_files('${raw_volume}/jobs', format => 'json',
  schemaHints => 'job_id STRING, title STRING, job_family STRING, job_level STRING, business_line STRING, region STRING, is_people_manager STRING, is_licensed_role STRING, required_license_type STRING, pay_band_id STRING, created_date STRING, job_description STRING',
  inferColumnTypes => false);

CREATE OR REFRESH STREAMING TABLE bronze_workers (
  CONSTRAINT valid_business_line EXPECT (
    business_line IN ('Consumer Banking','Operations','Wealth Management','Technology','Commercial Banking','Corporate Functions')
  )
)
COMMENT 'Raw workers snapshot JSONL rows from the Aita raw volume.'
AS SELECT *,
  _metadata.file_path AS source_file_path,
  _metadata.file_modification_time AS source_file_modified_at,
  current_timestamp() AS ingest_ts
FROM STREAM read_files('${raw_volume}/workers', format => 'json',
  schemaHints => 'worker_id STRING, first_name STRING, last_name STRING, work_email STRING, phone STRING, home_postal_code STRING, hire_date STRING, employment_type STRING, manager_id STRING, title STRING, is_manager STRING, hire_job_id STRING, hire_manager_id STRING, job_id STRING, job_level STRING, site_id STRING, team_id STRING, work_mode STRING, status STRING, termination_date STRING, termination_type STRING, updated_date STRING, business_line STRING, region STRING',
  inferColumnTypes => false);

CREATE OR REFRESH STREAMING TABLE bronze_worker_events (
  CONSTRAINT valid_business_line EXPECT (
    business_line IN ('Consumer Banking','Operations','Wealth Management','Technology','Commercial Banking','Corporate Functions')
  )
)
COMMENT 'Raw worker state events from the Aita raw volume. Source for SCD2 history.'
AS SELECT *,
  _metadata.file_path AS source_file_path,
  _metadata.file_modification_time AS source_file_modified_at,
  current_timestamp() AS ingest_ts
FROM STREAM read_files('${raw_volume}/worker_events', format => 'json',
  schemaHints => 'event_id STRING, event_seq STRING, worker_id STRING, event_type STRING, effective_date STRING, job_id STRING, org_unit_id STRING, manager_id STRING, business_line STRING, region STRING, work_mode STRING, termination_type STRING, last_promotion_date STRING',
  inferColumnTypes => false);

CREATE OR REFRESH STREAMING TABLE bronze_compensation
COMMENT 'Raw compensation events from the Aita raw volume.'
AS SELECT *,
  _metadata.file_path AS source_file_path,
  _metadata.file_modification_time AS source_file_modified_at,
  current_timestamp() AS ingest_ts
FROM STREAM read_files('${raw_volume}/compensation', format => 'json',
  schemaHints => 'comp_event_id STRING, worker_id STRING, effective_date STRING, base_salary STRING, change_reason STRING, business_line STRING, region STRING',
  inferColumnTypes => false);

CREATE OR REFRESH STREAMING TABLE bronze_performance_reviews
COMMENT 'Raw annual performance reviews from the Aita raw volume.'
AS SELECT *,
  _metadata.file_path AS source_file_path,
  _metadata.file_modification_time AS source_file_modified_at,
  current_timestamp() AS ingest_ts
FROM STREAM read_files('${raw_volume}/performance_reviews', format => 'json',
  schemaHints => 'review_id STRING, worker_id STRING, review_year STRING, rating STRING, reviewer_id STRING, review_date STRING, manager_comment STRING, business_line STRING, region STRING',
  inferColumnTypes => false);

CREATE OR REFRESH STREAMING TABLE bronze_engagement_responses
COMMENT 'Raw quarterly engagement survey responses from the Aita raw volume.'
AS SELECT *,
  _metadata.file_path AS source_file_path,
  _metadata.file_modification_time AS source_file_modified_at,
  current_timestamp() AS ingest_ts
FROM STREAM read_files('${raw_volume}/engagement_responses', format => 'json',
  schemaHints => 'response_id STRING, worker_id STRING, wave_id STRING, wave_date STRING, engagement_index STRING, q_manager STRING, q_workload STRING, q_growth STRING, q_recommend STRING, comment STRING, business_line STRING, region STRING',
  inferColumnTypes => false);
