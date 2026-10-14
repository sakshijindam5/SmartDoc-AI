import json
import uuid
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import desc
from app.models.chat import ChatHistory
from app.models.document import Document
from app.schemas.chat import (
    ChatMessageResponse,
    ChatHistoryResponse,
    ConversationSummary,
    SourceExcerpt
)

class HistoryService:
    @staticmethod
    def save_message(
        db: Session,
        document_id: str,
        conversation_id: str,
        question: str,
        answer: str,
        language: str,
        is_supported: bool,
        source_pages: List[int],
        excerpts: List[Dict[str, Any]]
    ) -> ChatHistory:
        """Saves a Q&A interaction to SQLite."""
        chat_item = ChatHistory(
            id=str(uuid.uuid4()),
            document_id=document_id,
            conversation_id=conversation_id,
            question=question,
            answer=answer,
            language=language,
            is_supported=is_supported,
            source_pages=json.dumps(source_pages),
            excerpts=json.dumps(excerpts)
        )
        db.add(chat_item)
        db.commit()
        db.refresh(chat_item)
        return chat_item

    @staticmethod
    def get_document_history(db: Session, document_id: str, conversation_id: Optional[str] = None) -> ChatHistoryResponse:
        """Retrieves history for a document, optionally filtered by conversation_id."""
        query = db.query(ChatHistory).filter(ChatHistory.document_id == document_id)
        if conversation_id:
            query = query.filter(ChatHistory.conversation_id == conversation_id)
        
        records = query.order_by(ChatHistory.created_at.asc()).all()

        messages = []
        for r in records:
            try:
                pages = json.loads(r.source_pages) if r.source_pages else []
            except Exception:
                pages = []
            try:
                raw_excerpts = json.loads(r.excerpts) if r.excerpts else []
                excerpts = [
                    SourceExcerpt(page=e["page"], text=e["text"], score=e.get("score", 0.0))
                    for e in raw_excerpts
                ]
            except Exception:
                excerpts = []

            messages.append(ChatMessageResponse(
                id=r.id,
                conversation_id=r.conversation_id,
                question=r.question,
                answer=r.answer,
                language=r.language,
                is_supported=r.is_supported,
                source_pages=pages,
                excerpts=excerpts,
                created_at=r.created_at
            ))

        return ChatHistoryResponse(
            document_id=document_id,
            total_messages=len(messages),
            messages=messages
        )

    @staticmethod
    def delete_conversation(db: Session, conversation_id: str) -> bool:
        """Deletes all messages associated with a conversation ID."""
        deleted_count = db.query(ChatHistory).filter(ChatHistory.conversation_id == conversation_id).delete()
        db.commit()
        return deleted_count > 0

    @staticmethod
    def get_recent_conversations(db: Session, limit: int = 10) -> List[ConversationSummary]:
        """Returns distinct active conversations with document details."""
        records = (
            db.query(ChatHistory)
            .join(Document, ChatHistory.document_id == Document.id)
            .order_by(desc(ChatHistory.created_at))
            .all()
        )

        seen_conversations = {}
        for r in records:
            cid = r.conversation_id
            if cid not in seen_conversations:
                seen_conversations[cid] = {
                    "conversation_id": cid,
                    "document_id": r.document_id,
                    "document_name": r.document.filename if r.document else "Unknown Document",
                    "last_question": r.question,
                    "message_count": 1,
                    "last_activity": r.created_at
                }
            else:
                seen_conversations[cid]["message_count"] += 1

            if len(seen_conversations) >= limit:
                break

        return [ConversationSummary(**item) for item in seen_conversations.values()]
