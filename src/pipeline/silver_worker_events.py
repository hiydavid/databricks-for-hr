"""Typed, deduplicated worker event stream used by AUTO CDC.

Streaming SQL has no row-level dedupe without a window and watermark, so this
one table is Python. Duplicate event_id rows are identical; keeping the first
copy is sufficient. Termination events dated before the worker's hire date are
dropped by the expectation before SCD2 sees them.
"""

from pyspark import pipelines as dp
from pyspark.sql import functions as F

VALID_LINES = (
    "Consumer Banking",
    "Operations",
    "Wealth Management",
    "Technology",
    "Commercial Banking",
    "Corporate Functions",
)


@dp.table(
    name="silver_worker_events_stage",
    comment="Typed, deduplicated worker events with business line recovered from the org unit.",
)
@dp.expect_or_drop(
    "hire_before_termination",
    "(event_type <> 'termination' OR hire_date IS NULL OR effective_date >= hire_date)",
)
def silver_worker_events_stage():
    hires = (
        spark.read.table("bronze_workers")
        .select("worker_id", F.to_date("hire_date").alias("hire_date"))
        .groupBy("worker_id")
        .agg(F.min("hire_date").alias("hire_date"))
    )
    orgs = spark.read.table("bronze_org_units").select(
        "org_unit_id", F.col("business_line").alias("org_business_line")
    )
    events = (
        spark.readStream.table("bronze_worker_events")
        .select(
            "event_id",
            F.col("event_seq").cast("int").alias("event_seq"),
            "worker_id",
            "event_type",
            F.to_date("effective_date").alias("effective_date"),
            "job_id",
            "org_unit_id",
            F.when(F.col("manager_id") == "", None)
            .otherwise(F.col("manager_id"))
            .alias("manager_id"),
            F.col("business_line").alias("raw_business_line"),
            "region",
            "work_mode",
            F.when(F.col("termination_type") == "", None)
            .otherwise(F.col("termination_type"))
            .alias("termination_type"),
            F.to_date("last_promotion_date").alias("last_promotion_date"),
            "source_file_path",
        )
        .join(hires, "worker_id", "left")
        .join(orgs, "org_unit_id", "left")
        .withColumn(
            "business_line",
            F.when(F.col("raw_business_line").isin(*VALID_LINES), F.col("raw_business_line"))
            .otherwise(F.col("org_business_line")),
        )
        .withColumn(
            "effective_ts",
            F.expr(
                "cast(effective_date as timestamp) + make_interval(0, 0, 0, 0, 0, 0, event_seq)"
            ),
        )
        .dropDuplicates(["event_id"])
    )
    return events
