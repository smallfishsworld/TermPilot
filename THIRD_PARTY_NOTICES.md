# Third-party notices

[中文版](THIRD_PARTY_NOTICES.zh-CN.md)

## RAGFlow

`backend/termpilot/knowledge/engine/` contains code adapted from
[RAGFlow](https://github.com/infiniflow/ragflow) release v0.16.0,
Copyright 2024-2025 The InfiniFlow Authors, licensed under the Apache License, Version 2.0.
A copy of the license is in [`LICENSES/Apache-2.0.txt`](LICENSES/Apache-2.0.txt).

Each adapted file keeps its original copyright header and has a note saying it was modified.

| Upstream path | Where it is here |
| --- | --- |
| `deepdoc/parser/*` (docx, excel, html, json, markdown, pdf, ppt, txt, utils) | `engine/parser/` |
| `deepdoc/vision/*` (ocr, layout, table structure, operators, post-processing) | `engine/vision/` |
| `rag/nlp/{__init__,query,rag_tokenizer,search,synonym,term_weight}.py` | `engine/nlp/` |
| `rag/utils/__init__.py` | `engine/utils.py` |
| `rag/utils/{doc_store_conn,es_conn}.py` | `engine/store/` |
| `rag/app/naive.py` | `engine/chunker.py` |
| `conf/mapping.json` | `engine/store/es_mapping.json` |

What I changed:

- Imports now live under `termpilot.knowledge.engine`. Model, dictionary and index-mapping paths come from
  `engine/runtime.py` instead of the RAGFlow project directory.
- The Elasticsearch connection takes its address and credentials from the runtime config, and it fails
  straight away instead of retrying for two minutes. Index names use a configurable prefix.
- The chunker no longer needs Apache Tika (so old `.doc` files aren't accepted). PowerPoint (`.pptx`) works
  through the existing slide parser, and Markdown files are read as UTF-8.
- When the `datrie` extension isn't installed, the tokenizer falls back to a pure-Python trie
  (`engine/simple_trie.py`).
- Removed the Python 2 compatibility code (`six`), the command-line test scripts and the vision CLI helper.
- Translated the one Chinese code comment (in `nlp/term_weight.py`) into English.
- `engine/runtime.py`, `engine/fields.py` and `engine/simple_trie.py` are new files.

The model weights are not in this repository. `backend/scripts/fetch_models.py` downloads them from the
Hugging Face repositories `InfiniFlow/deepdoc` and `InfiniFlow/text_concat_xgb_v1.0`, and the word
segmentation dictionary from the RAGFlow repository. Their own licenses apply.

## Campus code book

`backend/termpilot/campus/codebook.json` maps the department, college and class codes used by the academic
records system to their published names.
