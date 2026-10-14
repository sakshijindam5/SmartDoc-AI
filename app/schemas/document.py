from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, ConfigDict

class DocumentBase(BaseModel):
    filename: str
    file_size_bytes: int
    page_count: int
    is_scanned: bool
    status: str
    total_chunks: int

class DocumentResponse(DocumentBase):
    id: str
    created_at: datetime
    updated_at: datetime
    error_message: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

class DocumentListResponse(BaseModel):
    total: int
    documents: List[DocumentResponse]

class DocumentPreviewPage(BaseModel):
    page_number: int
    text_preview: str

class DocumentDetailResponse(DocumentResponse):
    preview_pages: Optional[List[DocumentPreviewPage]] = None
