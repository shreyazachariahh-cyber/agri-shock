from agri_shock.common.validation import validate_mandi_price


def test_valid_mandi_price() -> None:
    result = validate_mandi_price({"district": "Nashik", "market": "Lasalgaon", "commodity": "Onion", "min_price": 100, "modal_price": 150, "max_price": 200})
    assert result.valid


def test_negative_price_is_rejected() -> None:
    result = validate_mandi_price({"district": "Nashik", "market": "Lasalgaon", "commodity": "Onion", "modal_price": -1})
    assert not result.valid and result.reason == "negative_modal_price"


def test_invalid_price_order_is_rejected() -> None:
    result = validate_mandi_price({"district": "Nashik", "market": "Lasalgaon", "commodity": "Onion", "min_price": 200, "modal_price": 150, "max_price": 250})
    assert not result.valid and result.reason == "price_order_invalid"
