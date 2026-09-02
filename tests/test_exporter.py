from pathlib import Path

from openpyxl import load_workbook

from scraperunner.exporter import export_items_xlsx
from scraperunner.models import Item, PageResult


def test_items_xlsx_has_header_rows_and_links(tmp_path: Path):
    item = Item(title="Pan", link="https://s.com/p/1", image="https://s.com/i.jpg", price="449 ₴", old_price="1 038 ₴", text="Pan 449 ₴")
    page = PageResult(url="https://s.com/", status=200, items=[item])
    path = tmp_path / "items.xlsx"

    export_items_xlsx([page], path)

    sheet = load_workbook(path).active
    rows = list(sheet.iter_rows(values_only=True))
    assert rows[0] == ("title", "price", "old_price", "link", "image", "page", "group", "text")
    assert rows[1] == ("Pan", "449 ₴", "1 038 ₴", "https://s.com/p/1", "https://s.com/i.jpg", "https://s.com/", 1, "Pan 449 ₴")
    assert sheet["D2"].hyperlink.target == "https://s.com/p/1"
    assert sheet.freeze_panes == "A2"
