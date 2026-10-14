import os
import shutil
import uuid
import pymupdf
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from app.database import get_db
from app.config import settings
from app.models.document import Document
from app.schemas.document import (
    DocumentResponse,
    DocumentListResponse,
    DocumentDetailResponse,
    DocumentPreviewPage
)
from app.services.pdf_service import PDFService
from app.services.retrieval_service import RetrievalService

router = APIRouter(prefix="/api/documents", tags=["Documents"])

@router.post("/upload", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """
    Upload and process a PDF document:
    - Validates file type and size limit
    - Generates safe filename
    - Extracts text preserving page numbers
    - Detects scanned/image-only PDFs
    - Chunks text and builds hybrid vector search index
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file selected for upload.")

    # Read file content into memory to check size
    file_bytes = await file.read()
    file_size = len(file_bytes)

    # Validate type and size
    is_valid, validation_err = PDFService.validate_file(file.filename, file_size)
    if not is_valid:
        raise HTTPException(status_code=400, detail=validation_err)

    # Generate safe unique filename and destination path
    safe_name = PDFService.sanitize_filename(file.filename)
    dest_path = os.path.join(settings.UPLOAD_DIR, safe_name)

    # Save to disk
    with open(dest_path, "wb") as f:
        f.write(file_bytes)

    # Create document DB record
    doc_id = str(uuid.uuid4())
    doc_record = Document(
        id=doc_id,
        filename=file.filename,
        safe_filename=safe_name,
        file_path=dest_path,
        file_size_bytes=file_size,
        status="processing"
    )
    db.add(doc_record)
    db.commit()

    # Extract text page by page
    extract_result = PDFService.extract_text_and_pages(dest_path)
    doc_record.page_count = extract_result.get("total_pages", 0)

    if not extract_result["success"]:
        # Handle scanned or unextractable PDF
        doc_record.is_scanned = extract_result.get("is_scanned", False)
        doc_record.status = "scanned_needs_ocr" if doc_record.is_scanned else "error"
        doc_record.error_message = extract_result.get("error", "Failed to extract text.")
        db.commit()
        db.refresh(doc_record)
        
        raise HTTPException(
            status_code=422,
            detail=doc_record.error_message
        )

    # Chunk text retaining page numbers
    chunks = PDFService.chunk_document(extract_result["pages"])
    if not chunks:
        doc_record.status = "error"
        doc_record.error_message = "No readable text content found in document."
        db.commit()
        raise HTTPException(
            status_code=422,
            detail="The document could not be processed because no readable text was found."
        )

    # Build vector search index
    index_success = RetrievalService.index_document(doc_id, chunks)
    if not index_success:
        doc_record.status = "error"
        doc_record.error_message = "Failed to build document search index."
        db.commit()
        raise HTTPException(status_code=500, detail="Failed to create search index.")

    doc_record.total_chunks = len(chunks)
    doc_record.status = "ready"
    doc_record.error_message = None
    db.commit()
    db.refresh(doc_record)

    return doc_record

@router.get("", response_model=DocumentListResponse)
def list_documents(db: Session = Depends(get_db)):
    """List all uploaded documents."""
    docs = db.query(Document).order_by(Document.created_at.desc()).all()
    return DocumentListResponse(total=len(docs), documents=docs)

@router.get("/{document_id}", response_model=DocumentDetailResponse)
def get_document(document_id: str, db: Session = Depends(get_db)):
    """Get single document details and sample page text preview."""
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")

    # Generate page previews (first 3 pages)
    previews = []
    if os.path.exists(doc.file_path):
        try:
            pdf_doc = pymupdf.open(doc.file_path)
            for i in range(min(3, len(pdf_doc))):
                p_text = pdf_doc[i].get_text("text").strip()
                preview_snippet = p_text[:400] + ("..." if len(p_text) > 400 else "")
                previews.append(DocumentPreviewPage(
                    page_number=i + 1,
                    text_preview=preview_snippet
                ))
            pdf_doc.close()
        except Exception:
            pass

    return DocumentDetailResponse(
        id=doc.id,
        filename=doc.filename,
        file_size_bytes=doc.file_size_bytes,
        page_count=doc.page_count,
        is_scanned=doc.is_scanned,
        status=doc.status,
        total_chunks=doc.total_chunks,
        created_at=doc.created_at,
        updated_at=doc.updated_at,
        error_message=doc.error_message,
        preview_pages=previews
    )

@router.delete("/{document_id}", status_code=status.HTTP_200_OK)
def delete_document(document_id: str, db: Session = Depends(get_db)):
    """Deletes document, physical file, search index, and chat history."""
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")

    # Remove physical file
    if os.path.exists(doc.file_path):
        try:
            os.remove(doc.file_path)
        except Exception:
            pass

    # Remove vector index files
    RetrievalService.delete_index(document_id)

    # Delete DB record (cascade deletes chat history)
    db.delete(doc)
    db.commit()

    return {"message": f"Document '{doc.filename}' and all associated search data were successfully deleted."}

@router.get("/{document_id}/file")
def view_pdf_file(document_id: str, db: Session = Depends(get_db)):
    """Serves the PDF file for browser preview."""
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc or not os.path.exists(doc.file_path):
        raise HTTPException(status_code=404, detail="PDF file not found.")

    return FileResponse(
        path=doc.file_path,
        media_type="application/pdf",
        filename=doc.filename
    )
