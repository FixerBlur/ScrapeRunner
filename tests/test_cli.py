import json
from pathlib import Path

import pytest

from scraperunner import cli
from scraperunner.config import FetchMode
from scraperunner.exporter import export_items_json
from scraperunner.models import Item


def test_args_map_onto_config():
    args = cli.build_parser().parse_args([
        "https://s.com", "-d", "2", "--mode", "browser", "--pages", "1-3", "--concurrency", "8",
        "--card-selector", "div.p", "--price-selector", ".price", "--text",
    ])
    config = cli.config_from_args(args)
    assert config.depth == 2 and config.mode is FetchMode.BROWSER and config.pages == "1-3"
    assert config.concurrency == 8 and config.extract_text
    assert config.selectors.card == "div.p" and config.selectors.price == ".price"


def test_invalid_selector_exits_with_code_2(capsys):
    with pytest.raises(SystemExit) as exit_info:
        cli.main(["https://s.com", "--price-selector", "div[[["])
    assert exit_info.value.code == 2
    assert "price selector" in capsys.readouterr().err


def test_print_changes_reports_and_writes_file(tmp_path: Path, capsys):
    previous = tmp_path / "prev"
    export_items_json([{"title": "Pan", "link": "/p", "image": None, "price": "100 ₴", "old_price": None, "text": "", "group": 1, "page": "x"}], previous / "items.json")
    now = [Item(title="Pan", link="/p", image=None, price="80 ₴", old_price=None, text="")]

    cli.print_changes(previous, now, tmp_path / "out")

    out = capsys.readouterr().out
    assert "1 price changes" in out and "-20.0%" in out
    changes = json.loads((tmp_path / "out" / "changes.json").read_text(encoding="utf-8"))
    assert changes["price_changes"][0]["after"] == "80 ₴"


def test_print_changes_without_previous_file(tmp_path: Path, capsys):
    cli.print_changes(tmp_path / "nowhere", [], tmp_path / "out")
    assert "Nothing to compare" in capsys.readouterr().out
