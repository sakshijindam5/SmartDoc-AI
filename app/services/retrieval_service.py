import os
import json
import logging
import numpy as np
from typing import List, Dict, Any, Optional
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from app.config import settings

logger = logging.getLogger(__name__)

# Lazy singleton for SentenceTransformer
_embedding_model = None

def get_embedding_model():
    global _embedding_model
    if _embedding_model is None:
        try:
            from sentence_transformers import SentenceTransformer
            logger.info(f"Loading SentenceTransformer model: {settings.EMBEDDING_MODEL_NAME}")
            _embedding_model = SentenceTransformer(settings.EMBEDDING_MODEL_NAME)
        except Exception as e:
            logger.warning(f"Could not load SentenceTransformer ({str(e)}). TF-IDF keyword retrieval will be used.")
            _embedding_model = None
    return _embedding_model

class RetrievalService:
    @staticmethod
    def get_index_path(document_id: str) -> str:
        return os.path.join(settings.VECTOR_STORE_DIR, f"{document_id}.json")

    @staticmethod
    def get_embeddings_path(document_id: str) -> str:
        return os.path.join(settings.VECTOR_STORE_DIR, f"{document_id}_embeddings.npy")

    @classmethod
    def index_document(cls, document_id: str, chunks: List[Dict[str, Any]]) -> bool:
        """
        Indexes document chunks:
        1. Saves chunk texts and page metadata.
        2. Generates semantic embeddings with SentenceTransformer.
        3. Saves embeddings to disk.
        """
        if not chunks:
            return False

        try:
            texts = [c["text"] for c in chunks]
            model = get_embedding_model()

            if model is not None:
                embeddings = model.encode(texts, convert_to_numpy=True, normalize_embeddings=True)
                np.save(cls.get_embeddings_path(document_id), embeddings)
            else:
                embeddings = None

            # Save chunks metadata
            index_data = {
                "document_id": document_id,
                "total_chunks": len(chunks),
                "chunks": chunks,
                "has_embeddings": embeddings is not None
            }

            with open(cls.get_index_path(document_id), "w", encoding="utf-8") as f:
                json.dump(index_data, f, ensure_ascii=False, indent=2)

            return True
        except Exception as e:
            logger.error(f"Error indexing document {document_id}: {str(e)}")
            return False

    @classmethod
    def delete_index(cls, document_id: str):
        """Deletes vector index and stored metadata for document."""
        for path in [cls.get_index_path(document_id), cls.get_embeddings_path(document_id)]:
            if os.path.exists(path):
                try:
                    os.remove(path)
                except Exception as e:
                    logger.warning(f"Could not delete index file {path}: {str(e)}")

    @classmethod
    def search(
        cls,
        document_id: str,
        query: str,
        top_k: int = None,
        threshold: float = None
    ) -> List[Dict[str, Any]]:
        """
        Performs hybrid semantic + keyword retrieval on the specific document.
        Returns top chunks meeting the relevance threshold with page numbers.
        """
        if top_k is None:
            top_k = settings.TOP_K_CHUNKS
        if threshold is None:
            threshold = settings.SIMILARITY_THRESHOLD

        index_file = cls.get_index_path(document_id)
        if not os.path.exists(index_file):
            logger.warning(f"Index file not found for document {document_id}")
            return []

        try:
            with open(index_file, "r", encoding="utf-8") as f:
                index_data = json.load(f)

            chunks = index_data.get("chunks", [])
            if not chunks:
                return []

            texts = [c["text"] for c in chunks]
            num_chunks = len(chunks)

            # 1. Semantic Scores (Cosine similarity with SentenceTransformer)
            semantic_scores = np.zeros(num_chunks)
            emb_path = cls.get_embeddings_path(document_id)
            model = get_embedding_model()

            if model is not None and os.path.exists(emb_path):
                try:
                    doc_embeddings = np.load(emb_path)
                    query_embedding = model.encode([query], convert_to_numpy=True, normalize_embeddings=True)
                    # Dot product between normalized vectors is cosine similarity
                    semantic_scores = np.dot(doc_embeddings, query_embedding.T).flatten()
                except Exception as e:
                    logger.warning(f"Semantic scoring error: {e}")

            # 2. Keyword Scores (TF-IDF Cosine similarity as fallback/hybrid)
            keyword_scores = np.zeros(num_chunks)
            try:
                # Add query to corpus for vectorization
                tfidf = TfidfVectorizer(ngram_range=(1, 2), stop_words="english")
                tfidf_matrix = tfidf.fit_transform(texts + [query])
                chunk_tfidf = tfidf_matrix[:-1]
                query_tfidf = tfidf_matrix[-1:]
                kw_sim = cosine_similarity(chunk_tfidf, query_tfidf).flatten()
                keyword_scores = kw_sim
            except Exception as e:
                logger.debug(f"TF-IDF scoring note: {e}")

            # 3. Hybrid Combination Score
            # Use maximum between semantic and combined to never penalize strong semantic matches
            if np.any(semantic_scores > 0):
                final_scores = np.maximum(semantic_scores, (0.60 * semantic_scores) + (0.40 * keyword_scores))
            else:
                final_scores = keyword_scores

            # Downrank boilerplate credit tables when user asks for syllabus, lab or course content
            q_lower = query.lower()
            is_content_query = any(w in q_lower for w in ["syllabus", "curriculum", "experiment", "experiments", "lab", "practicals", "practical", "topics", "unit", "units", "course"])
            is_credit_query = any(w in q_lower for w in ["credit", "credits", "evaluation", "scheme", "marks", "teaching hrs", "hours", "exam"])
            if is_content_query and not is_credit_query:
                for idx, c in enumerate(chunks):
                    c_low = c["text"].lower()
                    if any(tab in c_low for tab in ["weakly teaching", "evaluation scheme", "ca mse ese", "semester-i credits", "semester-ii credits", "total semester-"]):
                        final_scores[idx] *= 0.30

            # Filter by relevance threshold and rank
            ranked_indices = np.argsort(final_scores)[::-1]
            results = []

            for idx in ranked_indices:
                score = float(final_scores[idx])
                if score >= threshold:
                    chunk = chunks[idx]
                    results.append({
                        "chunk_id": chunk.get("chunk_id", idx),
                        "page_number": chunk["page_number"],
                        "text": chunk["text"],
                        "score": round(score, 4),
                        "semantic_score": round(float(semantic_scores[idx]), 4),
                        "keyword_score": round(float(keyword_scores[idx]), 4)
                    })
                if len(results) >= top_k:
                    break

            # If content/syllabus query, expand with sibling chunks from top matching pages for full outline
            if is_content_query and results:
                top_pages = set(r["page_number"] for r in results[:2])
                existing_cids = set(r["chunk_id"] for r in results)
                for idx, c in enumerate(chunks):
                    cid = c.get("chunk_id", idx)
                    if c["page_number"] in top_pages and cid not in existing_cids:
                        results.append({
                            "chunk_id": cid,
                            "page_number": c["page_number"],
                            "text": c["text"],
                            "score": round(float(final_scores[idx]), 4),
                            "semantic_score": round(float(semantic_scores[idx]), 4),
                            "keyword_score": round(float(keyword_scores[idx]), 4)
                        })

            # If no chunks met threshold but user asked for document summary/overview
            if len(results) == 0 and any(w in query.lower() for w in ["summary", "summarize", "overview", "about"]):
                for c in chunks[:top_k]:
                    results.append({
                        "chunk_id": c.get("chunk_id", 0),
                        "page_number": c["page_number"],
                        "text": c["text"],
                        "score": 0.25,
                        "semantic_score": 0.25,
                        "keyword_score": 0.25
                    })

            return results
        except Exception as e:
            logger.error(f"Search failed for doc {document_id}: {str(e)}")
            return []
