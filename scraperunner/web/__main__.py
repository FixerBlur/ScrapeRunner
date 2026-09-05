from __future__ import annotations

import argparse
import logging

import uvicorn

LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}


def main() -> None:
    parser = argparse.ArgumentParser(prog="scraperunner.web", description="Run the scraperunner web UI.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    if args.host not in LOCAL_HOSTS:
        logging.basicConfig(level=logging.WARNING)
        logging.warning(
            "Binding to %s exposes the UI without authentication: anyone on that network can start crawls "
            "and read results. Keep it on 127.0.0.1 unless the network is trusted.", args.host,
        )
    uvicorn.run("scraperunner.web.app:app", host=args.host, port=args.port)


if __name__ == "__main__":
    main()
