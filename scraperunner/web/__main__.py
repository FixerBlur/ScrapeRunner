from __future__ import annotations

import argparse

import uvicorn


def main() -> None:
    parser = argparse.ArgumentParser(prog="scraperunner.web", description="Run the scraperunner web UI.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    uvicorn.run("scraperunner.web.app:app", host=args.host, port=args.port)


if __name__ == "__main__":
    main()
