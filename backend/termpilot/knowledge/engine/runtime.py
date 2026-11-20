"""Resource locations and search-cluster settings for the document engine.

The engine never reads application settings directly. ``termpilot.knowledge``
calls :func:`configure` once; until then the defaults below point at
``backend/var``. Model files are fetched by ``scripts/fetch_models.py`` or, as
a fallback, downloaded on first use from the Hugging Face hub.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

_BACKEND_ROOT = Path(__file__).resolve().parents[3]


@dataclass
class EngineConfig:
    models_dir: Path = _BACKEND_ROOT / "var" / "models"
    search_url: str = "http://localhost:9200"
    search_username: str = "elastic"
    search_password: str | None = None
    index_prefix: str = "termpilot-library"
    request_timeout: int = 120
    # Skip optional GPU probing (torch) in the PDF parser.
    lighten: bool = True


_config = EngineConfig()


def _register_resources() -> None:
    os.environ.setdefault("TIKTOKEN_CACHE_DIR", tiktoken_dir())
    nltk_dir = str(_config.models_dir / "nltk_data")
    if nltk_dir not in os.environ.get("NLTK_DATA", ""):
        os.environ["NLTK_DATA"] = os.pathsep.join(part for part in (nltk_dir, os.environ.get("NLTK_DATA")) if part)
    # nltk reads NLTK_DATA only when first imported, so also update a loaded module.
    import nltk

    if nltk_dir not in nltk.data.path:
        nltk.data.path.insert(0, nltk_dir)


def configure(config: EngineConfig) -> None:
    global _config
    _config = config
    _register_resources()


def config() -> EngineConfig:
    return _config


def deepdoc_dir() -> str:
    """Directory with the OCR, layout and table-structure models."""
    return str(_config.models_dir / "deepdoc")


def tokenizer_stem() -> str:
    """Path of the tokenizer dictionary without its ``.txt`` suffix."""
    return str(_config.models_dir / "tokenizer" / "huqie")


def nlp_resource(name: str = "") -> str:
    base = _config.models_dir / "tokenizer"
    return str(base / name) if name else str(base)


def tiktoken_dir() -> str:
    return str(_config.models_dir / "tiktoken")


def es_mapping() -> str:
    return str(Path(__file__).with_name("store") / "es_mapping.json")


def index_name(owner: str) -> str:
    return f"{_config.index_prefix}-{owner}".lower()


_register_resources()
