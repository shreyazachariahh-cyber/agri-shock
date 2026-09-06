import json
import pytest
from agri_shock.ingestion.http import SourceFetchError, fetch_json

class Response:
    def __enter__(self): return self
    def __exit__(self, *_): return False
    def read(self): return json.dumps({"records": []}).encode()

def test_fetch_retries_then_returns_json() -> None:
    calls = []
    def opener(*_args, **_kwargs):
        calls.append(1)
        if len(calls) < 3: raise TimeoutError("temporary")
        return Response()
    assert fetch_json("https://example.test", max_attempts=3, sleep=lambda _: None, opener=opener) == {"records": []}
    assert len(calls) == 3

def test_fetch_raises_after_bounded_retries() -> None:
    with pytest.raises(SourceFetchError, match="after 2 attempts"):
        fetch_json("https://example.test", max_attempts=2, sleep=lambda _: None, opener=lambda *_args, **_kwargs: (_ for _ in ()).throw(TimeoutError()))
