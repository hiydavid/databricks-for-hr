-- Incremental AI enrichment. Each table streams from a silver text table and
-- filters blank text before calling the model, so only new non-empty rows are
-- sent on each pipeline update.

CREATE OR REFRESH STREAMING TABLE silver_exit_interviews_ai
COMMENT 'AI exit reason for voluntary leavers. One ai_classify call per non-empty comment.'
AS SELECT
  exit_interview_id, worker_id, termination_date, interview_date, comment,
  result:response[0]::STRING AS exit_reason,
  result:error_message::STRING AS ai_error
FROM (
  SELECT *,
    ai_classify(
      comment,
      '["schedule_workload","compensation","career_growth","manager_relationship","relocation_personal","health_burnout","other"]',
      map('version', '2.0')
    ) AS result
  FROM STREAM(silver_exit_interviews)
  WHERE comment IS NOT NULL AND trim(comment) <> ''
);

CREATE OR REFRESH STREAMING TABLE silver_engagement_ai
COMMENT 'AI sentiment and burnout flag for survey comments. Two calls per non-empty comment.'
AS SELECT
  response_id, worker_id, wave_date, comment,
  sentiment,
  burnout_result:response[0]::STRING AS burnout_label,
  burnout_result:response[0]::STRING = 'burnout' AS burnout_flag,
  burnout_result:error_message::STRING AS ai_error
FROM (
  SELECT *,
    ai_analyze_sentiment(comment) AS sentiment,
    ai_classify(
      comment,
      '{"burnout":"Text describes exhaustion, unsustainable workload, staff shortages or no breaks","no_burnout":"Text does not describe burnout"}',
      map('version', '2.0')
    ) AS burnout_result
  FROM STREAM(silver_engagement_responses)
  WHERE comment IS NOT NULL AND trim(comment) <> ''
);

CREATE OR REFRESH STREAMING TABLE silver_performance_ai
COMMENT 'AI skills extracted from manager review comments. One ai_extract call per non-empty comment.'
AS SELECT
  review_id, worker_id, review_date, manager_comment,
  result:response:skills::ARRAY<STRING> AS skills,
  result:error_message::STRING AS ai_error
FROM (
  SELECT *,
    ai_extract(
      manager_comment,
      '{"skills":{"type":"array","items":{"type":"string"}}}',
      map('version', '2.1')
    ) AS result
  FROM STREAM(silver_performance_reviews)
  WHERE manager_comment IS NOT NULL AND trim(manager_comment) <> ''
);

CREATE OR REFRESH STREAMING TABLE silver_jobs_ai
COMMENT 'AI GenAI exposure tier and skills extracted from job descriptions. Two calls per non-empty description.'
AS SELECT
  job_id, title, job_family, job_level, business_line, region, is_licensed_role, pay_band_id, job_description,
  tier_result:response[0]::STRING AS genai_exposure_tier,
  skills_result:response:skills::ARRAY<STRING> AS skills,
  tier_result:error_message::STRING AS tier_error,
  skills_result:error_message::STRING AS skills_error
FROM (
  SELECT *,
    ai_classify(
      job_description,
      '{"high":"Most tasks are routine document, data-entry or rules-based processing that generative AI can automate","medium":"A mix of routine processing and judgement or relationship work, with some tasks automatable","low":"Mostly judgement, advisory, relationship or specialist work with little routine processing"}',
      map('version', '2.0', 'instructions', 'Rate how exposed this job is to generative AI automation, not how senior it is.')
    ) AS tier_result,
    ai_extract(
      job_description,
      '{"skills":{"type":"array","items":{"type":"string"}}}',
      map('version', '2.1')
    ) AS skills_result
  FROM STREAM(silver_jobs)
  WHERE job_description IS NOT NULL AND trim(job_description) <> ''
);
