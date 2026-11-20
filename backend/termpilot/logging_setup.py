"""Process-wide logging configuration."""

from __future__ import annotations

import logging
import sys


def configure_logging(level: str = "INFO") -> None:
    root = logging.getLogger()
    if any(getattr(handler, "_termpilot", False) for handler in root.handlers):
        root.setLevel(level.upper())
        return
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)-7s %(name)s: %(message)s", "%H:%M:%S"))
    handler._termpilot = True  # type: ignore[attr-defined]
    root.addHandler(handler)
    root.setLevel(level.upper())
    # Third-party clients are chatty at INFO.
    for noisy in ("httpx", "elastic_transport", "urllib3", "openai"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
