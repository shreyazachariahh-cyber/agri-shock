"""Event-time geographic shock association; invoked after Silver normalization."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any

@dataclass(frozen=True, slots=True)
class ShockJoinPolicy:
    lookahead_days: int
    def __post_init__(self) -> None:
        if self.lookahead_days <= 0:
            raise ValueError("lookahead_days must be positive")

def join_shocks_to_prices(shocks: Any, prices: Any, policy: ShockJoinPolicy) -> Any:
    """Join canonical district observations within a post-shock event-time window.

    Inputs must already have watermarks and columns `district_id`, `shock_time`
    / `event_time`. This avoids display-name joins and retains the actual delay.
    """
    from pyspark.sql import functions as F
    condition = ((F.col("p.district_id") == F.col("s.district_id")) &
                 (F.col("p.event_time") >= F.col("s.shock_time")) &
                 (F.col("p.event_time") <= F.col("s.shock_time") + F.expr(f"INTERVAL {policy.lookahead_days} DAYS")))
    return shocks.alias("s").join(prices.alias("p"), condition, "inner").select("s.*", F.col("p.event_id").alias("price_event_id"), F.col("p.event_time").alias("price_event_time"), F.col("p.market_id"), F.col("p.commodity_id"), F.col("p.modal_price"), F.datediff(F.col("p.event_time"), F.col("s.shock_time")).alias("days_after_shock"))
