import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, Boolean, DateTime, Text, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base

class ChatHistory(Base):
    __tablename__ = "chat_history"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    document_id = Column(String(36), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    conversation_id = Column(String(36), nullable=False, index=True)
    question = Column(Text, nullable=False)
    answer = Column(Text, nullable=False)
    language = Column(String(10), default="en")  # "en", "hi", "mr"
    is_supported = Column(Boolean, default=True)  # False if "Answer not found in the uploaded document."
    source_pages = Column(Text, default="[]")  # JSON encoded list of page numbers
    excerpts = Column(Text, default="[]")  # JSON encoded list of excerpt objects
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    document = relationship("Document", back_populates="chat_histories")
