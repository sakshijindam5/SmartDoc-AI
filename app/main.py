import os
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from app.config import settings
from app.database import init_db, get_db
from app.api.documents import router as documents_router
from app.api.chat import router as chat_router
from app.api.health import router as health_router
from app.models.document import Document

BASE_DIR = Path(__file__).resolve().parent

from app.services.retrieval_service import get_embedding_model

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize Database tables
    init_db()
    # Pre-warm embedding model in RAM so user requests are instantaneous
    get_embedding_model()
    yield
    # Shutdown logic if any

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.PROJECT_VERSION,
    description="Intelligent Document Assistant using PDF processing, hybrid vector retrieval, and evidence-grounded QA.",
    lifespan=lifespan
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount Static Files
static_dir = BASE_DIR / "static"
os.makedirs(static_dir / "css", exist_ok=True)
os.makedirs(static_dir / "js", exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# Templates
templates_dir = BASE_DIR / "templates"
templates = Jinja2Templates(directory=str(templates_dir))

# Include API Routers
app.include_router(health_router)
app.include_router(documents_router)
app.include_router(chat_router)

# Frontend UI Routes
@app.get("/")
def dashboard_page(request: Request):
    """Renders the main dashboard page."""
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "title": "SmartDoc AI – Dashboard",
            "settings": settings
        }
    )

@app.get("/chat/{document_id}")
def chat_page(document_id: str, request: Request, db: Session = Depends(get_db)):
    """Renders the dedicated interactive document Q&A chat page."""
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")

    return templates.TemplateResponse(
        request=request,
        name="chat.html",
        context={
            "document": doc,
            "title": f"SmartDoc AI – Chat: {doc.filename}",
            "settings": settings
        }
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=settings.HOST, port=settings.PORT, reload=settings.DEBUG)
