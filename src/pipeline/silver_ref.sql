-- Silver reference data: typed, empty strings converted to NULL.

CREATE OR REFRESH STREAMING TABLE silver_org_units
COMMENT 'Typed org hierarchy with empty labels converted to NULL.'
AS SELECT
  org_unit_id,
  name AS org_unit_name,
  unit_type,
  NULLIF(parent_org_unit_id, '') AS parent_org_unit_id,
  NULLIF(business_line, '') AS business_line,
  NULLIF(region, '') AS region,
  NULLIF(site_type, '') AS site_type,
  NULLIF(city, '') AS city,
  NULLIF(state, '') AS state
FROM STREAM(bronze_org_units)
WHERE org_unit_id IS NOT NULL;

CREATE OR REFRESH STREAMING TABLE silver_pay_bands
COMMENT 'Typed pay bands.'
AS SELECT
  pay_band_id,
  CAST(NULLIF(band_min, '') AS INT) AS band_min,
  CAST(NULLIF(band_mid, '') AS INT) AS band_mid,
  CAST(NULLIF(band_max, '') AS INT) AS band_max,
  CAST(NULLIF(effective_date, '') AS DATE) AS effective_date
FROM STREAM(bronze_pay_bands)
WHERE pay_band_id IS NOT NULL;

CREATE OR REFRESH STREAMING TABLE silver_jobs
COMMENT 'Typed job catalogue including free-text job descriptions.'
AS SELECT
  job_id,
  title,
  job_family,
  CAST(NULLIF(job_level, '') AS INT) AS job_level,
  NULLIF(business_line, '') AS business_line,
  NULLIF(region, '') AS region,
  CAST(NULLIF(is_people_manager, '') AS BOOLEAN) AS is_people_manager,
  CAST(NULLIF(is_licensed_role, '') AS BOOLEAN) AS is_licensed_role,
  NULLIF(required_license_type, '') AS required_license_type,
  NULLIF(pay_band_id, '') AS pay_band_id,
  CAST(NULLIF(created_date, '') AS DATE) AS created_date,
  NULLIF(job_description, '') AS job_description
FROM STREAM(bronze_jobs)
WHERE job_id IS NOT NULL;

CREATE OR REFRESH STREAMING TABLE silver_site_events
COMMENT 'Typed site events. schedule_change rows identify contact-centre shift changes.'
AS SELECT
  site_event_id,
  org_unit_id,
  CAST(NULLIF(event_date, '') AS DATE) AS event_date,
  event_type,
  NULLIF(description, '') AS description,
  NULLIF(business_line, '') AS business_line,
  NULLIF(region, '') AS region
FROM STREAM(bronze_site_events)
WHERE site_event_id IS NOT NULL;
