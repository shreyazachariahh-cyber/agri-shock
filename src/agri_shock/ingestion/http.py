"""Bounded, injectable HTTP boundary for public-source adapters."""
from __future__ import annotations
import json
import time
from collections.abc import Callable
from typing import Any
from urllib.request import Request, urlopen

class SourceFetchError(RuntimeError):
    pass

def fetch_json(url: str, timeout_seconds: float = 20.0, max_attempts: int = 3, sleep: Callable[[float], None] = time.sleep, opener: Callable[..., Any] = urlopen) -> Any:
    if max_attempts < 1:
        raise ValueError("max_attempts must be positive")
    request = Request(url, headers={"Accept": "application/json", "User-Agent": "AgriShock/0.1"})
    for attempt in range(1, max_attempts + 1):
        try:
            with opener(request, timeout=timeout_seconds) as response:
                return json.loads(response.read().decode("utf-8"))
        except Exception as error:
            if attempt == max_attempts:
                raise SourceFetchError(f"source request failed after {max_attempts} attempts: {error}") from error
            sleep(2 ** (attempt - 1))
    raise AssertionError("unreachable")
