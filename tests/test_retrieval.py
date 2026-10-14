import os
import pytest
from app.services.pdf_service import PDFService
from app.services.retrieval_service import RetrievalService

SAMPLE_PDF = os.path.join(os.path.dirname(__file__), "sample_docs", "mca_syllabus.pdf")
TEST_DOC_ID = "test-doc-unit-1"

@pytest.fixture(scope="module", autouse=True)
def setup_and_teardown_index():
    # Extract & index
    extract = PDFService.extract_text_and_pages(SAMPLE_PDF)
    chunks = PDFService.chunk_document(extract["pages"])
    success = RetrievalService.index_document(TEST_DOC_ID, chunks)
    assert success is True
    yield
    # Cleanup
    RetrievalService.delete_index(TEST_DOC_ID)

def test_semantic_retrieval_page1():
    results = RetrievalService.search(TEST_DOC_ID, "How does leader election work in Raft consensus?")
    assert len(results) > 0
    top = results[0]
    assert top["page_number"] == 1
    assert "Raft" in top["text"]
    assert top["score"] >= 0.30

def test_semantic_retrieval_page2():
    results = RetrievalService.search(TEST_DOC_ID, "What guarantees are stated in CAP theorem for Apache Cassandra?")
    assert len(results) > 0
    pages = [r["page_number"] for r in results]
    assert 2 in pages

def test_semantic_retrieval_page3():
    results = RetrievalService.search(TEST_DOC_ID, "What is the marks weightage for viva voce and demonstration?")
    assert len(results) > 0
    top = results[0]
    assert top["page_number"] == 3
    assert "Viva Voce" in top["text"] or "25 Marks" in top["text"]

def test_completely_irrelevant_query_threshold():
    # A question completely unrelated to this syllabus
    results = RetrievalService.search(TEST_DOC_ID, "How to bake a chocolate cake using fresh strawberries?", threshold=0.35)
    assert len(results) == 0
