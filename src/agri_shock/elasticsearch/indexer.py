"""Index validated MarketShockSignal documents into Elasticsearch.

The module has no import-time Elasticsearch dependency so contract tests and
fixture validation can run without a local cluster.  The optional client is
required only by the command-line delivery path.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
import time
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any, Callable


INDEX_NAME = "agrishock-market-shock-signals-v1"
REQUIRED_FIELDS = frozenset(
    {
        "signal_id",
        "fixture_kind",
        "state",
        "district",
        "commodity",
        "shock_type",
        "shock_time",
        "price_event_time",
        "event_time",
        "ingestion_time",
        "signal_level",
        "data_confidence",
    }
)
VALID_FIXTURE_KINDS = frozenset(
    {"real_source", "replayed_historical", "synthetic_demo"}
)


class ElasticsearchDeliveryError(RuntimeError):
    """An Elasticsearch delivery failure that callers must surface."""


@dataclass(frozen=True, slots=True)
class ElasticsearchRetryPolicy:
    max_attempts: int = 3
    initial_backoff_seconds: float = 0.25

    def __post_init__(self) -> None:
        if self.max_attempts < 1 or self.initial_backoff_seconds < 0:
            raise ValueError("Elasticsearch retry policy values are invalid")

INDEX_TEMPLATE: dict[str, Any] = {
    "index_patterns": ["agrishock-market-shock-signals-*"],
    "template": {
        "settings": {"number_of_shards": 1, "number_of_replicas": 0},
        "mappings": {
            "dynamic": "strict",
            "properties": {
                "signal_id": {"type": "keyword"},
                "shock_id": {"type": "keyword"},
                "price_event_id": {"type": "keyword"},
                "state_id": {"type": "keyword"},
                "district_id": {"type": "keyword"},
                "market_id": {"type": "keyword"},
                "commodity_id": {"type": "keyword"},
                "scenario_id": {"type": "keyword"},
                "fixture_kind": {"type": "keyword"},
                "state": {"type": "keyword"},
                "district": {"type": "keyword"},
                "market": {"type": "keyword"},
                "commodity": {"type": "keyword"},
                "shock_type": {"type": "keyword"},
                "shock_time": {"type": "date"},
                "price_event_time": {"type": "date"},
                "event_time": {"type": "date"},
                "ingestion_time": {"type": "date"},
                "processing_time": {"type": "date"},
                "model_contract_version": {"type": "keyword"},
                "location": {"type": "geo_point"},
                "observed_price": {"type": "double"},
                "baseline_price": {"type": "double"},
                "deviation_pct": {"type": "double"},
                "robust_z_score": {"type": "double"},
                "days_after_shock": {"type": "integer"},
                "shock_severity": {"type": "double"},
                "control_difference_pct": {"type": "double"},
                "signal_strength": {"type": "double"},
                "signal_level": {"type": "keyword"},
                "component_scores": {"type": "flattened"},
                "data_confidence": {
                    "properties": {
                        "value": {"type": "double"},
                        "is_sufficient": {"type": "boolean"},
                        "reasons": {"type": "keyword"},
                    }
                },
                "confidence_reasons": {"type": "keyword"},
                "source_references": {"type": "keyword"},
                "scenario_note": {"type": "text"},
            },
        },
    },
}


def validate_document(document: Mapping[str, Any]) -> dict[str, Any]:
    """Validate the stable dashboard contract before it reaches Elasticsearch."""
    missing = REQUIRED_FIELDS - document.keys()
    if missing:
        raise ValueError(f"signal document missing required fields: {sorted(missing)}")
    normalized = dict(document)
    if normalized["fixture_kind"] not in VALID_FIXTURE_KINDS:
        raise ValueError(
            "fixture_kind must be real_source, replayed_historical, or synthetic_demo"
        )
    if normalized["signal_level"] not in {
        "LOW",
        "MEDIUM",
        "HIGH",
        "INSUFFICIENT_EVIDENCE",
    }:
        raise ValueError("unsupported signal_level")
    if not isinstance(normalized["data_confidence"], Mapping):
        raise ValueError("data_confidence must be an object")
    if normalized["signal_level"] == "INSUFFICIENT_EVIDENCE":
        if normalized.get("signal_strength") is not None:
            raise ValueError("insufficient evidence must not carry signal_strength")
    elif not 0 <= float(normalized.get("signal_strength", -1)) <= 100:
        raise ValueError("signal_strength must be in [0, 100] when evidence is sufficient")
    return normalized


def read_ndjson(path: Path) -> list[dict[str, Any]]:
    documents: list[dict[str, Any]] = []
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not raw_line.strip():
            continue
        try:
            document = json.loads(raw_line)
        except json.JSONDecodeError as error:
            raise ValueError(f"invalid JSON in {path} line {line_number}") from error
        documents.append(validate_document(document))
    if not documents:
        raise ValueError(f"no documents found in {path}")
    return documents


def deduplicate_documents(documents: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Collapse identical replay records; reject contradictory same-ID records."""
    unique: dict[str, dict[str, Any]] = {}
    for document in documents:
        validated = validate_document(document)
        existing = unique.get(validated["signal_id"])
        if existing is not None and existing != validated:
            raise ValueError("conflicting documents share one signal_id")
        unique[validated["signal_id"]] = validated
    return list(unique.values())


def ensure_index(client: Any, index_name: str = INDEX_NAME) -> None:
    """Create the versioned index once, using the repository mapping."""
    if not client.indices.exists(index=index_name):
        template = INDEX_TEMPLATE["template"]
        client.indices.create(
            index=index_name,
            settings=template["settings"],
            mappings=template["mappings"],
        )


def _response_is_retriable(response: Mapping[str, Any]) -> bool:
    statuses = [
        item["index"].get("status")
        for item in response.get("items", [])
        if isinstance(item, Mapping) and isinstance(item.get("index"), Mapping)
    ]
    return bool(statuses) and all(status == 429 or isinstance(status, int) and status >= 500 for status in statuses)


def _exception_is_retriable(error: Exception) -> bool:
    status = getattr(error, "status_code", None)
    return isinstance(error, (TimeoutError, ConnectionError, OSError)) or status == 429 or isinstance(status, int) and status >= 500


def index_documents(
    client: Any,
    documents: Iterable[Mapping[str, Any]],
    index_name: str = INDEX_NAME,
    retry_policy: ElasticsearchRetryPolicy = ElasticsearchRetryPolicy(),
    sleep: Callable[[float], None] = time.sleep,
) -> int:
    """Index by stable signal ID; retry only transient delivery failures."""
    operations: list[dict[str, Any]] = []
    for validated in deduplicate_documents(documents):
        operations.append({"index": {"_index": index_name, "_id": validated["signal_id"]}})
        operations.append(validated)
    if not operations:
        return 0
    for attempt in range(1, retry_policy.max_attempts + 1):
        try:
            response = client.bulk(operations=operations, refresh="wait_for")
        except Exception as error:
            if not _exception_is_retriable(error) or attempt == retry_policy.max_attempts:
                raise ElasticsearchDeliveryError("Elasticsearch bulk request failed") from error
        else:
            if not response.get("errors"):
                return len(operations) // 2
            if not _response_is_retriable(response) or attempt == retry_policy.max_attempts:
                raise ElasticsearchDeliveryError("Elasticsearch bulk request reported permanent item failures")
        sleep(retry_policy.initial_backoff_seconds * 2 ** (attempt - 1))
    raise AssertionError("Elasticsearch retry loop exited unexpectedly")


def main() -> None:
    parser = argparse.ArgumentParser(description="Index AgriShock signal NDJSON")
    parser.add_argument("ndjson_path", type=Path)
    parser.add_argument("--url", default="http://localhost:9200")
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="validate the Gold-to-Elasticsearch document contract without a cluster",
    )
    args = parser.parse_args()
    documents = read_ndjson(args.ndjson_path)
    if args.validate_only:
        print(f"Validated {len(documents)} signal documents for {INDEX_NAME}")
        return
    try:
        from elasticsearch import Elasticsearch
    except ImportError as error:
        raise RuntimeError("Install agri-shock[streaming] to use Elasticsearch indexing") from error
    client = Elasticsearch(args.url)
    ensure_index(client)
    print(f"Indexed {index_documents(client, documents)} signal documents into {INDEX_NAME}")


if __name__ == "__main__":
    main()
