from __future__ import annotations

import csv
import json
from collections.abc import Sequence
from dataclasses import asdict, fields
from typing import TYPE_CHECKING
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Font
from openpyxl.utils import get_column_letter

from scraperunner.models import Item, PageResult

if TYPE_CHECKING:
    from scraperunner.compare import Changes

ITEM_COLUMNS = ("title", "price", "old_price", "link", "image", "page", "group", "text")
_XLSX_WIDTHS = {"title": 50, "price": 12, "old_price": 12, "link": 45, "image": 45, "page": 35, "group": 8, "text": 80}
_URL_COLUMNS = {"link", "image", "page"}


def export_pages_json(pages: Sequence[PageResult], path: Path) -> None:
    _write_json([page.to_dict() for page in pages], path)


def export_links_csv(pages: Sequence[PageResult], path: Path) -> None:
    """Flat table: one row per link or image found on a page."""
    rows = [
        (page.url, page.title, kind, url)
        for page in pages
        for kind, urls in (("link", page.links), ("image", page.images))
        for url in urls
    ]
    _write_csv(("page_url", "page_title", "type", "item_url"), rows, path)


def export_items_json(pages: Sequence[PageResult], path: Path) -> None:
    _write_json(flat_items(pages), path)


def export_items_csv(pages: Sequence[PageResult], path: Path) -> None:
    rows = [tuple(item[column] for column in ITEM_COLUMNS) for item in flat_items(pages)]
    _write_csv(ITEM_COLUMNS, rows, path)


def export_items_xlsx(pages: Sequence[PageResult], path: Path) -> None:
    """Excel sheet: bold frozen header, filters, sensible widths, clickable URLs."""
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Items"
    sheet.append(list(ITEM_COLUMNS))
    for cell in sheet[1]:
        cell.font = Font(bold=True)

    for item in flat_items(pages):
        sheet.append([item[column] for column in ITEM_COLUMNS])
        row = sheet[sheet.max_row]
        for cell, column in zip(row, ITEM_COLUMNS):
            if column in _URL_COLUMNS and cell.value:
                cell.hyperlink = cell.value
                cell.font = Font(color="0563C1", underline="single")

    for index, column in enumerate(ITEM_COLUMNS, start=1):
        sheet.column_dimensions[get_column_letter(index)].width = _XLSX_WIDTHS[column]
    sheet.freeze_panes = "A2"
    sheet.auto_filter.ref = sheet.dimensions

    path.parent.mkdir(parents=True, exist_ok=True)
    workbook.save(path)


def read_items_json(path: Path) -> list[Item]:
    """Items back from an ``items.json`` written by :func:`export_items_json`."""
    with path.open(encoding="utf-8") as fh:
        rows = json.load(fh)
    names = {f.name for f in fields(Item)}
    return [Item(**{key: value for key, value in row.items() if key in names}) for row in rows]


def export_changes_json(changes: "Changes", path: Path) -> None:
    _write_json_object(changes.to_dict(), path)


def flat_items(pages: Sequence[PageResult]) -> list[dict]:
    """Every item from every page, each tagged with the page it came from."""
    return [{**asdict(item), "page": page.url} for page in pages for item in page.items]


def unique_images(pages: Sequence[PageResult]) -> list[str]:
    return _unique(image for page in pages for image in page.images)


def unique_item_images(pages: Sequence[PageResult]) -> list[str]:
    return _unique(item.image for page in pages for item in page.items if item.image)


def _unique(urls) -> list[str]:
    return list(dict.fromkeys(urls))


def _write_json(data: list, path: Path) -> None:
    _write_json_object(data, path)


def _write_json_object(data, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)


def _write_csv(header: Sequence[str], rows: Sequence[tuple], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(header)
        writer.writerows(rows)
