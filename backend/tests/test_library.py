import io

import pytest
from pydantic import SecretStr

from termpilot.errors import FeatureUnavailable
from termpilot.knowledge import providers
from termpilot.knowledge.extract import extract_text
from termpilot.knowledge.index import LibraryIndex, Passage
from termpilot.settings import BACKEND_ROOT

needs_language_data = pytest.mark.skipif(
    not (BACKEND_ROOT / "var" / "models" / "tokenizer" / "huqie.txt").exists(),
    reason="run scripts/fetch_models.py --skip-ocr first",
)


class FakeCluster:
    def __init__(self) -> None:
        self.created: list[tuple[str, int]] = []
        self.rows: list[dict] = []
        self.deleted: list[dict] = []

    def createIdx(self, name, kb, size):  # mirrors the engine interface
        self.created.append((name, size))

    def insert(self, rows, name):
        self.rows.extend(rows)
        return []

    def delete(self, condition, name, kb):
        self.deleted.append(condition)
        return 3


@needs_language_data
def test_ingest_stores_vectors_and_reading_order(monkeypatch):
    cluster = FakeCluster()
    monkeypatch.setattr(LibraryIndex, "_connection", lambda self: cluster)
    monkeypatch.setattr(providers, "embed_batch", lambda texts: [[0.25, 0.5, 0.75] for _ in texts])
    text = "# Graphs\n" + "\n\n".join(
        f"## Topic {n}\n" + "Breadth first search explores level by level. " * 30 for n in range(4)
    )
    count = LibraryIndex(7).ingest("notes.md", text.encode(), "doc-key")
    assert count == len(cluster.rows) > 1
    assert cluster.created == [("termpilot-library-7", 3)]
    first = cluster.rows[0]
    assert first["doc_id"] == "doc-key" and first["kb_id"] == "termpilot-library-7"
    assert first["q_3_vec"] == [0.25, 0.5, 0.75] and first["available_int"] == 1
    assert [row["chunk_order_int"] for row in cluster.rows] == list(range(count))
    assert all("image" not in row for row in cluster.rows)
    assert len({row["id"] for row in cluster.rows}) == count


@needs_language_data
def test_ingest_without_embeddings_is_reported_as_unavailable(monkeypatch):
    monkeypatch.setattr(LibraryIndex, "_connection", lambda self: FakeCluster())

    def unavailable(texts):
        raise providers.EmbeddingUnavailable("no key")

    monkeypatch.setattr(providers, "embed_batch", unavailable)
    with pytest.raises(FeatureUnavailable):
        LibraryIndex(7).ingest("notes.txt", b"some text", "k")


def test_library_api_requires_embeddings(client, auth):
    state = client.get("/api/library/documents", headers=auth).json()
    assert state["available"] is False and "TP_EMBEDDING_API_KEY" in state["reason"]
    report = client.post(
        "/api/library/documents", files=[("files", ("a.md", b"# hi", "text/markdown"))], headers=auth
    ).json()
    assert report["uploaded"] == [] and "TP_EMBEDDING_API_KEY" in report["failed"][0]["reason"]


def test_library_upload_validation_and_delete(client, auth, settings, monkeypatch):
    settings.embedding_api_key = SecretStr("test")
    calls: list[str] = []
    monkeypatch.setattr(LibraryIndex, "ready", lambda self: True)
    monkeypatch.setattr(LibraryIndex, "ingest", lambda self, name, data, key: calls.append(name) or 4)
    monkeypatch.setattr(LibraryIndex, "delete_document", lambda self, key: calls.append(f"delete {key}") or 4)
    monkeypatch.setattr(LibraryIndex, "search", lambda self, q, top_k=5: [Passage(1, "notes.md", "k", "text", 0.9)])
    files = [
        ("files", ("notes.md", b"# Heaps", "text/markdown")),
        ("files", ("fake.pdf", b"not a pdf", "application/pdf")),
        ("files", ("virus.exe", b"MZ", "application/octet-stream")),
    ]
    report = client.post("/api/library/documents", files=files, headers=auth).json()
    assert [item["filename"] for item in report["uploaded"]] == ["notes.md"]
    assert report["uploaded"][0]["status"] == "ready" and report["uploaded"][0]["chunks"] == 4
    assert {item["filename"] for item in report["failed"]} == {"fake.pdf", "virus.exe"}
    again = client.post(
        "/api/library/documents", files=[("files", ("notes.md", b"x", "text/markdown"))], headers=auth
    ).json()
    assert "already in your library" in again["failed"][0]["reason"]

    document = client.get("/api/library/documents", headers=auth).json()["documents"][0]
    assert client.delete(f"/api/library/documents/{document['id']}", headers=auth).status_code == 204
    assert calls[-1].startswith("delete ")
    assert client.get("/api/library/documents", headers=auth).json()["documents"] == []


def test_attachment_text_from_office_files():
    from docx import Document
    from pptx import Presentation

    buffer = io.BytesIO()
    document = Document()
    document.add_paragraph("Lab 4 is due on Friday.")
    table = document.add_table(rows=1, cols=2)
    table.cell(0, 0).text, table.cell(0, 1).text = "Item", "Weight"
    document.save(buffer)
    text, truncated = extract_text("brief.docx", buffer.getvalue(), 1000)
    assert "Lab 4 is due on Friday." in text and "Item | Weight" in text and not truncated

    buffer = io.BytesIO()
    deck = Presentation()
    slide = deck.slides.add_slide(deck.slide_layouts[1])
    slide.shapes.title.text = "Dynamic programming"
    deck.save(buffer)
    text, _ = extract_text("week9.pptx", buffer.getvalue(), 1000)
    assert text.startswith("Slide 1\nDynamic programming")

    text, truncated = extract_text("long.txt", ("word " * 500).encode("gb18030"), 100)
    assert truncated and len(text) == 100
