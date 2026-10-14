import sys
import httpx

def test_live_api_endpoints():
    client = httpx.Client(base_url="http://127.0.0.1:8000", timeout=30.0)

    # 1. Health check
    health = client.get("/api/health").json()
    assert health["status"] == "healthy"
    assert health["database"] == "ok"

    # 2. List documents and select the 3-page benchmark mca_syllabus
    docs = client.get("/api/documents").json()
    doc_id = None
    for d in docs.get("documents", []):
        if d["filename"] == "mca_syllabus.pdf" and d.get("page_count") == 3:
            doc_id = d["id"]
            break
    if not doc_id:
        with open("tests/sample_docs/mca_syllabus.pdf", "rb") as f:
            up_res = client.post("/api/documents/upload", files={"file": ("mca_syllabus.pdf", f, "application/pdf")}).json()
            doc_id = up_res["id"]

    # 3. Ask known question
    q_known = "What is the randomized election timeout range in Raft consensus?"
    res_known = client.post(f"/api/documents/{doc_id}/ask", json={"question": q_known, "language": "en"}).json()
    assert res_known["is_supported"] is True
    assert 1 in res_known["source_pages"]
    assert "150ms" in res_known["answer"] or "300ms" in res_known["answer"]

    # 4. Ask absent question (Strict anti-hallucination)
    q_absent = "What is the molecular formula of table salt and sugar?"
    res_absent = client.post(f"/api/documents/{doc_id}/ask", json={"question": q_absent, "language": "en"}).json()
    assert res_absent["is_supported"] is False
    assert res_absent["answer"] == "Answer not found in the uploaded document."
    assert res_absent["source_pages"] == []

    # 5. Multilingual question (Marathi)
    q_mr = "plagiarism percentage disqualified report IEEE"
    res_mr = client.post(f"/api/documents/{doc_id}/ask", json={"question": q_mr, "language": "mr"}).json()
    assert res_mr["is_supported"] is True
    assert 3 in res_mr["source_pages"]

    # 6. Chat History
    hist = client.get(f"/api/documents/{doc_id}/history").json()
    assert hist["total_messages"] >= 3

if __name__ == "__main__":
    test_live_api_endpoints()
    print("ALL LIVE ENDPOINTS AND RAG RETRIEVAL VERIFIED SUCCESSFULLY!")
