CREATE OR REFRESH MATERIALIZED VIEW fact_performance (
  review_id STRING COMMENT 'Performance review identifier.',
  worker_id STRING COMMENT 'Employee identifier.',
  review_year INT COMMENT 'Review cycle year.',
  review_date DATE COMMENT 'Review date.',
  rating INT COMMENT 'Performance rating, 1 to 5.',
  reviewer_id STRING COMMENT 'Reviewer worker id.',
  manager_comment STRING COMMENT 'Free-text manager comment.',
  skills ARRAY<STRING> COMMENT 'Skills AI-extracted from the manager comment.',
  is_latest_review BOOLEAN COMMENT 'TRUE for the most recent review per employee.',
  business_line STRING COMMENT 'Business line used for row-level security.',
  region STRING COMMENT 'Region used for row-level security.',
  site_id STRING COMMENT 'Site org unit id.',
  site_name STRING COMMENT 'Site or office name.',
  site_city STRING COMMENT 'Site city.',
  site_state STRING COMMENT 'Site state.',
  team_id STRING COMMENT 'Team org unit id.',
  team_name STRING COMMENT 'Team org unit name.',
  job_id STRING COMMENT 'Job id at review time.',
  job_title STRING COMMENT 'Job title at review time.',
  job_family STRING COMMENT 'Job family at review time.',
  job_level INT COMMENT 'Job level at review time.',
  is_licensed_role BOOLEAN COMMENT 'TRUE when the job is licensed.',
  manager_id STRING COMMENT 'Manager worker id as of the review date.',
  last_promotion_date DATE COMMENT 'Most recent promotion date as of the review date.',
  months_since_promotion_at_review INT COMMENT 'Completed months since promotion at review date.',
  tenure_months INT COMMENT 'Completed months of tenure at review date.',
  base_salary INT COMMENT 'Current annual base salary.',
  pay_band_id STRING COMMENT 'Current pay band id.',
  band_min INT COMMENT 'Current pay band minimum.',
  band_mid INT COMMENT 'Current pay band midpoint.',
  band_max INT COMMENT 'Current pay band maximum.',
  pay_to_midpoint DOUBLE COMMENT 'Current salary divided by band midpoint.',
  pay_position STRING COMMENT 'below_mid below 1.00, at_mid 1.00 to 1.05, above_mid above 1.05; NULL when pay is unknown.'
)
COMMENT 'One row per performance review with AI skills, current pay position and promotion timing.'
AS SELECT
  r.review_id, r.worker_id, r.review_year, r.review_date, r.rating, r.reviewer_id,
  r.manager_comment, a.skills,
  ROW_NUMBER() OVER (PARTITION BY r.worker_id ORDER BY r.review_date DESC, r.review_id DESC) = 1 AS is_latest_review,
  h.business_line, h.region, o.site_id, o.site_name, o.city AS site_city, o.state AS site_state,
  h.org_unit_id AS team_id, o.org_unit_name AS team_name,
  h.job_id, j.title AS job_title, j.job_family, j.job_level,
  j.is_licensed_role, h.manager_id, h.last_promotion_date,
  CAST(floor(months_between(r.review_date, h.last_promotion_date)) AS INT) AS months_since_promotion_at_review,
  CAST(floor(months_between(r.review_date, w.hire_date)) AS INT) AS tenure_months,
  c.base_salary, c.pay_band_id, c.band_min, c.band_mid, c.band_max,
  c.pay_to_midpoint,
  CASE WHEN c.pay_to_midpoint IS NULL THEN NULL
       WHEN c.pay_to_midpoint < 1 THEN 'below_mid'
       WHEN c.pay_to_midpoint <= 1.05 THEN 'at_mid'
       ELSE 'above_mid' END AS pay_position
FROM silver_performance_reviews r
LEFT JOIN silver_performance_ai a ON r.review_id = a.review_id
LEFT JOIN silver_worker_history_clean h
  ON r.worker_id = h.worker_id
 AND h.__START_AT <= CAST(r.review_date AS TIMESTAMP) + INTERVAL 1 DAY - INTERVAL 1 SECOND
 AND (h.__END_AT > CAST(r.review_date AS TIMESTAMP) + INTERVAL 1 DAY - INTERVAL 1 SECOND OR h.__END_AT IS NULL)
LEFT JOIN dim_org o ON h.org_unit_id = o.org_unit_id
LEFT JOIN dim_job j ON h.job_id = j.job_id
LEFT JOIN dim_worker w ON r.worker_id = w.worker_id
LEFT JOIN fact_compensation c ON r.worker_id = c.worker_id AND c.is_current;

CREATE OR REFRESH MATERIALIZED VIEW fact_compensation (
  comp_event_id STRING COMMENT 'Compensation event identifier.',
  worker_id STRING COMMENT 'Employee identifier.',
  effective_date DATE COMMENT 'Date the salary took effect.',
  base_salary INT COMMENT 'Annual base salary after the change.',
  change_reason STRING COMMENT 'initial, hire, merit or promotion.',
  is_current BOOLEAN COMMENT 'TRUE for the latest compensation event per employee.',
  business_line STRING COMMENT 'Business line used for row-level security.',
  region STRING COMMENT 'Region used for row-level security.',
  site_id STRING COMMENT 'Site org unit id.',
  site_name STRING COMMENT 'Site or office name.',
  site_city STRING COMMENT 'Site city.',
  site_state STRING COMMENT 'Site state.',
  team_id STRING COMMENT 'Team org unit id.',
  team_name STRING COMMENT 'Team org unit name.',
  job_id STRING COMMENT 'Current job id.',
  job_title STRING COMMENT 'Current job title.',
  job_family STRING COMMENT 'Current job family.',
  job_level INT COMMENT 'Current job level.',
  manager_id STRING COMMENT 'Current manager worker id.',
  pay_band_id STRING COMMENT 'Current pay band id.',
  band_min INT COMMENT 'Current pay band minimum.',
  band_mid INT COMMENT 'Current pay band midpoint.',
  band_max INT COMMENT 'Current pay band maximum.',
  pay_to_midpoint DOUBLE COMMENT 'Base salary divided by band midpoint.',
  hire_date DATE COMMENT 'Original hire date.',
  tenure_months INT COMMENT 'Completed months of tenure as of today.'
)
COMMENT 'One row per compensation event with current pay band and pay position.'
AS SELECT
  c.comp_event_id, c.worker_id, c.effective_date, c.base_salary, c.change_reason,
  ROW_NUMBER() OVER (PARTITION BY c.worker_id ORDER BY c.effective_date DESC, c.comp_event_id DESC) = 1 AS is_current,
  w.business_line, w.region, w.site_id, w.site_name, w.site_city, w.site_state,
  w.team_id, w.team_name, w.job_id, w.job_title, w.job_family, w.job_level, w.manager_id,
  j.pay_band_id, j.band_min, j.band_mid, j.band_max,
  CASE WHEN j.band_mid IS NOT NULL AND j.band_mid > 0 THEN c.base_salary / j.band_mid END AS pay_to_midpoint,
  w.hire_date,
  CAST(floor(months_between(current_date(), w.hire_date)) AS INT) AS tenure_months
FROM silver_compensation c
LEFT JOIN dim_worker w ON c.worker_id = w.worker_id
LEFT JOIN dim_job j ON w.job_id = j.job_id;
