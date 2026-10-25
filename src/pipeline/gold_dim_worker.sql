CREATE OR REFRESH MATERIALIZED VIEW dim_worker (
  worker_id STRING COMMENT 'Unique employee identifier.',
  first_name STRING COMMENT 'Employee first name.',
  last_name STRING COMMENT 'Employee last name.',
  work_email STRING COMMENT 'Work email address.',
  phone STRING COMMENT 'Work phone number.',
  home_postal_code STRING COMMENT 'Employee home postal code.',
  hire_date DATE COMMENT 'Original hire date.',
  termination_date DATE COMMENT 'Termination date, NULL when still active.',
  termination_type STRING COMMENT 'Voluntary, involuntary or retirement.',
  status STRING COMMENT 'Current employment status from the latest snapshot.',
  is_active BOOLEAN COMMENT 'TRUE when status is active.',
  employment_type STRING COMMENT 'Full-time, part-time or contractor.',
  work_mode STRING COMMENT 'Onsite, hybrid or remote.',
  business_line STRING COMMENT 'Business line used for row-level security.',
  region STRING COMMENT 'Region used for row-level security.',
  site_id STRING COMMENT 'Site org unit id.',
  site_name STRING COMMENT 'Site or office name.',
  site_city STRING COMMENT 'Site city.',
  site_state STRING COMMENT 'Site state.',
  team_id STRING COMMENT 'Team org unit id.',
  team_name STRING COMMENT 'Team org unit name.',
  manager_id STRING COMMENT 'Current manager worker id.',
  manager_name STRING COMMENT 'Current manager full name.',
  job_id STRING COMMENT 'Current job id.',
  job_title STRING COMMENT 'Current job title.',
  job_family STRING COMMENT 'Current job family.',
  job_level INT COMMENT 'Current job level.',
  is_manager BOOLEAN COMMENT 'TRUE when the employee manages people.',
  is_licensed_role BOOLEAN COMMENT 'TRUE when the current job is licensed.',
  required_license_type STRING COMMENT 'License required by the current job.',
  last_promotion_date DATE COMMENT 'Most recent promotion date.',
  months_since_promotion INT COMMENT 'Completed months since the last promotion as of today.',
  tenure_months INT COMMENT 'Completed months since hire as of today.',
  valid_from TIMESTAMP COMMENT 'Timestamp the current history version became effective.'
)
COMMENT 'One row per employee: current job, org placement, personal fields and tenure.'
AS SELECT
  w.worker_id, w.first_name, w.last_name, w.work_email, w.phone, w.home_postal_code,
  w.hire_date, w.termination_date, w.termination_type, w.status,
  w.status = 'active' AS is_active,
  w.employment_type, w.work_mode, w.business_line, w.region,
  w.site_id, w.site_name, w.site_city, w.site_state, w.team_id, w.team_name,
  w.manager_id,
  concat_ws(' ', m.first_name, m.last_name) AS manager_name,
  w.job_id, j.title AS job_title, j.job_family, j.job_level, w.is_manager,
  j.is_licensed_role, j.required_license_type,
  h.last_promotion_date,
  CAST(floor(months_between(current_date(), h.last_promotion_date)) AS INT) AS months_since_promotion,
  CAST(floor(months_between(current_date(), w.hire_date)) AS INT) AS tenure_months,
  h.__START_AT AS valid_from
FROM silver_workers_current w
LEFT JOIN silver_worker_history_clean h
  ON w.worker_id = h.worker_id AND h.__END_AT IS NULL
LEFT JOIN dim_job j ON w.job_id = j.job_id
LEFT JOIN silver_workers_current m ON w.manager_id = m.worker_id;
