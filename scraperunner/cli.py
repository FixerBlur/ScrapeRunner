from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from scraperunner.compare import compare_items
from scraperunner.config import DEFAULT_USER_AGENT, FetchMode, ScrapeConfig, Selectors
from scraperunner.exporter import export_changes_json, flat_items, read_items_json
from scraperunner.models import Item
from scraperunner.parser.items import validate_selectors
from scraperunner.runner import run_crawl

SELECTOR_FIELDS = ("card", "title", "price", "old_price", "link", "image")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="scraperunner",
        description="Crawl any website and extract links, images, text and catalogue items.",
    )
    parser.add_argument("url", help="Start URL, e.g. https://example.com")

    crawl = parser.add_argument_group("crawl limits")
    crawl.add_argument("-d", "--depth", type=int, default=1, help="Link depth to follow (default: 1)")
    crawl.add_argument("-m", "--max-pages", type=int, default=100, help="Stop after N pages (default: 100)")
    crawl.add_argument("--all-domains", action="store_true", help="Follow links to other domains")
    crawl.add_argument("--ignore-robots", action="store_true", help="Do not respect robots.txt")

    paging = parser.add_argument_group("pagination")
    paging.add_argument("--pages", help="Page numbers to seed, e.g. '1-10' or '1,3,5'")
    paging.add_argument(
        "--page-pattern",
        help="URL template with {page}, e.g. https://site.com/list?page={page} (auto-detected if omitted)",
    )

    net = parser.add_argument_group("network")
    net.add_argument("--delay", type=float, default=0.5, help="Minimum seconds between requests to one host (default: 0.5)")
    net.add_argument("--timeout", type=float, default=15.0, help="Request timeout in seconds")
    net.add_argument("--retries", type=int, default=2, help="Extra attempts on network errors and 5xx (default: 2)")
    net.add_argument("--concurrency", type=int, default=4, help="Pages fetched in parallel (default: 4)")
    net.add_argument("--proxy", help="Proxy URL, e.g. http://user:pass@host:port or socks5://host:port")
    net.add_argument("--user-agent", default=DEFAULT_USER_AGENT)

    browser = parser.add_argument_group("browser")
    browser.add_argument(
        "--mode",
        choices=[mode.value for mode in FetchMode],
        default=FetchMode.AUTO.value,
        help="http = fast, browser = real Chrome, auto = http with Chrome fallback",
    )
    browser.add_argument("--settle", type=float, default=1.5, help="Seconds to let JS run after load (default: 1.5)")
    browser.add_argument("--cdp", help="Attach to a Chrome you started yourself, e.g. http://127.0.0.1:9222")

    selectors = parser.add_argument_group("custom selectors (override item detection)")
    selectors.add_argument("--card-selector", metavar="CSS", help="Selector matching one item card, e.g. 'div.product'")
    for name in SELECTOR_FIELDS[1:]:
        selectors.add_argument(f"--{name.replace('_', '-')}-selector", metavar="CSS", help=f"Selector for the {name.replace('_', ' ')} inside a card")

    output = parser.add_argument_group("output")
    output.add_argument("--text", action="store_true", help="Also store readable page text")
    output.add_argument("--download-images", action="store_true", help="Save found images to disk")
    output.add_argument("--compare", type=Path, metavar="DIR", help="Compare items with a previous run's folder and write changes.json")
    output.add_argument("-o", "--out", type=Path, default=Path("results"), help="Output folder")
    output.add_argument("-v", "--verbose", action="store_true", help="Debug logging")
    return parser


def config_from_args(args: argparse.Namespace) -> ScrapeConfig:
    selectors = Selectors(**{name: getattr(args, f"{name}_selector") for name in SELECTOR_FIELDS})
    validate_selectors(selectors)
    return ScrapeConfig(
        start_url=args.url,
        depth=args.depth,
        max_pages=args.max_pages,
        same_domain=not args.all_domains,
        respect_robots=not args.ignore_robots,
        pages=args.pages,
        page_pattern=args.page_pattern,
        delay=args.delay,
        timeout=args.timeout,
        retries=args.retries,
        concurrency=args.concurrency,
        proxy=args.proxy,
        user_agent=args.user_agent,
        mode=FetchMode(args.mode),
        settle=args.settle,
        cdp_url=args.cdp,
        selectors=selectors,
        extract_text=args.text,
        download_images=args.download_images,
        output_dir=args.out,
    )


def run(config: ScrapeConfig, compare_with: Path | None = None) -> int:
    report = run_crawl(config)
    downloaded = f" (downloaded: {len(report.downloaded)})" if config.download_images else ""
    print(
        f"\nPages: {len(report.pages)} (failed: {report.failed})"
        f"\nItems: {report.total_items}"
        f"\nLinks: {report.total_links}"
        f"\nImages: {len(report.images)}{downloaded}"
        f"\nOutput: {config.output_dir.resolve()}"
    )
    if compare_with is not None:
        print_changes(compare_with, [Item(**{k: v for k, v in row.items() if k != "page"}) for row in flat_items(report.pages)], config.output_dir)
    return 0


def print_changes(previous_dir: Path, items: list[Item], output_dir: Path) -> None:
    previous_file = previous_dir / "items.json"
    if not previous_file.exists():
        print(f"\nNothing to compare: {previous_file} not found")
        return
    changes = compare_items(read_items_json(previous_file), items)
    export_changes_json(changes, output_dir / "changes.json")
    print(
        f"\nChanges vs {previous_dir}: {len(changes.price_changes)} price changes, "
        f"{len(changes.added)} new, {len(changes.removed)} gone, {changes.unchanged} unchanged"
    )
    for change in changes.price_changes[:20]:
        delta = f" ({change.delta_pct:+.1f}%)" if change.delta_pct is not None else ""
        print(f"  {change.before or '-'} -> {change.after or '-'}{delta}  {change.title or change.link}")


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(message)s",
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    try:
        sys.exit(run(config_from_args(args), args.compare))
    except KeyboardInterrupt:
        print("\nInterrupted.")
        sys.exit(130)
    except (ValueError, RuntimeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(2)
