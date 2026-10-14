import os
import re
import uuid
import pymupdf
from typing import List, Dict, Any, Tuple
from app.config import settings

class PDFService:
    @staticmethod
    def sanitize_filename(filename: str) -> str:
        """Sanitizes user filename and generates a safe unique disk filename."""
        clean = re.sub(r'[^a-zA-Z0-9_\.-]', '_', filename)
        unique_id = uuid.uuid4().hex[:10]
        return f"{unique_id}_{clean}"

    @staticmethod
    def validate_file(filename: str, file_size_bytes: int) -> Tuple[bool, str]:
        """Validates file extension and size."""
        ext = os.path.splitext(filename)[1].lower()
        if ext not in settings.ALLOWED_EXTENSIONS:
            return False, f"Unsupported file type '{ext}'. Only PDF documents are allowed."
        
        max_bytes = settings.MAX_FILE_SIZE_MB * 1024 * 1024
        if file_size_bytes > max_bytes:
            return False, f"File size exceeds maximum allowed limit of {settings.MAX_FILE_SIZE_MB} MB."
            
        return True, ""

    @staticmethod
    def extract_text_and_pages(pdf_path: str) -> Dict[str, Any]:
        """
        Extracts text page by page from PDF using PyMuPDF.
        Preserves original 1-indexed page numbers.
        Detects scanned or image-only documents.
        """
        try:
            doc = pymupdf.open(pdf_path)
            total_pages = len(doc)
            
            if total_pages == 0:
                return {
                    "success": False,
                    "error": "The uploaded PDF document contains 0 pages.",
                    "pages": [],
                    "total_pages": 0,
                    "is_scanned": False
                }
            
            pages_data = []
            total_char_count = 0
            has_images = False
            
            for page_idx in range(total_pages):
                page_num = page_idx + 1
                page = doc[page_idx]
                text = page.get_text("text").strip()
                
                # Check for image presence on page
                images = page.get_images()
                if images and len(images) > 0:
                    has_images = True
                
                char_count = len(text)
                total_char_count += char_count
                
                pages_data.append({
                    "page_number": page_num,
                    "text": text,
                    "char_count": char_count
                })
            
            doc.close()
            
            # Scanned detection heuristic:
            # If total character count across all pages is under 30 characters (or average < 15 chars/page)
            # and contains images or zero text, it is likely a scanned document requiring OCR.
            is_scanned = False
            if total_char_count < 30 or (total_pages > 1 and (total_char_count / total_pages) < 15):
                is_scanned = True
                return {
                    "success": False,
                    "error": "Scanned or image-based PDF detected: No usable text could be extracted. The document requires an OCR (Optical Character Recognition) pipeline.",
                    "pages": pages_data,
                    "total_pages": total_pages,
                    "is_scanned": True,
                    "total_chars": total_char_count
                }
                
            return {
                "success": True,
                "error": None,
                "pages": pages_data,
                "total_pages": total_pages,
                "is_scanned": False,
                "total_chars": total_char_count
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to parse PDF document: {str(e)}",
                "pages": [],
                "total_pages": 0,
                "is_scanned": False
            }

    @staticmethod
    def chunk_document(pages_data: List[Dict[str, Any]], chunk_size: int = None, chunk_overlap: int = None) -> List[Dict[str, Any]]:
        """
        Splits extracted page text into overlapping chunks while retaining exact page metadata.
        Uses sentence-aware splitting where possible.
        """
        chunk_size = chunk_size or settings.CHUNK_SIZE
        chunk_overlap = chunk_overlap or settings.CHUNK_OVERLAP
        
        chunks = []
        chunk_index = 0
        
        for page in pages_data:
            page_num = page["page_number"]
            text = page["text"].strip()
            
            if not text:
                continue
                
            # Split text by paragraphs first
            paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
            
            current_chunk = ""
            
            for para in paragraphs:
                # If paragraph fits in current chunk
                if len(current_chunk) + len(para) + 1 <= chunk_size:
                    current_chunk = f"{current_chunk}\n\n{para}".strip()
                else:
                    if current_chunk:
                        chunks.append({
                            "chunk_id": chunk_index,
                            "page_number": page_num,
                            "text": current_chunk,
                            "char_count": len(current_chunk)
                        })
                        chunk_index += 1
                        
                        # Apply overlap by taking trailing part of previous chunk
                        overlap_text = current_chunk[-chunk_overlap:] if len(current_chunk) > chunk_overlap else ""
                        current_chunk = f"{overlap_text} {para}".strip() if overlap_text else para
                    else:
                        # Paragraph itself is larger than chunk_size, split by sentences or fixed window
                        sentences = re.split(r'(?<=[.!?])\s+', para)
                        sub_chunk = ""
                        for sent in sentences:
                            if len(sub_chunk) + len(sent) + 1 <= chunk_size:
                                sub_chunk = f"{sub_chunk} {sent}".strip()
                            else:
                                if sub_chunk:
                                    chunks.append({
                                        "chunk_id": chunk_index,
                                        "page_number": page_num,
                                        "text": sub_chunk,
                                        "char_count": len(sub_chunk)
                                    })
                                    chunk_index += 1
                                    overlap_sub = sub_chunk[-chunk_overlap:] if len(sub_chunk) > chunk_overlap else ""
                                    sub_chunk = f"{overlap_sub} {sent}".strip()
                                else:
                                    # Fallback for unbroken giant strings
                                    for start_idx in range(0, len(sent), chunk_size - chunk_overlap):
                                        slice_text = sent[start_idx:start_idx + chunk_size].strip()
                                        if slice_text:
                                            chunks.append({
                                                "chunk_id": chunk_index,
                                                "page_number": page_num,
                                                "text": slice_text,
                                                "char_count": len(slice_text)
                                            })
                                            chunk_index += 1
                                    sub_chunk = ""
                        if sub_chunk:
                            current_chunk = sub_chunk
            
            # Append remaining chunk for this page
            if current_chunk:
                chunks.append({
                    "chunk_id": chunk_index,
                    "page_number": page_num,
                    "text": current_chunk,
                    "char_count": len(current_chunk)
                })
                chunk_index += 1
                
        return chunks
