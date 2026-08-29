"""Framework-free validation primitives; adapters add source-specific rules."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Mapping


@dataclass(frozen=True, slots=True)
class ValidationResult:
    valid: bool
    reason: str | None = None


def validate_mandi_price(payload: Mapping[str, Any]) -> ValidationResult:
    required_text = ("district", "market", "commodity")
    for field in required_text:
        if not str(payload.get(field, "")).strip():
            return ValidationResult(False, f"missing_{field}")

    prices: dict[str, Decimal] = {}
    for field in ("min_price", "modal_price", "max_price"):
        value = payload.get(field)
        if value is None:
            continue
        try:
            parsed = Decimal(str(value))
        except Exception:
            return ValidationResult(False, f"invalid_{field}")
        if parsed < 0:
            return ValidationResult(False, f"negative_{field}")
        prices[field] = parsed

    if {"min_price", "modal_price", "max_price"}.issubset(prices):
        if not prices["min_price"] <= prices["modal_price"] <= prices["max_price"]:
            return ValidationResult(False, "price_order_invalid")
    return ValidationResult(True)
