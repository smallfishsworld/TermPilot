"""Download the models and language data the document library needs.

Usage:  python scripts/fetch_models.py [--target var/models] [--skip-ocr]

Everything lands in ``backend/var/models`` (ignored by git):

* ``deepdoc/``    OCR, layout and table-structure models (Hugging Face: InfiniFlow/deepdoc)
                  and the text-merge model (InfiniFlow/text_concat_xgb_v1.0)
* ``tokenizer/``  the Chinese segmentation dictionary ``huqie.txt``
* ``nltk_data/``  English tokenizer, stop words and WordNet
* ``tiktoken/``   the cl100k_base encoding used to count tokens

Behind a firewall, set HF_ENDPOINT (e.g. https://hf-mirror.com) before running.
"""

from __future__ import annotations

import argparse
import os
import sys
import urllib.request
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
DICTIONARY_URL = "https://raw.githubusercontent.com/infiniflow/ragflow/v0.16.0/rag/res/huqie.txt"
NLTK_PACKAGES = ("punkt", "punkt_tab", "stopwords", "wordnet", "omw-1.4", "averaged_perceptron_tagger")


def fetch_vision_models(target: Path) -> None:
    from huggingface_hub import snapshot_download

    directory = target / "deepdoc"
    directory.mkdir(parents=True, exist_ok=True)
    print(f"• document vision models -> {directory}")
    snapshot_download(repo_id="InfiniFlow/deepdoc", local_dir=directory)
    snapshot_download(repo_id="InfiniFlow/text_concat_xgb_v1.0", local_dir=directory)


def fetch_dictionary(target: Path) -> None:
    path = target / "tokenizer" / "huqie.txt"
    if path.exists() and path.stat().st_size > 1_000_000:
        print(f"• tokenizer dictionary already present at {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    print(f"• tokenizer dictionary -> {path}")
    urllib.request.urlretrieve(DICTIONARY_URL, path)


def fetch_nltk(target: Path) -> None:
    import nltk

    directory = target / "nltk_data"
    print(f"• NLTK data -> {directory}")
    for package in NLTK_PACKAGES:
        nltk.download(package, download_dir=str(directory), quiet=True)


def fetch_tiktoken(target: Path) -> None:
    directory = target / "tiktoken"
    directory.mkdir(parents=True, exist_ok=True)
    os.environ["TIKTOKEN_CACHE_DIR"] = str(directory)
    import tiktoken

    print(f"• tiktoken encoding -> {directory}")
    tiktoken.get_encoding("cl100k_base")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--target", type=Path, default=BACKEND / "var" / "models")
    parser.add_argument(
        "--skip-ocr", action="store_true", help="skip the ~200 MB vision models (text files still work)"
    )
    options = parser.parse_args()
    target = options.target.resolve()
    if not options.skip_ocr:
        fetch_vision_models(target)
    fetch_dictionary(target)
    fetch_nltk(target)
    fetch_tiktoken(target)
    print("Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
