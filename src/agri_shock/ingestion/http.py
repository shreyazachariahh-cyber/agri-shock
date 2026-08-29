"""Small injectable HTTP boundary for public-source adapters."""
from __future__ import annotations
import json
from typing import Any
from urllib.request import Request, urlopen

class SourceFetchError(RuntimeError): pass

def fetch_json(url: str, timeout_seconds: float = 20.0) -> Any:
    try:
        with urlopen(Request(url, headers={"Accept": "application/json", "User-Agent": "AgriShock/0.1"}), timeout=timeout_seconds) as response:
            return json.loads(response.read().decode("utf-8"))
    except Exception as error:
        raise SourceFetchError(f"source request failed: {error}") from error
