# SmartDoc AI – Intelligent Document Assistant

[![Python Version](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-green.svg)](https://fastapi.tiangolo.com/)
[![License](https://img.shields.io/badge/License-MIT-purple.svg)](LICENSE)
[![Status](https://img.shields.io/badge/Status-Complete%20%26%20Tested-brightgreen.svg)]()

> **SmartDoc AI**: Intelligent, evidence-grounded document question-answering assistant using FastAPI, PyMuPDF, Sentence Transformers, Hybrid Vector Retrieval, and strict Anti-Hallucination rules with exact page references.

---

## 🌟 Key Highlights & Innovations

1. **Strict Evidence-Grounded Guarantee**:
   Answers questions exclusively using retrieved document content. If an answer is not present in the document, the system refuses to hallucinate and responds with:
   ```text
   Answer not found in the uploaded document.
   ```
2. **Precise 1-Indexed Page Attribution**:
   Every response includes clickable source page citations (`Page 1`, `Page 3`) and expandable supporting excerpts with relevance scores.
3. **Hybrid Semantic & Keyword Retrieval**:
   Combines dense semantic vector embeddings (`all-MiniLM-L6-v2`) with sparse keyword matching (TF-IDF) using maximum-score combination to ensure zero penalties on specialized technical terminology.
4. **Local Extractive Fallback (Zero-Cost Operation)**:
   Does not depend on paid external APIs. Runs 100% locally using an extractive QA ranker. Optionally supports Google Gemini (`gemini-1.5-flash`), OpenAI (`gpt-4o-mini`), and Groq (`llama-3.1-8b-instant`).
5. **Multilingual Support (English, हिन्दी, मराठी)**:
   Users can submit questions and receive grounded answers in English, Hindi, and Marathi.
6. **Scanned PDF Detection**:
   Detects image-only/scanned PDFs lacking extractable text, notifying the user rather than silently producing empty search indexes.

---

## 🏗️ System Architecture

```mermaid
graph TD
    User([User / Browser]) -->|Upload PDF| FastAPI[FastAPI Backend /app/main.py]
    FastAPI --> PDFService[PDFService /app/services/pdf_service.py]
    PDFService -->|PyMuPDF Text & Page Extraction| Chunker[Boundary-Aware Chunker]
    Chunker --> Embedder[Sentence Transformers / all-MiniLM-L6-v2]
    Embedder --> VectorStore[(Vector Store /vector_store/)]
    
    User -->|Ask Question in EN/HI/MR| ChatRouter[Chat API /api/documents/{id}/ask]
    ChatRouter --> Retrieval[RetrievalService /app/services/retrieval_service.py]
    Retrieval -->|Cosine Similarity + TF-IDF| VectorStore
    Retrieval -->|Top Relevant Chunks & Pages| AnswerGen[AnswerService /app/services/answer_service.py]
    
    AnswerGen -->|If relevance < threshold| Refusal["Answer not found in the uploaded document."]
    AnswerGen -->|If evidence valid| LLMOrLocal{LLM Provider?}
    LLMOrLocal -->|extractive| ExtractiveRanker[Local Extractive QA Engine]
    LLMOrLocal -->|gemini/openai/groq| ExternalAPI[External Cloud LLM API]
    
    AnswerGen --> DB[(SQLite DB: smartdoc.db)]
    AnswerGen -->|Grounded Answer + Page Badges + Excerpts| User
```

---

## 📂 Project Structure

```text
documind-ai/
├── app/
│   ├── main.py                     # FastAPI application entrypoint & UI routes
│   ├── config.py                   # Centralized configuration & environment loader
│   ├── database.py                 # SQLite database connection & session maker
│   ├── models/
│   │   ├── document.py             # SQLAlchemy Document model
│   │   └── chat.py                 # SQLAlchemy ChatHistory model
│   ├── schemas/
│   │   ├── document.py             # Pydantic schemas for document operations
│   │   └── chat.py                 # Pydantic schemas for Q&A and history
│   ├── api/
│   │   ├── documents.py            # Upload, list, preview & delete endpoints
│   │   ├── chat.py                 # Q&A querying, history & conversation management
│   │   └── health.py               # Application health check endpoint
│   ├── services/
│   │   ├── pdf_service.py          # PyMuPDF extraction, validation, chunking
│   │   ├── retrieval_service.py    # Hybrid vector search (SentenceTransformer + TF-IDF)
│   │   ├── answer_service.py       # Grounded Q&A engine, prompt builder & local ranker
│   │   └── history_service.py      # SQLite Q&A persistence & conversation threads
│   ├── templates/
│   │   ├── index.html              # Modern responsive Dashboard UI
│   │   └── chat.html               # Interactive Document Q&A Studio UI
│   └── static/
│       ├── css/style.css           # Custom design system with rich aesthetics
│       └── js/
│           ├── app.js              # Dashboard client-side logic & dropzone
│           └── chat.js             # Real-time Q&A interface & language switcher
├── uploads/                        # Secure local storage for uploaded PDF files
├── vector_store/                   # Stored embeddings (.npy) and chunk indexes (.json)
├── tests/
│   ├── sample_docs/                # Sample academic PDFs for testing
│   │   ├── mca_syllabus.pdf        # 3-page MCA course syllabus with verified facts
│   │   └── scanned_mock.pdf        # Mock image-only document for OCR detection
│   ├── test_pdf.py                 # Unit tests for text extraction & chunking
│   ├── test_retrieval.py           # Unit tests for vector indexing & similarity
│   ├── test_qa.py                  # Unit tests for Q&A accuracy & anti-hallucination
│   ├── test_live_api.py            # End-to-end integration test against live server
│   ├── evaluation_dataset.json     # Benchmark queries (facts, multi-page, absent)
│   └── run_evaluation.py           # Benchmark evaluation execution script
├── .env.example                    # Template environment variables
├── .gitignore                      # Git ignore file
├── requirements.txt                # Production dependencies
├── render.yaml                     # Render cloud deployment configuration
└── README.md                       # Comprehensive project documentation
```

---

## 🚀 Quickstart Installation Guide

### Prerequisites
* Python 3.10+ (Tested on Python 3.11.9)
* Git

### 1. Clone & Navigate
```bash
git clone <repository-url>
cd documind-ai
```

### 2. Set Up Virtual Environment
```bash
# Windows
python -m venv venv
.\venv\Scripts\activate

# Linux / macOS
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Configure Environment
Copy the example environment file:
```bash
cp .env.example .env
```
Default `.env` settings are ready for 100% offline local operation (`LLM_PROVIDER=extractive`). If you have an external API key (e.g., Gemini or OpenAI), configure it in `.env`:
```env
LLM_PROVIDER=gemini
GEMINI_API_KEY=your_actual_gemini_api_key_here
```

### 5. Run Application
```bash
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

* **Web UI Dashboard:** [http://127.0.0.1:8000](http://127.0.0.1:8000)
* **Interactive Swagger API Docs:** [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
* **Health Check:** [http://127.0.0.1:8000/api/health](http://127.0.0.1:8000/api/health)

---

## 🧪 Testing and Accuracy Evaluation

### Running Automated Test Suite
Run the 14 automated unit tests:
```bash
python -m pytest -v tests/
```
Output:
```text
tests/test_pdf.py::test_validate_file_extension PASSED                   [  7%]
tests/test_pdf.py::test_extract_text_and_preserve_pages PASSED           [ 14%]
tests/test_pdf.py::test_detect_scanned_pdf PASSED                        [ 21%]
tests/test_pdf.py::test_chunking_retains_page_metadata PASSED            [ 28%]
tests/test_qa.py::test_direct_question_known_answer PASSED               [ 35%]
tests/test_qa.py::test_question_combining_multiple_pages PASSED          [ 42%]
tests/test_qa.py::test_paraphrased_question PASSED                       [ 50%]
tests/test_qa.py::test_question_absent_from_document_must_refuse PASSED  [ 57%]
tests/test_qa.py::test_multilingual_question_hindi PASSED                [ 64%]
tests/test_qa.py::test_multilingual_question_marathi PASSED              [ 71%]
tests/test_retrieval.py::test_semantic_retrieval_page1 PASSED            [ 78%]
tests/test_retrieval.py::test_semantic_retrieval_page2 PASSED            [ 85%]
tests/test_retrieval.py::test_semantic_retrieval_page3 PASSED            [ 92%]
tests/test_retrieval.py::test_completely_irrelevant_query_threshold PASSED [100%]
============================= 14 passed in 23.12s =============================
```

### Running Benchmark Evaluation Harness
Execute the evaluation dataset benchmark:
```bash
python tests/run_evaluation.py
```
Output:
```text
======================================================================
  SmartDoc AI: Retrieval & QA Pipeline Evaluation Benchmark
======================================================================
  Total Test Queries:           8
  In-Document Queries:          6
  Out-of-Document Queries:      2
  Page Retrieval Recall:        100.0%
  Strict Anti-Hallucination:    100.0% (Refused all absent queries)
  Overall QA Accuracy:          100.0%
======================================================================
```

---

## 📡 Backend API Reference

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/documents/upload` | Upload and process PDF, extract pages, build vector index |
| `GET` | `/api/documents` | List all uploaded documents with status and metadata |
| `GET` | `/api/documents/{id}` | Retrieve document details and first 3 page text previews |
| `DELETE` | `/api/documents/{id}` | Delete document, physical file, vector index, and chat history |
| `GET` | `/api/documents/{id}/file` | Serve original PDF file for browser preview |
| `POST` | `/api/documents/{id}/ask` | Submit question with language selector (`en`, `hi`, `mr`) |
| `GET` | `/api/documents/{id}/history` | Retrieve conversation history for document |
| `DELETE` | `/api/history/{conv_id}` | Delete conversation session |
| `GET` | `/api/conversations/recent` | Get list of recent conversation threads |
| `GET` | `/api/health` | Application status, database connectivity & model status |

---

## ☁️ Deployment Configuration (Render)

This repository includes a production-ready `render.yaml` specification:

1. Connect your GitHub repository to [Render.com](https://render.com).
2. Choose **Blueprint** deployment.
3. Configure persistent disk:
   - **Mount Path**: `/opt/render/project/src/data`
   - **Size**: 5 GB (preserves uploaded PDFs, vector indexes, and SQLite database across restarts).
4. Start Command:
   ```bash
   uvicorn app.main:app --host 0.0.0.0 --port $PORT
   ```

---

## 🎓 Demonstration Guide

When presenting SmartDoc AI, follow this 4-step demonstration flow:

1. **Step 1: Document Ingestion & Scanned PDF Guardrail**
   - Upload `tests/sample_docs/mca_syllabus.pdf`. Point out the instantaneous text extraction and chunk calculation.
   - (Optional) Try uploading `tests/sample_docs/scanned_mock.pdf` to demonstrate the intelligent OCR-needed guardrail preventing blank ingestion.
2. **Step 2: Fact Verification with Page Citations**
   - Ask: *"What is the election timeout range in Raft?"*
   - Show the answer (`150ms and 300ms`), point to the **`Page 1`** badge, and expand the **Supporting Excerpts** showing the exact source sentence and relevance score.
3. **Step 3: Multi-Page Information Synthesis**
   - Ask: *"What consensus algorithm is used and how many marks are allocated for viva voce?"*
   - Demonstrate that SmartDoc AI retrieves evidence across both **Page 1** and **Page 3** and links them into a unified response.
4. **Step 4: Strict Anti-Hallucination & Refusal Test**
   - Ask: *"What is the boiling point of liquid nitrogen at sea level?"*
   - Highlight the refusal:
     > `"Answer not found in the uploaded document."`
   - Emphasize that unlike generic chatbots, SmartDoc AI eliminates hallucinations and is engineered for academic and enterprise accuracy.
5. **Step 5: Multilingual Support**
   - Switch language pill to **हिन्दी** or **मराठी** and demonstrate responses grounded in the source text.
