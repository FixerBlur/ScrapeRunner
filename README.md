# ScrapeRunner

Point it at any URL. Get back links, images, readable text and, on catalogue
pages, structured items with title, price, old price, link and photo. Works from
the command line or a small web UI, exports to Excel, CSV and JSON, drives your
real Chrome when a site needs JavaScript or blocks bots, and can rerun a crawl
on a schedule and show you what changed.

No per-site rules, no AI, no cloud. One dependency set, one command.

## Highlights

- **Universal.** Crawls any site breadth-first with depth, page-count and domain limits, and respects `robots.txt`.
- **Fast.** Pages are fetched by a pool of workers with a per-host delay; transient errors are retried.
- **Structured items.** Detects repeated cards on listing pages and turns each into a row: title, price, old price, link, image, page, group, text. Several listings on one page are all captured.
- **Sale prices.** Tells the current price from a struck-through or "old" price.
- **Custom selectors.** When the heuristic gets a site wrong, give a CSS selector for the card and any field.
- **Real Chrome fallback.** Plain HTTP first. If a page comes back empty or blocked, it is reloaded in the Google Chrome already installed on your machine, over the DevTools protocol. No headless Chromium to download.
- **Pagination.** `--pages 1-10` expands a listing URL into every page; the page number is detected automatically.
- **Images done right.** Finds `src`, lazy-load attributes, `srcset`, `<picture>`, Open Graph tags and CSS backgrounds. On catalogue pages it downloads product photos only.
- **Schedules and price changes.** Repeat a crawl every N hours; every run is compared with the previous one: price changes with percentages, new and gone items.
- **Web UI.** Form, live progress, cards or table view, one-click `.xlsx` download, run history that survives restarts, dark theme by default.
- **Exports.** `items.xlsx`, `items.csv`, `items.json`, `pages.json`, `links.csv`, `changes.json`.

## Install

Requires Python 3.10+ and, for browser mode, Google Chrome.

```bash
git clone https://github.com/FixerBlur/ScrapeRunner.git
cd ScrapeRunner
pip install -r requirements.txt
```

Browser mode needs the Playwright client library only. Chrome itself is the one you already have:

```bash
pip install playwright
```

## Quick start

Web UI:

```bash
python -m scraperunner.web
```

Open http://127.0.0.1:8000, paste a URL, press Start. The JSON API is documented at `/api/docs`.

CLI:

```bash
python -m scraperunner https://books.toscrape.com --depth 1 --download-images
```

Scrape ten catalogue pages of a shop into an Excel sheet of products:

```bash
python -m scraperunner "https://shop.example/catalog?page=1" --pages 1-10 --depth 0
```

Run it again tomorrow and see what changed:

```bash
python -m scraperunner "https://shop.example/catalog?page=1" --pages 1-10 --depth 0 \
  --out results/today --compare results/yesterday
```

```
Pages: 10 (failed: 0)
Items: 500
Links: 6230
Images: 1270
Output: /path/to/results/today

Changes vs results/yesterday: 12 price changes, 3 new, 1 gone, 484 unchanged
  1 038 ₴ -> 899 ₴ (-13.4%)  Frying pan Berlin 28 cm
  ...
```

## How it works

```
URL ──> HTTP fetch ──> looks empty or blocked? ──> real Chrome fetch
                │                                        │
                └──────────────> HTML <──────────────────┘
                                  │
             ┌────────────┬───────┴────────┬───────────────┐
           links        images        repeated cards      text
                                     (title, price, ...)
                                  │
                    pages.json  items.xlsx/csv/json  links.csv  images/
```

**Auto mode** is the default. Every page is requested over HTTP first. A page
that comes back with almost no links or visible text is treated as a JavaScript
shell or a bot-protection stub and refetched in Chrome. Static sites never open
a browser; React storefronts and protected shops do, and only for the pages that
need it.

**Browser mode** launches a visible Chrome window with its own profile
(`%LOCALAPPDATA%\scraperunner-chrome` on Windows). Sites see an ordinary
browser, so checks that block headless automation pass. The window stays open
between crawls. If a site ever shows a challenge or a login page, solve it there
once and rerun. A crawl with `--proxy` gets its own Chrome profile and port, so
it never silently reuses a direct-connection window.

**Items** come from groups of sibling blocks that share a tag and classes and
each contain a link and an image. On a catalogue that is the product grid; on a
news site, the article list. Every group of three or more cards is kept and
numbered in page order, so a page with "sale" and "new arrivals" sections gives
both. A price is the innermost element whose whole text is a price, so
`<span>449</span><span>₴</span>` is read as one value while `+4 ₴` bonuses and
`-589 ₴` discounts are ignored. A price inside `<del>`, `<s>` or an element with
an `old`/`was`/`regular` class becomes `old_price`; with two plain prices, the
higher one is treated as the previous price.

**Custom selectors** replace any part of that. `--card-selector "div.product"`
picks the cards; `--title-selector`, `--price-selector`, `--old-price-selector`,
`--link-selector` and `--image-selector` are looked up inside each card. Fields
without a selector keep using the heuristic.

**Changes** are computed by matching items between two runs by link: same link
with a different price is a price change, a link only in the new run is a new
item, a link only in the old run is gone.

## CLI reference

```
python -m scraperunner URL [options]
```

| Group | Flag | Meaning |
|-------|------|---------|
| Crawl | `-d, --depth N` | link levels to follow from the start page (default 1) |
| | `-m, --max-pages N` | hard cap on visited pages (default 100) |
| | `--all-domains` | follow links to other sites too |
| | `--ignore-robots` | skip `robots.txt` checks |
| Pagination | `--pages SPEC` | pages to seed: `1-10`, `1,3,7`, `1-3,10` |
| | `--page-pattern URL` | template with `{page}`; detected from the URL if omitted |
| Network | `--delay S` | minimum gap between requests to one host, jittered ±50% (default 0.5) |
| | `--timeout S` | request timeout (default 15) |
| | `--retries N` | extra attempts on network errors and 5xx/429 (default 2) |
| | `--concurrency N` | pages fetched in parallel (default 4) |
| | `--proxy URL` | `http://user:pass@host:port` or `socks5://host:port` |
| | `--user-agent UA` | custom User-Agent |
| Browser | `--mode http\|browser\|auto` | `auto` (default) uses HTTP with Chrome fallback |
| | `--settle S` | seconds to let scripts run after the DOM is ready (default 1.5) |
| | `--cdp URL` | attach to a Chrome you started yourself, e.g. `http://127.0.0.1:9222` |
| Selectors | `--card-selector CSS` | one item card, e.g. `article.product` |
| | `--title-selector`, `--price-selector`, `--old-price-selector`, `--link-selector`, `--image-selector` | fields inside a card |
| Output | `--text` | also store readable page text |
| | `--download-images` | save images to `<out>/images/` |
| | `--compare DIR` | compare items with a previous run's folder, print and write `changes.json` |
| | `-o, --out DIR` | output folder (default `results/`) |
| | `-v, --verbose` | debug logging |

### Pagination

The page number is found in the query (`?page=1`, `?p=1`) or in the last numeric
path segment (`/page/1/`). Give the template yourself when the site uses another
shape:

```bash
python -m scraperunner https://books.toscrape.com --pages 1-5 \
  --page-pattern "https://books.toscrape.com/catalogue/page-{page}.html"
```

Pasting the address of any real page into `--page-pattern` also works; the number
in it is replaced automatically.

### Output files

| File | Content |
|------|---------|
| `items.xlsx` | one row per item; bold frozen header, filters, clickable links |
| `items.csv`, `items.json` | the same rows as plain data |
| `changes.json` | with `--compare`: price changes, new and gone items |
| `pages.json` | one object per page: url, status, title, depth, links, images, items, text |
| `links.csv` | flat table of every link and image with the page it was found on |
| `images/` | downloaded photos, when `--download-images` is set |

### Scheduling from the command line

Use your system scheduler (cron, Windows Task Scheduler) with `--out` set to a
dated folder and `--compare` pointing at the previous one. The web UI does this
for you, see below.

## Web UI

```bash
python -m scraperunner.web --host 127.0.0.1 --port 8000
```

- Every CLI option is a form field; network settings and custom selectors sit under **Advanced**.
- **Repeat**: pick an interval and the crawl becomes a schedule. Schedules survive restarts, can be run on demand or deleted.
- Live progress: state, pages, items, links, images, downloads, last visited URLs, Cancel button.
- Results in tabs: Items (cards or a full table), **Changes** against the previous run of the same URL, Pages, Links, Images gallery, Text.
- Download buttons for every export file, including `Download table (.xlsx)`.
- **History** of all runs, restored from disk on startup; open any past run.
- Dark theme by default, light theme one click away, choice remembered.

Each run is stored under `results/<job id>/` together with a `job.json` that lets
the server pick it up again after a restart. Schedules live in
`results/schedules.json`.

## Project layout

```
scraperunner/
  cli.py           command-line interface
  runner.py        one crawl run: crawl, export, download (shared by CLI and web)
  crawler.py       breadth-first crawl with a worker pool, per-host throttle, limits
  compare.py       diff of two item lists: price changes, new, gone
  config.py        ScrapeConfig, Selectors, fetch modes
  models.py        FetchResult, PageResult, Item
  http.py          the one shared HTTP client
  downloader.py    image saving
  exporter.py      xlsx / csv / json writers and readers
  fetcher/         http (with retries), browser (real Chrome over CDP), auto, chrome launcher
  parser/          links, images, items (cards + selectors), prices, text
  utils/           URL normalisation, pagination, robots.txt cache
  web/             FastAPI app, persistent jobs, scheduler
  web/static/      frontend as plain ES modules: app.js, results.js, dom.js (no build step)
tests/             pytest suite
```

## Development

```bash
pip install -r requirements.txt pytest
pytest
```

The suite runs without network access: the crawler, retries, jobs and scheduler
are exercised against fakes.

## Good citizenship

ScrapeRunner respects `robots.txt` by default, keeps a minimum delay per host
even when crawling in parallel, and identifies itself in the User-Agent. Browser
mode is a real browser with a real profile, nothing is spoofed or hidden.
Bypassing CAPTCHAs or evading bot protection is out of scope. Check a site's
terms before scraping it, keep delays reasonable, and do not overload servers.

## License

MIT
