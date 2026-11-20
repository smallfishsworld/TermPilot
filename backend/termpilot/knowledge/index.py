"""Per-student document index on the search cluster."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import xxhash

from termpilot.errors import FeatureUnavailable, UpstreamFailure
from termpilot.knowledge import providers

logger = logging.getLogger(__name__)

# Chunk keys the engine produces that are safe to store (the rest are images or scratch data).
_STORED_KEYS = (
    "docnm_kwd",
    "title_tks",
    "title_sm_tks",
    "content_with_weight",
    "content_ltks",
    "content_sm_ltks",
    "page_num_int",
    "position_int",
    "top_int",
)


@dataclass(frozen=True)
class Passage:
    rank: int
    document: str
    doc_key: str
    text: str
    score: float


def _quiet(prog: float | None = None, msg: str = "") -> None:
    logger.debug("ingest progress %s %s", prog, msg)


class LibraryIndex:
    """Ingest, search and delete the documents of one student."""

    def __init__(self, student_id: int) -> None:
        self.owner = str(student_id)

    @property
    def name(self) -> str:
        from termpilot.knowledge.engine import runtime

        return runtime.index_name(self.owner)

    def _connection(self):  # type: ignore[no-untyped-def]
        try:
            from termpilot.knowledge.engine.store.es_conn import ESConnection

            return ESConnection()
        except Exception as exc:  # the cluster client could not be created
            raise FeatureUnavailable("The document search service is not reachable.") from exc

    def ready(self) -> bool:
        try:
            return bool(self._connection().es.ping())
        except Exception:
            return False

    def ingest(self, filename: str, data: bytes, doc_key: str) -> int:
        """Parse, embed and store a document; returns the number of chunks."""
        from termpilot.knowledge.engine.chunker import chunk

        try:
            chunks = chunk(filename, binary=data, callback=_quiet)
        except NotImplementedError as exc:
            raise FeatureUnavailable(str(exc)) from exc
        chunks = [item for item in chunks if str(item.get("content_with_weight", "")).strip()]
        if not chunks:
            return 0
        try:
            vectors = providers.embed_batch([item["content_with_weight"] for item in chunks])
        except providers.EmbeddingUnavailable as exc:
            raise FeatureUnavailable(str(exc)) from exc

        now = datetime.now(UTC)
        rows: list[dict[str, Any]] = []
        for position, (item, vector) in enumerate(zip(chunks, vectors, strict=True)):
            row = {key: item[key] for key in _STORED_KEYS if key in item}
            row.update(
                {
                    "id": xxhash.xxh64(f"{doc_key}:{position}").hexdigest(),
                    "doc_id": doc_key,
                    "kb_id": self.name,
                    "docnm_kwd": filename,
                    "docnm": filename,
                    "chunk_order_int": position,
                    "available_int": 1,
                    "important_kwd": [],
                    "question_kwd": [],
                    "create_time": now.strftime("%Y-%m-%d %H:%M:%S"),
                    "create_timestamp_flt": now.timestamp(),
                    f"q_{len(vector)}_vec": vector,
                }
            )
            rows.append(row)
        try:
            connection = self._connection()
            connection.createIdx(self.name, "", len(vectors[0]))
            errors = connection.insert(rows, self.name)
        except Exception as exc:
            raise UpstreamFailure("The document could not be stored in the search index.") from exc
        if errors:
            logger.warning("Index errors for %s: %s", filename, errors[:3])
            raise UpstreamFailure("Some document chunks were rejected by the search index.")
        return len(rows)

    def search(self, question: str, top_k: int = 5) -> list[Passage]:
        from termpilot.knowledge.engine.nlp.search import Dealer

        connection = self._connection()
        try:
            if not connection.indexExist(self.name, ""):
                return []
            result = Dealer(dataStore=connection).retrieval(
                question=question,
                embd_mdl=providers.EmbeddingModel(),
                tenant_ids=self.owner,
                kb_ids=None,
                page=1,
                page_size=top_k,
                similarity_threshold=0.2,
                vector_similarity_weight=0.6,
                rerank_mdl=providers.RerankModel() if providers.rerank_available() else None,
            )
        except providers.EmbeddingUnavailable as exc:
            raise FeatureUnavailable(str(exc)) from exc
        except Exception as exc:
            logger.exception("Library search failed")
            raise UpstreamFailure("The document search failed.") from exc
        return [
            Passage(
                rank=rank,
                document=str(chunk.get("docnm_kwd") or "document").rsplit("/", 1)[-1],
                doc_key=str(chunk.get("doc_id") or ""),
                text=str(chunk.get("content_with_weight") or ""),
                score=float(chunk.get("similarity") or 0.0),
            )
            for rank, chunk in enumerate(result.get("chunks", []), start=1)
        ]

    def document_text(self, doc_key: str, max_chars: int = 24_000) -> str:
        """The stored text of one document in reading order, truncated to ``max_chars``."""
        connection = self._connection()
        if not connection.es.indices.exists(index=self.name):
            return ""
        response = connection.es.search(
            index=self.name,
            query={"term": {"doc_id": doc_key}},
            sort=[{"chunk_order_int": {"order": "asc", "unmapped_type": "integer"}}],
            source=["content_with_weight"],
            size=1000,
        )
        parts: list[str] = []
        total = 0
        for hit in response["hits"]["hits"]:
            text = str(hit["_source"].get("content_with_weight") or "")
            if total + len(text) > max_chars:
                parts.append(text[: max_chars - total])
                break
            parts.append(text)
            total += len(text)
        return "\n\n".join(parts)

    def delete_document(self, doc_key: str) -> int:
        try:
            return self._connection().delete({"doc_id": doc_key}, self.name, None)
        except FeatureUnavailable:
            raise
        except Exception as exc:
            raise UpstreamFailure("The document could not be removed from the search index.") from exc
