"""Run the API with ``python -m termpilot`` (add ``--reload`` while developing)."""

from __future__ import annotations

import argparse

import uvicorn

from termpilot.settings import get_settings


def main() -> None:
    settings = get_settings()
    parser = argparse.ArgumentParser(prog="termpilot", description="Start the TermPilot API server.")
    parser.add_argument("--host", default=settings.host)
    parser.add_argument("--port", type=int, default=settings.port)
    parser.add_argument("--reload", action="store_true", help="restart on code changes")
    options = parser.parse_args()
    uvicorn.run("termpilot.main:app", host=options.host, port=options.port, reload=options.reload)


if __name__ == "__main__":
    main()
