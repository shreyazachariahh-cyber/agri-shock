"""Delta-only Gold persistence helpers, imported only in a Spark/Delta runtime."""
from __future__ import annotations

from typing import Any


def merge_gold_signals(batch_df: Any, path: str) -> None:
    """Idempotently insert Gold signals by deterministic `signal_id`.

    A matching ID is intentionally left unchanged: a replay is not a source
    correction. Corrections require a distinct source/revision ID and hence a
    distinct signal lineage. This function is designed for a `foreachBatch`
    materialization once the baseline computation is available as a Spark
    transformation.
    """
    try:
        from delta.tables import DeltaTable
    except ImportError as error:
        raise RuntimeError("Delta Lake runtime is required for Gold MERGE") from error
    if DeltaTable.isDeltaTable(batch_df.sparkSession, path):
        target = DeltaTable.forPath(batch_df.sparkSession, path)
        (target.alias("target").merge(batch_df.alias("source"), "target.signal_id = source.signal_id")
            .whenNotMatchedInsertAll().execute())
    else:
        batch_df.write.format("delta").mode("errorifexists").save(path)
