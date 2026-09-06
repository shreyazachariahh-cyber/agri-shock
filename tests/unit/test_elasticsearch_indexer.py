from pathlib import Path

import pytest

from agri_shock.elasticsearch.indexer import (
    INDEX_NAME,
    ensure_index,
    index_documents,
    read_ndjson,
    validate_document,
)


class FakeIndices:
    def __init__(self) -> None:
        self.created: dict[str, object] | None = None

    def exists(self, *, index: str) -> bool:
        return self.created is not None

    def create(self, **kwargs: object) -> None:
        self.created = kwargs


class FakeClient:
    def __init__(self) -> None:
        self.indices = FakeIndices()
        self.operations: list[dict[str, object]] | None = None

    def bulk(self, *, operations: list[dict[str, object]], refresh: str) -> dict[str, bool]:
        self.operations = operations
        assert refresh == "wait_for"
        return {"errors": False}


def document() -> dict[str, object]:
    return {
        "signal_id": "signal-001",
        "fixture_kind": "synthetic_demo",
        "state": "Assam",
        "district": "Dhemaji",
        "commodity": "rice",
        "shock_type": "flood",
        "shock_time": "2024-06-30T00:00:00Z",
        "price_event_time": "2024-07-02T00:00:00Z",
        "event_time": "2024-07-02T00:00:00Z",
        "ingestion_time": "2026-09-06T00:00:00Z",
        "signal_strength": 75.0,
        "signal_level": "HIGH",
        "data_confidence": {"value": 0.8, "is_sufficient": True, "reasons": []},
    }


def test_indexing_is_idempotent_by_signal_id() -> None:
    client = FakeClient()
    ensure_index(client)
    indexed = index_documents(client, [document()])
    assert indexed == 1
    assert client.indices.created is not None
    assert client.indices.created["index"] == INDEX_NAME
    assert client.operations is not None
    assert client.operations[0]["index"]["_id"] == "signal-001"


def test_insufficient_evidence_cannot_have_numeric_strength() -> None:
    invalid = document() | {"signal_level": "INSUFFICIENT_EVIDENCE"}
    with pytest.raises(ValueError, match="must not carry"):
        validate_document(invalid)


def test_demo_fixture_is_validated_from_ndjson() -> None:
    fixture = Path("data/sample/market_shock_signals.ndjson")
    documents = read_ndjson(fixture)
    assert len(documents) == 10
    assert {item["state"] for item in documents} == {
        "Assam",
        "Bihar",
        "Kerala",
        "Maharashtra",
        "Himachal Pradesh",
    }
