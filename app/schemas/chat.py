from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field

class SourceExcerpt(BaseModel):
    page: int
    text: str
    score: float

class AskQuestionRequest(BaseModel):
    question: str = Field(..., min_length=2, max_length=1000, description="Question about the document")
    language: str = Field(default="en", description="Preferred response language: 'en', 'hi', or 'mr'")
    conversation_id: Optional[str] = Field(default=None, description="Optional conversation UUID to chain chat")

class AskQuestionResponse(BaseModel):
    conversation_id: str
    document_id: str
    question: str
    answer: str
    language: str
    is_supported: bool
    source_pages: List[int]
    excerpts: List[SourceExcerpt]
    created_at: datetime

class ChatMessageResponse(BaseModel):
    id: str
    conversation_id: str
    question: str
    answer: str
    language: str
    is_supported: bool
    source_pages: List[int]
    excerpts: List[SourceExcerpt]
    created_at: datetime

class ChatHistoryResponse(BaseModel):
    document_id: str
    total_messages: int
    messages: List[ChatMessageResponse]

class ConversationSummary(BaseModel):
    conversation_id: str
    document_id: str
    document_name: str
    last_question: str
    message_count: int
    last_activity: datetime
