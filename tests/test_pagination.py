import pytest

from scraperunner.utils.pagination import detect_page_pattern, paginated_urls, parse_page_range


def test_range_and_list_are_merged_and_sorted():
    assert parse_page_range("3,1-2, 5") == [1, 2, 3, 5]


@pytest.mark.parametrize("bad", ["", "a-b", "5-2", "1--3", "1,"])
def test_invalid_ranges_raise(bad):
    with pytest.raises(ValueError):
        parse_page_range(bad)


def test_pattern_from_query_parameter():
    assert detect_page_pattern("https://s.com/list?sort=new&page=2") == "https://s.com/list?sort=new&page={page}"


def test_pattern_from_last_numeric_path_segment():
    assert detect_page_pattern("https://s.com/cat/12/page/3/") == "https://s.com/cat/12/page/{page}/"


def test_no_number_gives_none():
    assert detect_page_pattern("https://s.com/list") is None


def test_urls_are_expanded_with_detected_pattern():
    assert paginated_urls("https://s.com/list?page=1", "1-3") == [
        "https://s.com/list?page=1",
        "https://s.com/list?page=2",
        "https://s.com/list?page=3",
    ]


def test_explicit_pattern_wins():
    urls = paginated_urls("https://s.com/", "2", pattern="https://s.com/p/{page}/")
    assert urls == ["https://s.com/p/2/"]


def test_missing_pattern_is_an_error():
    with pytest.raises(ValueError):
        paginated_urls("https://s.com/list", "1-2")


def test_pasted_page_url_as_pattern_is_accepted():
    urls = paginated_urls("https://comfy.ua/ua/skovorodki/", "1-2", pattern="https://comfy.ua/ua/skovorodki/?p=2")
    assert urls == ["https://comfy.ua/ua/skovorodki/?p=1", "https://comfy.ua/ua/skovorodki/?p=2"]


def test_pattern_without_any_number_is_an_error():
    with pytest.raises(ValueError):
        paginated_urls("https://s.com/", "1-2", pattern="https://s.com/list")
