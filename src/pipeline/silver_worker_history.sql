-- Duplicate detection is a QA materialized view because expectations cannot
-- contain subqueries and streaming SQL cannot rank rows. The rank > 1 copies
-- are dropped, which gives an expectation metric for the planted duplicates.

CREATE OR REFRESH MATERIALIZED VIEW silver_worker_event_quality (
  CONSTRAINT no_duplicate_event EXPECT (duplicate_rank = 1) ON VIOLATION DROP ROW
)
COMMENT 'QA view: one row per worker event with a duplicate rank. Violating copies are dropped and counted in the event log.'
AS SELECT
  event_id,
  worker_id,
  event_seq,
  ROW_NUMBER() OVER (PARTITION BY event_id ORDER BY effective_date, event_seq) AS duplicate_rank
FROM bronze_worker_events
WHERE event_id IS NOT NULL;

CREATE OR REFRESH STREAMING TABLE silver_worker_history
COMMENT 'SCD Type 2 worker history. Current rows have __END_AT IS NULL. Sequence is effective_date then event_seq.';

-- An empty manager on a promotion means "unchanged", while an empty manager
-- on manager_change, hire or initial_state means "no manager". AUTO CDC's
-- IGNORE NULL UPDATES can only distinguish these if the second case is
-- non-NULL, so it is encoded as an empty string here and normalised to NULL
-- in silver_worker_history_clean.
CREATE TEMPORARY VIEW silver_worker_events_cdc AS
SELECT * EXCEPT (manager_id),
  CASE WHEN event_type = 'promotion' THEN manager_id
       ELSE COALESCE(manager_id, '') END AS manager_id
FROM STREAM(silver_worker_events_stage);

CREATE FLOW worker_scd2 AS AUTO CDC INTO silver_worker_history
FROM STREAM(silver_worker_events_cdc)
KEYS (worker_id)
IGNORE NULL UPDATES
SEQUENCE BY effective_ts
COLUMNS * EXCEPT (hire_date, raw_business_line, org_business_line, source_file_path)
STORED AS SCD TYPE 2;

CREATE OR REFRESH MATERIALIZED VIEW silver_worker_history_clean
COMMENT 'SCD2 history with the no-manager sentinel converted back to NULL. Use this for point-in-time joins.'
AS SELECT * EXCEPT (manager_id), NULLIF(manager_id, '') AS manager_id
FROM silver_worker_history;
