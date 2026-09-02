from scraperunner.compare import compare_items
from scraperunner.models import Item


def item(link, price=None, title=None):
    return Item(title=title or link, link=link, image=None, price=price, old_price=None, text="")


def test_added_removed_changed_and_unchanged():
    before = [item("/a", "100 ₴"), item("/b", "200 ₴"), item("/c", "300 ₴")]
    after = [item("/a", "100 ₴"), item("/b", "150 ₴"), item("/d", "400 ₴")]

    changes = compare_items(before, after)

    assert [i.link for i in changes.added] == ["/d"]
    assert [i.link for i in changes.removed] == ["/c"]
    assert changes.unchanged == 1
    (change,) = changes.price_changes
    assert (change.link, change.before, change.after, change.delta_pct) == ("/b", "200 ₴", "150 ₴", -25.0)


def test_missing_price_gives_no_percentage():
    (change,) = compare_items([item("/a", None)], [item("/a", "5 ₴")]).price_changes
    assert change.delta_pct is None and change.after == "5 ₴"


def test_to_dict_is_json_friendly():
    data = compare_items([item("/a", "1 ₴")], [item("/a", "2 ₴")]).to_dict()
    assert data["price_changes"][0]["delta_pct"] == 100.0
