import httpx

from scraperunner.utils.robots import RobotsCache

ROBOTS = "User-agent: *\nDisallow: /private/\n"


def cache_for(status=200, body=ROBOTS):
    calls = []

    def handler(request):
        calls.append(str(request.url))
        return httpx.Response(status, text=body)

    return RobotsCache(httpx.Client(transport=httpx.MockTransport(handler)), "TestBot"), calls


def test_disallowed_paths_are_blocked_and_robots_fetched_once_per_origin():
    cache, calls = cache_for()
    assert cache.can_fetch("https://s.com/shop")
    assert not cache.can_fetch("https://s.com/private/x")
    assert not cache.can_fetch("https://other.com/private/x")   # same rules served for that host
    assert cache.can_fetch("https://s.com/private/y") is False   # cached: no refetch below
    assert calls == ["https://s.com/robots.txt", "https://other.com/robots.txt"]


def test_missing_robots_allows_everything():
    cache, _ = cache_for(status=404, body="")
    assert cache.can_fetch("https://s.com/private/x")


def test_network_error_allows_everything():
    def handler(request):
        raise httpx.ConnectError("down")

    cache = RobotsCache(httpx.Client(transport=httpx.MockTransport(handler)), "TestBot")
    assert cache.can_fetch("https://s.com/anything")
