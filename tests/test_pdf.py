import os
import pytest
from app.services.pdf_service import PDFService

SAMPLE_PDF = os.path.join(os.path.dirname(__file__), "sample_docs", "mca_syllabus.pdf")
SCANNED_PDF = os.path.join(os.path.dirname(__file__), "sample_docs", "scanned_mock.pdf")

def test_validate_file_extension():
    valid, msg = PDFService.validate_file("notes.pdf", 1000)
    assert valid is True
    assert msg == ""

    invalid, msg = PDFService.validate_file("notes.exe", 1000)
    assert invalid is False
    assert "Only PDF documents are allowed" in msg

def test_extract_text_and_preserve_pages():
    assert os.path.exists(SAMPLE_PDF), f"File {SAMPLE_PDF} not found"
    result = PDFService.extract_text_and_pages(SAMPLE_PDF)
    assert result["success"] is True
    assert result["total_pages"] == 3
    assert result["is_scanned"] is False
    
    # Check page 1 has Raft or Distributed Architecture
    pages = result["pages"]
    assert len(pages) == 3
    assert pages[0]["page_number"] == 1
    assert "Distributed Architecture Fundamentals" in pages[0]["text"]
    assert pages[1]["page_number"] == 2
    assert "Microservices and Storage Systems" in pages[1]["text"]
    assert pages[2]["page_number"] == 3
    assert "Final Examination Criteria" in pages[2]["text"]

def test_detect_scanned_pdf():
    assert os.path.exists(SCANNED_PDF)
    result = PDFService.extract_text_and_pages(SCANNED_PDF)
    assert result["success"] is False
    assert result["is_scanned"] is True
    assert "Scanned or image-based PDF detected" in result["error"]

def test_chunking_retains_page_metadata():
    result = PDFService.extract_text_and_pages(SAMPLE_PDF)
    chunks = PDFService.chunk_document(result["pages"], chunk_size=300, chunk_overlap=50)
    assert len(chunks) >= 3
    for chunk in chunks:
        assert "chunk_id" in chunk
        assert "page_number" in chunk
        assert chunk["page_number"] in [1, 2, 3]
        assert len(chunk["text"]) > 0
