CREATE OR REFRESH MATERIALIZED VIEW fact_engagement (
  response_id STRING COMMENT 'Survey response id.',
  worker_id STRING COMMENT 'Employee identifier.',
  wave_id STRING COMMENT 'Survey wave id.',
  wave_date DATE COMMENT 'Survey wave date.',
  engagement_index DOUBLE COMMENT 'Overall engagement index, 1 to 5.',
  q_manager DOUBLE COMMENT 'Manager question score, 1 to 5.',
  q_workload DOUBLE COMMENT 'Workload question score, 1 to 5.',
  q_growth DOUBLE COMMENT 'Career growth question score, 1 to 5.',
  q_recommend DOUBLE COMMENT 'Recommendation question score, 1 to 5.',
  comment STRING COMMENT 'Optional free-text comment.',
  sentiment STRING COMMENT 'AI sentiment: positive, negative, neutral or mixed.',
  burnout_flag BOOLEAN COMMENT 'TRUE when AI classifies the comment as burnout.',
  business_line STRING COMMENT 'Business line of the respondent.',
  region STRING COMMENT 'Region of the respondent.',
  site_id STRING COMMENT 'Site org unit id.',
  site_name STRING COMMENT 'Site or office name.',
  site_city STRING COMMENT 'Site city.',
  site_state STRING COMMENT 'Site state.',
  team_id STRING COMMENT 'Team org unit id.',
  team_name STRING COMMENT 'Team org unit name.',
  job_id STRING COMMENT 'Job id.',
  job_title STRING COMMENT 'Job title.',
  job_family STRING COMMENT 'Job family.',
  job_level INT COMMENT 'Job level.',
  manager_id STRING COMMENT 'Manager worker id.'
)
COMMENT 'One row per survey response with AI sentiment and burnout signal plus org context.'
AS SELECT
  e.response_id, e.worker_id, e.wave_id, e.wave_date, e.engagement_index,
  e.q_manager, e.q_workload, e.q_growth, e.q_recommend, e.comment,
  a.sentiment, a.burnout_flag, h.business_line, h.region,
  o.site_id, o.site_name, o.city AS site_city, o.state AS site_state,
  h.org_unit_id AS team_id, o.org_unit_name AS team_name,
  h.job_id, j.title AS job_title, j.job_family, j.job_level, h.manager_id
FROM silver_engagement_responses e
LEFT JOIN silver_engagement_ai a ON e.response_id = a.response_id
LEFT JOIN silver_worker_history_clean h
  ON e.worker_id = h.worker_id
 AND h.__START_AT <= CAST(e.wave_date AS TIMESTAMP) + INTERVAL 1 DAY - INTERVAL 1 SECOND
 AND (h.__END_AT > CAST(e.wave_date AS TIMESTAMP) + INTERVAL 1 DAY - INTERVAL 1 SECOND OR h.__END_AT IS NULL)
LEFT JOIN dim_org o ON h.org_unit_id = o.org_unit_id
LEFT JOIN dim_job j ON h.job_id = j.job_id;

CREATE OR REFRESH MATERIALIZED VIEW fact_productivity (
  worker_id STRING COMMENT 'Employee identifier.',
  week_start DATE COMMENT 'First day of the work week.',
  week_end DATE COMMENT 'Last day of the work week.',
  scheduled_hours DOUBLE COMMENT 'Scheduled hours for the week.',
  overtime_hours DOUBLE COMMENT 'Overtime hours for the week.',
  output_units INT COMMENT 'Units of work completed.',
  is_overtime BOOLEAN COMMENT 'TRUE when the week had any overtime.',
  business_line STRING COMMENT 'Business line.',
  region STRING COMMENT 'Region.',
  team_id STRING COMMENT 'Team org unit id.',
  team_name STRING COMMENT 'Team org unit name.',
  site_id STRING COMMENT 'Site org unit id.',
  site_name STRING COMMENT 'Site or office name.',
  site_city STRING COMMENT 'Site city.',
  site_state STRING COMMENT 'Site state.',
  job_id STRING COMMENT 'Job id.',
  job_title STRING COMMENT 'Job title.',
  job_family STRING COMMENT 'Job family.',
  job_level INT COMMENT 'Job level.',
  manager_id STRING COMMENT 'Manager worker id.'
)
COMMENT 'One row per completed worker-week with hours, overtime, output and org context.'
AS SELECT
  p.worker_id, p.week_start, p.week_end, p.scheduled_hours, p.overtime_hours,
  p.output_units, p.overtime_hours > 0 AS is_overtime,
  p.business_line, p.region, p.team_id, o.org_unit_name AS team_name,
  o.site_id, o.site_name, o.city AS site_city, o.state AS site_state,
  h.job_id, j.title AS job_title, j.job_family, j.job_level, h.manager_id
FROM silver_productivity p
LEFT JOIN dim_org o ON p.team_id = o.org_unit_id
LEFT JOIN silver_worker_history_clean h
  ON p.worker_id = h.worker_id
 AND h.__START_AT <= CAST(p.week_end AS TIMESTAMP) + INTERVAL 1 DAY - INTERVAL 1 SECOND
 AND (h.__END_AT > CAST(p.week_end AS TIMESTAMP) + INTERVAL 1 DAY - INTERVAL 1 SECOND OR h.__END_AT IS NULL)
LEFT JOIN dim_job j ON h.job_id = j.job_id;
