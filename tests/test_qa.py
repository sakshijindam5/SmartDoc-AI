import os
import pytest
from app.services.pdf_service import PDFService
from app.services.retrieval_service import RetrievalService
from app.services.answer_service import AnswerService, NOT_FOUND_RESPONSE

SAMPLE_PDF = os.path.join(os.path.dirname(__file__), "sample_docs", "mca_syllabus.pdf")
TEST_DOC_ID = "test-doc-qa-eval"

@pytest.fixture(scope="module", autouse=True)
def setup_and_teardown_index():
    extract = PDFService.extract_text_and_pages(SAMPLE_PDF)
    chunks = PDFService.chunk_document(extract["pages"])
    RetrievalService.index_document(TEST_DOC_ID, chunks)
    yield
    RetrievalService.delete_index(TEST_DOC_ID)

def test_direct_question_known_answer():
    q = "What is the randomized election timeout range in Raft?"
    chunks = RetrievalService.search(TEST_DOC_ID, q)
    assert len(chunks) > 0
    ans = AnswerService.generate_answer(q, chunks, language="en")
    
    assert ans["is_supported"] is True
    assert 1 in ans["source_pages"]
    assert "150ms" in ans["answer"] or "300ms" in ans["answer"]
    assert len(ans["excerpts"]) > 0

def test_question_combining_multiple_pages():
    # Asks about Raft (Page 1) and project marks (Page 3)
    q = "What algorithm is used for consensus and how many marks are allocated for final project viva voce?"
    chunks = RetrievalService.search(TEST_DOC_ID, q, top_k=4)
    ans = AnswerService.generate_answer(q, chunks, language="en")
    
    assert ans["is_supported"] is True
    # Should identify both pages or relevant references
    pages = ans["source_pages"]
    assert 1 in pages or 3 in pages
    assert "Raft" in ans["answer"] or "25 Marks" in ans["answer"] or "Marks" in ans["answer"]

def test_paraphrased_question():
    # Original text: "Chord utilize consistent hashing with SHA-1 to map keys to nodes efficiently"
    # Paraphrased: "Which hashing technique does the Chord DHT algorithm apply?"
    q = "Which hashing technique does the Chord DHT algorithm apply?"
    chunks = RetrievalService.search(TEST_DOC_ID, q)
    ans = AnswerService.generate_answer(q, chunks, language="en")
    
    assert ans["is_supported"] is True
    assert 1 in ans["source_pages"]
    assert "SHA-1" in ans["answer"] or "consistent hashing" in ans["answer"]

def test_question_absent_from_document_must_refuse():
    # Question on topic completely absent from syllabus
    q = "What is the boiling point of liquid nitrogen at sea level?"
    chunks = RetrievalService.search(TEST_DOC_ID, q, threshold=0.35)
    ans = AnswerService.generate_answer(q, chunks, language="en")
    
    assert ans["is_supported"] is False
    assert ans["answer"] == NOT_FOUND_RESPONSE
    assert ans["source_pages"] == []
    assert ans["excerpts"] == []

def test_multilingual_question_hindi():
    q = "Raft अल्गोरिदम मध्ये लीडर इलेक्शन टाईमआउट किती आहे?"
    # Search with English/transliterated keywords
    chunks = RetrievalService.search(TEST_DOC_ID, "leader election timeout Raft")
    ans = AnswerService.generate_answer(q, chunks, language="hi")
    
    assert ans["is_supported"] is True
    assert 1 in ans["source_pages"]
    assert "दस्तावेजातील माहितीनुसार" in ans["answer"]

def test_multilingual_question_marathi():
    q = "प्रकल्पाचे व्हिवा व्होस चे गुण किती आहेत?"
    chunks = RetrievalService.search(TEST_DOC_ID, "viva voce demonstration marks")
    ans = AnswerService.generate_answer(q, chunks, language="mr")
    
    assert ans["is_supported"] is True
    assert 3 in ans["source_pages"]
    assert "दस्तऐवजातील पुराव्यानुसार" in ans["answer"]
