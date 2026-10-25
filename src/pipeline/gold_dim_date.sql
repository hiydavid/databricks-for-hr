CREATE OR REFRESH MATERIALIZED VIEW dim_date (
  date_key DATE COMMENT 'Calendar date.',
  year INT COMMENT 'Calendar year.',
  quarter INT COMMENT 'Calendar quarter, 1 to 4.',
  month INT COMMENT 'Calendar month number.',
  month_name STRING COMMENT 'Calendar month name.',
  month_start DATE COMMENT 'First day of the month.',
  month_end DATE COMMENT 'Last day of the month.',
  week_start DATE COMMENT 'Monday of the ISO week.',
  week_end DATE COMMENT 'Sunday of the ISO week.',
  day_of_week INT COMMENT 'Day number, 1 Sunday to 7 Saturday.',
  day_name STRING COMMENT 'Weekday name.',
  is_weekend BOOLEAN COMMENT 'TRUE for Saturday and Sunday.',
  is_month_end BOOLEAN COMMENT 'TRUE when the date is the last day of its month.'
)
COMMENT 'Calendar dimension covering 2024-01-01 through today, with month-end and week flags.'
AS WITH dates AS (
  SELECT explode(sequence(DATE'2024-01-01', current_date(), INTERVAL 1 DAY)) AS calendar_date
)
SELECT
  calendar_date AS date_key,
  year(calendar_date) AS year,
  quarter(calendar_date) AS quarter,
  month(calendar_date) AS month,
  date_format(calendar_date, 'MMMM') AS month_name,
  trunc(calendar_date, 'MM') AS month_start,
  last_day(calendar_date) AS month_end,
  date_sub(calendar_date, weekday(calendar_date)) AS week_start,
  date_add(date_sub(calendar_date, weekday(calendar_date)), 6) AS week_end,
  dayofweek(calendar_date) AS day_of_week,
  date_format(calendar_date, 'EEEE') AS day_name,
  dayofweek(calendar_date) IN (1, 7) AS is_weekend,
  calendar_date = last_day(calendar_date) AS is_month_end
FROM dates;
