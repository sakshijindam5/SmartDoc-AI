import uuid
from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.document import Document
from app.schemas.chat import (
    AskQuestionRequest,
    AskQuestionResponse,
    ChatHistoryResponse,
    ConversationSummary,
    SourceExcerpt
)
from app.services.retrieval_service import RetrievalService
from app.services.answer_service import AnswerService
from app.services.history_service import HistoryService

router = APIRouter(tags=["Chat & Q&A"])

@router.post("/api/documents/{document_id}/ask", response_model=AskQuestionResponse)
def ask_question(
    document_id: str,
    payload: AskQuestionRequest,
    db: Session = Depends(get_db)
):
    """
    Intelligent Question Answering:
    - Restricts search exclusively to the selected document
    - Retrieves top relevant passages using semantic similarity and keyword matching
    - Formulates an evidence-based answer supported by exact page references
    - Clearly replies 'Answer not found in the uploaded document.' if unsupported
    - Multilingual response support (English, Hindi, Marathi)
    """
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")

    if doc.status != "ready":
        raise HTTPException(
            status_code=400,
            detail=f"Document is not ready for querying (Current status: {doc.status}). {doc.error_message or ''}"
        )

    # Validate language selection
    lang = payload.language.lower()
    if lang not in ["en", "hi", "mr"]:
        lang = "en"

    # Step 1: Hybrid Retrieval
    retrieved_chunks = RetrievalService.search(document_id, payload.question)

    # Step 2: Answer Generation (LLM or Extractive Fallback)
    answer_result = AnswerService.generate_answer(
        question=payload.question,
        retrieved_chunks=retrieved_chunks,
        language=lang
    )

    conversation_id = payload.conversation_id or str(uuid.uuid4())

    # Step 3: Persist in SQLite
    saved_chat = HistoryService.save_message(
        db=db,
        document_id=document_id,
        conversation_id=conversation_id,
        question=payload.question,
        answer=answer_result["answer"],
        language=lang,
        is_supported=answer_result["is_supported"],
        source_pages=answer_result["source_pages"],
        excerpts=answer_result["excerpts"]
    )

    formatted_excerpts = [
        SourceExcerpt(page=e["page"], text=e["text"], score=e.get("score", 0.0))
        for e in answer_result["excerpts"]
    ]

    return AskQuestionResponse(
        conversation_id=conversation_id,
        document_id=document_id,
        question=payload.question,
        answer=answer_result["answer"],
        language=lang,
        is_supported=answer_result["is_supported"],
        source_pages=answer_result["source_pages"],
        excerpts=formatted_excerpts,
        created_at=saved_chat.created_at
    )

@router.get("/api/documents/{document_id}/history", response_model=ChatHistoryResponse)
def get_document_history(
    document_id: str,
    conversation_id: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """Retrieve chat history for a document."""
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")

    return HistoryService.get_document_history(db, document_id, conversation_id)

@router.delete("/api/history/{conversation_id}")
def delete_conversation(conversation_id: str, db: Session = Depends(get_db)):
    """Delete a conversation session."""
    deleted = HistoryService.delete_conversation(db, conversation_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    return {"message": f"Conversation {conversation_id} was deleted successfully."}

@router.get("/api/conversations/recent", response_model=List[ConversationSummary])
def get_recent_conversations(db: Session = Depends(get_db)):
    """Retrieve recent conversation threads for the dashboard."""
    return HistoryService.get_recent_conversations(db, limit=10)
