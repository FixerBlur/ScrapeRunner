import httpx
import pytest

from scraperunner.fetcher import http as http_module
from scraperunner.fetcher.http import HttpFetcher


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    monkeypatch.setattr(http_module.time, "sleep", lambda seconds: None)


def client_with(responses):
    calls = []

    def handler(request):
        calls.append(request.url.path)
        outcome = responses[min(len(calls) - 1, len(responses) - 1)]
        if isinstance(outcome, Exception):
            raise outcome
        return httpx.Response(outcome, text="<html><body>ok</body></html>", headers={"content-type": "text/html"})

    return httpx.Client(transport=httpx.MockTransport(handler)), calls


def test_transient_errors_are_retried_then_succeed():
    client, calls = client_with([httpx.ConnectError("boom"), 503, 200])
    result = HttpFetcher(client, retries=2).fetch("https://s.com/x")
    assert result.status == 200
    assert len(calls) == 3


def test_gives_up_after_retries():
    client, calls = client_with([httpx.ConnectError("boom")])
    with pytest.raises(httpx.ConnectError):
        HttpFetcher(client, retries=1).fetch("https://s.com/x")
    assert len(calls) == 2


def test_client_errors_are_not_retried():
    client, calls = client_with([404])
    assert HttpFetcher(client, retries=3).fetch("https://s.com/x").status == 404
    assert len(calls) == 1
