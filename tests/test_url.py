from scraperunner.utils.url import is_same_domain, normalize_url, url_to_filename

BASE = "https://example.com/blog/post"


def test_relative_is_resolved():
    assert normalize_url("../about", BASE) == "https://example.com/about"


def test_fragment_is_stripped():
    assert normalize_url("/page#section", BASE) == "https://example.com/page"


def test_non_http_is_rejected():
    for bad in ("mailto:a@b.c", "javascript:void(0)", "#top", "", "tel:123", "data:image/png;base64,x"):
        assert normalize_url(bad, BASE) is None


def test_host_is_lowercased_and_root_path_added():
    assert normalize_url("HTTPS://Example.COM", BASE) == "https://example.com/"


def test_same_domain_ignores_www():
    assert is_same_domain("https://www.example.com/a", "https://example.com/b")
    assert not is_same_domain("https://example.com", "https://other.com")


def test_filename_is_safe_and_unique():
    a = url_to_filename("https://x.com/img/photo one.jpg")
    b = url_to_filename("https://x.com/img/photo one.jpg?v=2")
    assert a.endswith(".jpg") and " " not in a
    assert a != b
