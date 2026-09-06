"""Typed Bronze, Silver, and Gold contracts independent of Spark runtime."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from typing import Any, Mapping

from agri_shock.processing.confidence import DataConfidence
from agri_shock.processing.evidence import ShockEvidence
from agri_shock.processing.scoring import MarketShockSignal


GOLD_SIGNAL_CONTRACT_VERSION = "1.0"


def _utc(value: datetime, field_name: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")
    return value.astimezone(timezone.utc)


def deterministic_signal_id(
    shock_id: str,
    price_event_id: str,
    contract_version: str = GOLD_SIGNAL_CONTRACT_VERSION,
) -> str:
    """Stable identity for one shock/price analytical observation.

    Corrections must use a new source event ID or explicit revision before they
    intentionally replace a result; this prevents silent history mutation.
    """
    if not shock_id or not price_event_id or not contract_version:
        raise ValueError("shock_id, price_event_id, and contract_version are required")
    material = f"{shock_id}|{price_event_id}|{contract_version}"
    return sha256(material.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class BronzeEvent:
    """Append-only Kafka capture; raw data is deliberately not normalized here."""

    raw_payload: str
    kafka_topic: str
    kafka_partition: int
    kafka_offset: int
    kafka_timestamp: datetime
    ingestion_time: datetime
    source_event_time: datetime | None
    source: str | None
    source_event_id: str | None
    schema_version: str | None

    def __post_init__(self) -> None:
        if not self.raw_payload or not self.kafka_topic or self.kafka_partition < 0:
            raise ValueError("raw payload, topic, and non-negative partition are required")
        if self.kafka_offset < 0:
            raise ValueError("kafka_offset must be non-negative")
        _utc(self.kafka_timestamp, "kafka_timestamp")
        _utc(self.ingestion_time, "ingestion_time")
        if self.source_event_time is not None:
            _utc(self.source_event_time, "source_event_time")


@dataclass(frozen=True, slots=True)
class SilverMandiObservation:
    """Validated, canonical price observation with source provenance retained."""

    event_id: str
    event_time: datetime
    ingestion_time: datetime
    source: str
    state_id: str
    district_id: str
    market_id: str
    commodity_id: str
    modal_price: float
    kafka_topic: str
    kafka_partition: int
    kafka_offset: int
    raw_event_id: str
    geography_mapping_version: str

    def __post_init__(self) -> None:
        required = (
            self.event_id,
            self.source,
            self.state_id,
            self.district_id,
            self.market_id,
            self.commodity_id,
            self.kafka_topic,
            self.raw_event_id,
            self.geography_mapping_version,
        )
        if not all(value.strip() for value in required):
            raise ValueError("Silver mandi observation has missing canonical/provenance fields")
        if self.modal_price < 0 or self.kafka_partition < 0 or self.kafka_offset < 0:
            raise ValueError("Silver mandi observation has invalid numeric values")
        _utc(self.event_time, "event_time")
        _utc(self.ingestion_time, "ingestion_time")


@dataclass(frozen=True, slots=True)
class GoldSignalContext:
    shock_id: str
    price_event_id: str
    state_id: str
    district_id: str
    market_id: str
    commodity_id: str
    shock_type: str
    shock_time: datetime
    price_event_time: datetime
    provenance_type: str
    source_references: tuple[str, ...]
    processing_time: datetime
    display_state: str | None = None
    display_district: str | None = None
    display_market: str | None = None
    display_commodity: str | None = None
    location: Mapping[str, float] | None = None

    def __post_init__(self) -> None:
        required = (
            self.shock_id,
            self.price_event_id,
            self.state_id,
            self.district_id,
            self.market_id,
            self.commodity_id,
            self.shock_type,
            self.provenance_type,
        )
        if not all(value.strip() for value in required):
            raise ValueError("Gold context has missing canonical/provenance fields")
        _utc(self.shock_time, "shock_time")
        _utc(self.price_event_time, "price_event_time")
        _utc(self.processing_time, "processing_time")


@dataclass(frozen=True, slots=True)
class GoldMarketShockSignal:
    """Gold contract consumed directly by the Elasticsearch serving boundary."""

    signal_id: str
    context: GoldSignalContext
    evidence: ShockEvidence
    signal: MarketShockSignal
    model_contract_version: str = GOLD_SIGNAL_CONTRACT_VERSION

    def to_document(self) -> dict[str, Any]:
        confidence: DataConfidence = self.signal.data_confidence
        return {
            "signal_id": self.signal_id,
            "shock_id": self.context.shock_id,
            "price_event_id": self.context.price_event_id,
            "state_id": self.context.state_id,
            "district_id": self.context.district_id,
            "market_id": self.context.market_id,
            "commodity_id": self.context.commodity_id,
            "fixture_kind": self.context.provenance_type,
            "state": self.context.display_state or self.context.state_id,
            "district": self.context.display_district or self.context.district_id,
            "market": self.context.display_market or self.context.market_id,
            "commodity": self.context.display_commodity or self.context.commodity_id,
            "shock_type": self.context.shock_type,
            "shock_time": _utc(self.context.shock_time, "shock_time").isoformat(),
            "price_event_time": _utc(self.context.price_event_time, "price_event_time").isoformat(),
            "event_time": _utc(self.context.price_event_time, "price_event_time").isoformat(),
            "ingestion_time": _utc(self.context.processing_time, "processing_time").isoformat(),
            "processing_time": _utc(self.context.processing_time, "processing_time").isoformat(),
            "model_contract_version": self.model_contract_version,
            "location": dict(self.context.location) if self.context.location else None,
            "observed_price": self.evidence.observed_price,
            "baseline_price": self.evidence.baseline_price,
            "deviation_pct": self.evidence.deviation_pct,
            "robust_z_score": self.evidence.robust_z_score,
            "days_after_shock": self.evidence.days_after_shock,
            "shock_severity": self.evidence.shock_severity,
            "control_difference_pct": self.evidence.control_difference_pct,
            "component_scores": dict(self.signal.component_scores),
            "signal_strength": self.signal.signal_strength,
            "signal_level": self.signal.signal_level,
            "data_confidence": {
                "value": confidence.value,
                "is_sufficient": confidence.is_sufficient,
                "reasons": list(confidence.reasons),
            },
            "confidence_reasons": list(confidence.reasons),
            "source_references": list(self.context.source_references),
        }


def build_gold_signal(
    context: GoldSignalContext,
    evidence: ShockEvidence,
    signal: MarketShockSignal,
) -> GoldMarketShockSignal:
    if evidence.district_id != context.district_id:
        raise ValueError("evidence district_id must match Gold context district_id")
    return GoldMarketShockSignal(
        signal_id=deterministic_signal_id(context.shock_id, context.price_event_id),
        context=context,
        evidence=evidence,
        signal=signal,
    )


def late_event_disposition(event_time: datetime, watermark_cutoff: datetime) -> str:
    """Declare whether stateful streaming may use an event or reconciliation must."""
    return "reconcile" if _utc(event_time, "event_time") < _utc(watermark_cutoff, "watermark_cutoff") else "process"
