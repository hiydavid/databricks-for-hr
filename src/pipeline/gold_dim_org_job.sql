CREATE OR REFRESH MATERIALIZED VIEW dim_org (
  org_unit_id STRING COMMENT 'Org unit identifier at any level.',
  org_unit_name STRING COMMENT 'Org unit name.',
  unit_type STRING COMMENT 'company, business_line, site or team.',
  parent_org_unit_id STRING COMMENT 'Parent org unit id, NULL at the company root.',
  business_line STRING COMMENT 'Business line of the org unit.',
  region STRING COMMENT 'Region of the org unit.',
  site_id STRING COMMENT 'Resolved site org unit id.',
  site_name STRING COMMENT 'Resolved site or office name.',
  city STRING COMMENT 'Resolved site city.',
  state STRING COMMENT 'Resolved site state.',
  site_type STRING COMMENT 'Branch, contact centre, office or operations centre.',
  schedule_change_date DATE COMMENT 'Most recent schedule-change event date at the site.',
  has_schedule_change BOOLEAN COMMENT 'TRUE when the site has a recorded schedule change.'
)
COMMENT 'Org hierarchy flattened with the resolved site, city and schedule-change date for reporting.'
AS WITH units AS (
  SELECT *,
    CASE WHEN unit_type = 'team' THEN parent_org_unit_id ELSE org_unit_id END AS resolved_site_id
  FROM silver_org_units
),
changes AS (
  SELECT org_unit_id, MAX(event_date) AS schedule_change_date
  FROM silver_site_events
  WHERE event_type = 'schedule_change'
  GROUP BY org_unit_id
)
SELECT
  u.org_unit_id, u.org_unit_name, u.unit_type, u.parent_org_unit_id, u.business_line, u.region,
  u.resolved_site_id AS site_id, s.org_unit_name AS site_name, s.city, s.state, s.site_type,
  c.schedule_change_date, c.schedule_change_date IS NOT NULL AS has_schedule_change
FROM units u
LEFT JOIN silver_org_units s ON u.resolved_site_id = s.org_unit_id
LEFT JOIN changes c ON u.resolved_site_id = c.org_unit_id;

CREATE OR REFRESH MATERIALIZED VIEW dim_job (
  job_id STRING COMMENT 'Job identifier.',
  title STRING COMMENT 'Job title.',
  job_family STRING COMMENT 'Job family.',
  job_level INT COMMENT 'Job level, 1 to 5.',
  business_line STRING COMMENT 'Business line that owns the job.',
  is_people_manager BOOLEAN COMMENT 'TRUE when the job manages people.',
  is_licensed_role BOOLEAN COMMENT 'TRUE when the job is a licensed role.',
  required_license_type STRING COMMENT 'License type required by the role.',
  pay_band_id STRING COMMENT 'Pay band identifier.',
  band_min INT COMMENT 'Pay band minimum annual salary.',
  band_mid INT COMMENT 'Pay band midpoint annual salary.',
  band_max INT COMMENT 'Pay band maximum annual salary.',
  job_description STRING COMMENT 'Free-text job description.',
  genai_exposure_tier STRING COMMENT 'AI-classified GenAI exposure: high, medium or low.',
  skills ARRAY<STRING> COMMENT 'Skills extracted from the job description.',
  created_date DATE COMMENT 'Date the job was first created.'
)
COMMENT 'One row per job with pay band, GenAI exposure tier and extracted skills.'
AS SELECT
  j.job_id, j.title, j.job_family, j.job_level, j.business_line, j.is_people_manager,
  j.is_licensed_role, j.required_license_type, j.pay_band_id,
  p.band_min, p.band_mid, p.band_max, j.job_description,
  a.genai_exposure_tier, a.skills, j.created_date
FROM silver_jobs j
LEFT JOIN silver_pay_bands p ON j.pay_band_id = p.pay_band_id
LEFT JOIN silver_jobs_ai a ON j.job_id = a.job_id;
