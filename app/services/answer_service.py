import re
import logging
import httpx
from typing import List, Dict, Any, Tuple, Optional
from app.config import settings

logger = logging.getLogger(__name__)

NOT_FOUND_RESPONSE = "Answer not found in the uploaded document."

class AnswerService:
    @classmethod
    def generate_answer(
        cls,
        question: str,
        retrieved_chunks: List[Dict[str, Any]],
        language: str = "en"
    ) -> Dict[str, Any]:
        """
        Generates a clean, simple, and evidence-grounded answer.
        Returns:
            {
                "answer": str,
                "is_supported": bool,
                "source_pages": List[int],
                "excerpts": List[Dict[str, Any]]
            }
        """
        # 1. Handle conversational greetings simply and warmly
        clean_q = re.sub(r'[^a-zA-Z\s]', '', question).strip().lower()
        greetings = {
            "hi", "hello", "hey", "namaste", "good morning", "good evening",
            "good afternoon", "who are you", "what are you", "what can you do", "help"
        }
        if clean_q in greetings or clean_q.startswith("hi ") or clean_q.startswith("hello "):
            if language == "hi":
                greeting_ans = "नमस्ते! मैं **SmartDoc AI** हूँ। मैं आपके अपलोड किए गए दस्तावेज़ से जुड़े सभी प्रश्नों के आसान और सटीक उत्तर देने के लिए तैयार हूँ। आप कोई भी प्रश्न पूछ सकते हैं!"
            elif language == "mr":
                greeting_ans = "नमस्कार! मी **SmartDoc AI** आहे. मी या दस्तऐवजातील सर्व माहितीच्या आधारे सोपी आणि अचूक उत्तरे देण्यास तयार आहे. आपण कोणताही प्रश्न विचारू शकता!"
            else:
                greeting_ans = "Hello! I'm **SmartDoc AI**. I'm ready to answer any questions about your uploaded document simply and accurately with exact page references. What would you like to know?"
            return {
                "answer": greeting_ans,
                "is_supported": True,
                "source_pages": [],
                "excerpts": []
            }

        # 2. Strict Grounding: If no chunks retrieved above relevance threshold, refuse
        if not retrieved_chunks:
            return {
                "answer": NOT_FOUND_RESPONSE,
                "is_supported": False,
                "source_pages": [],
                "excerpts": []
            }

        source_pages = sorted(list(set(chunk["page_number"] for chunk in retrieved_chunks)))
        
        # Prepare excerpts
        excerpts = []
        for chunk in retrieved_chunks:
            snippet = chunk["text"].strip()
            if len(snippet) > 260:
                snippet = snippet[:260].rsplit(" ", 1)[0] + "..."
            excerpts.append({
                "page": chunk["page_number"],
                "text": snippet,
                "score": chunk.get("score", 0.0)
            })

        # 3. External LLM Provider if configured
        provider = settings.LLM_PROVIDER.lower()
        llm_answer = None

        if provider == "gemini" and settings.GEMINI_API_KEY:
            llm_answer = cls._call_gemini(question, retrieved_chunks, language)
        elif provider == "openai" and settings.OPENAI_API_KEY:
            llm_answer = cls._call_openai(question, retrieved_chunks, language)
        elif provider == "groq" and settings.GROQ_API_KEY:
            llm_answer = cls._call_groq(question, retrieved_chunks, language)

        if llm_answer is not None:
            clean_ans = llm_answer.strip()
            if NOT_FOUND_RESPONSE.lower() in clean_ans.lower() or "not found in the uploaded document" in clean_ans.lower():
                return {
                    "answer": NOT_FOUND_RESPONSE,
                    "is_supported": False,
                    "source_pages": [],
                    "excerpts": []
                }
            return {
                "answer": clean_ans,
                "is_supported": True,
                "source_pages": source_pages,
                "excerpts": excerpts
            }

        # 4. Enhanced Simple & Natural Extractive Fallback
        return cls._simple_extractive_answer(question, retrieved_chunks, language, source_pages, excerpts)

    @classmethod
    def _simple_extractive_answer(
        cls,
        question: str,
        retrieved_chunks: List[Dict[str, Any]],
        language: str,
        source_pages: List[int],
        excerpts: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Extracts and formats information into clean, readable, simple answers with bullets.
        """
        q_lower = question.lower()
        full_context = "\n".join([c["text"] for c in retrieved_chunks])
        top_page = source_pages[0] if source_pages else 1

        # A. Identity / Name Query
        if any(w in q_lower for w in ["name", "who is", "candidate", "author", "person"]):
            first_chunk_text = retrieved_chunks[0]["text"]
            lines = [line.strip() for line in first_chunk_text.split("\n") if line.strip()]
            name_candidate = lines[0] if lines else "Document Subject"
            
            # Clean name candidate if too long
            if len(name_candidate) > 45:
                name_candidate = name_candidate.split(",")[0].split("-")[0].strip()

            contact_snippet = ""
            for l in lines[1:4]:
                if "@" in l or "+" in l or "solapur" in l.lower() or "mumbai" in l.lower() or "pune" in l.lower():
                    contact_snippet = l
                    break

            if language == "hi":
                answer = f"**नाम:** {name_candidate}"
                if contact_snippet:
                    answer += f"\n**संपर्क:** {contact_snippet}"
            elif language == "mr":
                answer = f"**नाव:** {name_candidate}"
                if contact_snippet:
                    answer += f"\n**संपर्क:** {contact_snippet}"
            else:
                answer = f"**Name:** {name_candidate}"
                if contact_snippet:
                    answer += f"\n**Contact / Location:** {contact_snippet}"

            return {
                "answer": answer,
                "is_supported": True,
                "source_pages": [top_page],
                "excerpts": excerpts
            }

        # B. Document Summary / Overview Query
        if any(w in q_lower for w in ["summary", "summarize", "overview", "what is this document", "about this document"]):
            summary_sentences = []
            for chunk in retrieved_chunks:
                for line in chunk["text"].split("\n"):
                    l_clean = line.strip("• -*")
                    if len(l_clean) > 35 and not any(l_clean.lower().startswith(x) for x in ["http", "www", "email", "phone"]):
                        if l_clean not in summary_sentences:
                            summary_sentences.append(l_clean)
            if summary_sentences:
                bullets = "\n".join([f"• {s}" for s in summary_sentences[:3]])
                return {
                    "answer": f"**Document Overview & Summary (Page {top_page}):**\n{bullets}",
                    "is_supported": True,
                    "source_pages": [top_page],
                    "excerpts": excerpts
                }
        # B2. Syllabus / Course Outline / Lab Experiments Query
        syllabus_keywords = [
            "syllabus", "curriculum", "experiment", "experiments", "lab", "practicals",
            "practical", "course topic", "course topics", "course content", "course outline",
            "unit", "units", "what is taught in", "topics in", "course"
        ]
        if any(w in q_lower for w in syllabus_keywords):
            stop_subject = {
                "provide", "the", "a", "an", "what", "is", "give", "show", "tell", "me", "syllabus",
                "curriculum", "lab", "practical", "practicals", "experiment", "experiments", "of", "in",
                "for", "course", "topics", "topic", "units", "unit", "details", "all", "program", "please", "about"
            }
            subject_tokens = [w for w in re.findall(r'\b[a-zA-Z\d\+#]+\b', q_lower) if w not in stop_subject and len(w) > 1]

            def is_credit_table(txt: str) -> bool:
                t = txt.lower()
                indicators = ["weakly teaching", "evaluation scheme", "ca mse ese", "semester-i credits", "semester-ii credits", "total semester"]
                return any(ind in t for ind in indicators)

            # Filter candidate chunks
            candidate_chunks = [c for c in retrieved_chunks if not is_credit_table(c["text"])]
            if subject_tokens:
                matched_pages = set()
                for c in candidate_chunks:
                    if any(t in c["text"].lower() for t in subject_tokens):
                        matched_pages.add(c["page_number"])
                if matched_pages:
                    candidate_chunks = [c for c in candidate_chunks if c["page_number"] in matched_pages]

            # Sort chunks in original document reading order
            candidate_chunks.sort(key=lambda c: c.get("chunk_id", 0))

            # Group chunks by page number
            pages_map = {}
            for c in candidate_chunks:
                pages_map.setdefault(c["page_number"], []).append(c["text"])

            syllabus_blocks = []

            for p_num, texts in pages_map.items():
                full_page = "\n".join(texts)
                sub_text = full_page

                # Handle multi-lab page splitting (e.g., Python Lab vs DBMS Lab on Page 21)
                if "python" in q_lower and "b) dbms" in sub_text.lower():
                    sub_text = re.split(r'b\)\s*dbms', sub_text, flags=re.I)[0]
                elif "dbms" in q_lower and "b) dbms" in sub_text.lower():
                    sub_text = re.split(r'b\)\s*dbms', sub_text, flags=re.I)[1]

                # Extract Course Code and Title (e.g., MCAL107: Practical II (Python Lab...))
                title_m = re.search(r'(MCA[CL]\d+[:\s][^\n\r]+)', sub_text, re.I)
                course_title = title_m.group(1).strip() if title_m else ""
                course_title = re.sub(r'Dr\.\s*BaBasaheB.*?lonere', '', course_title, flags=re.I).strip()
                course_title = re.sub(r'\d+\s*\|\s*P\s*a\s*g\s*e', '', course_title, flags=re.I).strip()
                if not course_title:
                    alt_m = re.search(r'([A-Z]\)\s*[A-Za-z\s]+(?:Lab|Course|Programming))', sub_text, re.I)
                    if alt_m:
                        course_title = alt_m.group(1).strip()

                is_title_match = any(t in course_title.lower() for t in subject_tokens) if subject_tokens else True
                priority = 2 if is_title_match else 1

                # 1. Numbered Experiments Search
                items_dict = {}
                matches = re.finditer(r'(?:^|\s)(\d{1,2})\s*[\.\)]\s*(.*?)(?=(?:\s\d{1,2}\s*[\.\)]|\Z))', sub_text, re.DOTALL)
                for m in matches:
                    num = int(m.group(1))
                    content = m.group(2).strip()
                    clean = " ".join(content.split())
                    clean = re.sub(r'Dr\.\s*BaBasaheB.*?lonere', '', clean, flags=re.I).strip()
                    clean = re.sub(r'\d+\s*\|\s*P\s*a\s*g\s*e', '', clean, flags=re.I).strip()
                    clean = re.sub(r'MCA[CL]\d+:.*', '', clean, flags=re.I).strip()
                    if "text book" in clean.lower() or "reference book" in clean.lower():
                        continue
                    if len(clean) > 8:
                        if num not in items_dict or len(clean) > len(items_dict[num]):
                            items_dict[num] = clean

                if len(items_dict) >= 3:
                    res_lines = []
                    header = f"**{course_title} (Page {p_num}):**" if course_title else f"**List of Experiments (Page {p_num}):**"
                    res_lines.append(header)
                    for n in sorted(items_dict.keys()):
                        res_lines.append(f"{n}. {items_dict[n]}")
                    syllabus_blocks.append((priority, p_num, "\n".join(res_lines)))
                    continue

                # 2. Theory Course Units (Unit 1, Unit 2, ...)
                unit_matches = re.finditer(r'\[?Unit\s*(\d+)\]?[:\s]*([^\n\[]+(?:\n[^\n\[]+)*)', sub_text, re.I)
                units_found = []
                for um in unit_matches:
                    u_num = um.group(1)
                    u_content = " ".join(um.group(2).split())
                    u_content = re.sub(r'\[\d+\s*Hours\]', '', u_content, flags=re.I).strip()
                    u_content = re.sub(r'Dr\.\s*BaBasaheB.*?lonere', '', u_content, flags=re.I).strip()
                    u_content = re.sub(r'\d+\s*\|\s*P\s*a\s*g\s*e', '', u_content, flags=re.I).strip()
                    if "text book" in u_content.lower():
                        u_content = re.split(r'text\s*book', u_content, flags=re.I)[0].strip()
                    if len(u_content) > 15:
                        units_found.append(f"• **Unit {u_num}:** {u_content}")

                if len(units_found) >= 2:
                    res_lines = []
                    header = f"**{course_title} (Page {p_num}):**" if course_title else f"**Course Units (Page {p_num}):**"
                    res_lines.append(header)
                    res_lines.extend(units_found)
                    syllabus_blocks.append((priority, p_num, "\n".join(res_lines)))

            if syllabus_blocks:
                title_matches = [b for b in syllabus_blocks if b[0] == 2]
                chosen_blocks = title_matches if title_matches else syllabus_blocks
                top_blocks = chosen_blocks[:2]
                final_ans = "\n\n".join(b[2] for b in top_blocks)
                pages_cited = [b[1] for b in top_blocks]
                return {
                    "answer": final_ans,
                    "is_supported": True,
                    "source_pages": pages_cited,
                    "excerpts": excerpts
                }

        # B3. Technical Skills Query
        if any(w in q_lower for w in ["skill", "tech", "programming", "languages", "tools", "database", "stack"]):
            # Look for skills block in text
            skills_found = []
            for chunk in retrieved_chunks:
                text = chunk["text"]
                for line in text.split("\n"):
                    l_clean = line.strip("• -*")
                    if any(term in l_clean.lower() for term in ["php", "python", "mysql", "javascript", "html", "css", "c,", "sql", "bootstrap", "power bi", "rest api", "git", "postman", "react", "node"]):
                        if len(l_clean) < 120 and l_clean not in skills_found:
                            skills_found.append(l_clean)

            if skills_found:
                bullets = "\n".join([f"• {s}" for s in skills_found[:6]])
                if language == "hi":
                    answer = f"**तकनीकी कौशल (Technical Skills):**\n{bullets}"
                elif language == "mr":
                    answer = f"**तांत्रिक कौशल्ये (Technical Skills):**\n{bullets}"
                else:
                    answer = f"**Technical Skills & Tools:**\n{bullets}"

                return {
                    "answer": answer,
                    "is_supported": True,
                    "source_pages": source_pages,
                    "excerpts": excerpts
                }

        # C. Contact / Email / Phone Query
        if any(w in q_lower for w in ["contact", "email", "phone", "mobile", "number", "address", "location"]):
            email_match = re.search(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', full_context)
            phone_match = re.search(r'(\+?\d{1,3}[-.\s]?)?\(?\d{3,5}\)?[-.\s]?\d{3,5}[-.\s]?\d{3,5}', full_context)
            
            items = []
            if email_match:
                items.append(f"• **Email:** {email_match.group(0)}")
            if phone_match:
                items.append(f"• **Phone:** {phone_match.group(0)}")
            
            if items:
                answer = "**Contact Details:**\n" + "\n".join(items)
                return {
                    "answer": answer,
                    "is_supported": True,
                    "source_pages": [top_page],
                    "excerpts": excerpts
                }

        # D. Education Query
        if any(w in q_lower for w in ["education", "degree", "college", "school", "bca", "mca", "cgpa", "qualification"]):
            edu_lines = []
            for chunk in retrieved_chunks:
                for line in chunk["text"].split("\n"):
                    l_strip = line.strip("• -*")
                    if any(kw in l_strip.lower() for kw in ["bca", "mca", "b.tech", "college", "school", "cgpa", "percentage", "hsc", "ssc"]):
                        if len(l_strip) < 100 and l_strip not in edu_lines:
                            edu_lines.append(f"• {l_strip}")

            if edu_lines:
                answer = "**Education Details:**\n" + "\n".join(edu_lines[:4])
                return {
                    "answer": answer,
                    "is_supported": True,
                    "source_pages": source_pages,
                    "excerpts": excerpts
                }

        # E. Experience / Projects Query
        if any(w in q_lower for w in ["experience", "work", "job", "company", "project"]):
            exp_lines = []
            for chunk in retrieved_chunks:
                for line in chunk["text"].split("\n"):
                    l_strip = line.strip("• -*")
                    if any(kw in l_strip.lower() for kw in ["developer", "solutions", "worked", "built", "developed", "experience", "pvt", "ltd"]):
                        if len(l_strip) > 15 and len(l_strip) < 160 and l_strip not in exp_lines:
                            exp_lines.append(f"• {l_strip}")

            if exp_lines:
                title = "**Work Experience & Key Highlights:**" if "experience" in q_lower else "**Projects & Work Highlights:**"
                answer = f"{title}\n" + "\n".join(exp_lines[:4])
                return {
                    "answer": answer,
                    "is_supported": True,
                    "source_pages": source_pages,
                    "excerpts": excerpts
                }

        # F. General / Academic Document Q&A (Sentence Selection & Formatting)
        stop_words = {
            "what", "is", "the", "are", "a", "an", "in", "on", "of", "for", "to", "and",
            "how", "why", "when", "where", "who", "which", "does", "do", "explain", "describe",
            "tell", "me", "about", "can", "you", "give", "definition", "list", "show", "document"
        }
        q_tokens = [w for w in re.findall(r'\b\w+\b', q_lower) if w not in stop_words]

        def is_table_junk(s_text: str) -> bool:
            s_low = s_text.lower()
            indicators = [
                "weakly teaching", "evaluation scheme", "ca mse ese",
                "semester-i credits", "semester-ii credits", "total semester",
                "master of computer application", "i year programme", "audit",
                "l t p ca"
            ]
            return any(ind in s_low for ind in indicators) or len(s_text) > 400

        scored_sentences = []
        for chunk in retrieved_chunks:
            p_num = chunk["page_number"]
            # Split clean sentences on punctuation or line breaks
            raw_sents = [s.strip() for s in re.split(r'(?<=[.!?])\s+|\n+', chunk["text"]) if s.strip()]
            for s in raw_sents:
                if len(s) < 15 or is_table_junk(s):
                    continue
                s_lower = s.lower()
                matches = sum(1 for t in q_tokens if t in s_lower)
                overlap = matches / len(q_tokens) if q_tokens else 0.5
                score = (chunk.get("score", 0.5) * 0.5) + (overlap * 0.5)

                if matches > 0 or chunk.get("score", 0) >= 0.16:
                    scored_sentences.append({
                        "text": s,
                        "page": p_num,
                        "score": score
                    })

        if not scored_sentences:
            return {
                "answer": NOT_FOUND_RESPONSE,
                "is_supported": False,
                "source_pages": [],
                "excerpts": []
            }

        # Sort and pick top 2 most distinct sentences
        scored_sentences.sort(key=lambda x: x["score"], reverse=True)
        chosen = []
        chosen_pages = set()
        seen = set()

        for item in scored_sentences:
            prefix = item["text"][:35].lower()
            if prefix not in seen:
                seen.add(prefix)
                chosen.append(item["text"])
                chosen_pages.add(item["page"])
            if len(chosen) >= 2:
                break

        pages_str = ", ".join(f"Page {p}" for p in sorted(list(chosen_pages)))
        content = " ".join(chosen)

        if language == "hi":
            answer = f"दस्तावेजातील माहितीनुसार ({pages_str}):\n{content}"
        elif language == "mr":
            answer = f"दस्तऐवजातील पुराव्यानुसार ({pages_str}):\n{content}"
        else:
            answer = f"Based on the uploaded document ({pages_str}):\n{content}"

        return {
            "answer": answer,
            "is_supported": True,
            "source_pages": sorted(list(chosen_pages)),
            "excerpts": excerpts
        }

    @classmethod
    def _build_llm_prompt(cls, question: str, retrieved_chunks: List[Dict[str, Any]], language: str) -> Tuple[str, str]:
        context_blocks = [f"[Page {c['page_number']}]: {c['text']}" for c in retrieved_chunks]
        context_str = "\n\n".join(context_blocks)

        language_instruction = {
            "en": "Respond in clear, simple, easy-to-read English.",
            "hi": "Respond in simple, clear Hindi (हिन्दी).",
            "mr": "Respond in simple, clear Marathi (मराठी)."
        }.get(language, "Respond in simple English.")

        system_prompt = (
            "You are SmartDoc AI, an intelligent and friendly document assistant.\n"
            "Rules:\n"
            "1. Answer using ONLY facts from the provided excerpts.\n"
            f"2. If the answer is completely absent, reply with EXACTLY: \"{NOT_FOUND_RESPONSE}\".\n"
            "3. Make answers simple, concise, and easy to read (use clean bullet points where appropriate).\n"
            f"4. Language requirement: {language_instruction}\n"
            "5. Cite the source page number."
        )
        user_prompt = f"Excerpts:\n{context_str}\n\nQuestion:\n{question}"
        return system_prompt, user_prompt

    @classmethod
    def _call_gemini(cls, question: str, retrieved_chunks: List[Dict[str, Any]], language: str) -> Optional[str]:
        try:
            system_prompt, user_prompt = cls._build_llm_prompt(question, retrieved_chunks, language)
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{settings.GEMINI_MODEL}:generateContent?key={settings.GEMINI_API_KEY}"
            payload = {
                "system_instruction": {"parts": [{"text": system_prompt}]},
                "contents": [{"parts": [{"text": user_prompt}]}],
                "generationConfig": {"temperature": 0.2, "maxOutputTokens": 600}
            }
            with httpx.Client(timeout=20.0) as client:
                res = client.post(url, json=payload)
                if res.status_code == 200:
                    return res.json()["candidates"][0]["content"]["parts"][0]["text"]
        except Exception as e:
            logger.warning(f"Gemini API error: {e}")
        return None

    @classmethod
    def _call_openai(cls, question: str, retrieved_chunks: List[Dict[str, Any]], language: str) -> Optional[str]:
        try:
            system_prompt, user_prompt = cls._build_llm_prompt(question, retrieved_chunks, language)
            url = "https://api.openai.com/v1/chat/completions"
            headers = {"Authorization": f"Bearer {settings.OPENAI_API_KEY}"}
            payload = {
                "model": settings.OPENAI_MODEL,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                "temperature": 0.2
            }
            with httpx.Client(timeout=20.0) as client:
                res = client.post(url, headers=headers, json=payload)
                if res.status_code == 200:
                    return res.json()["choices"][0]["message"]["content"]
        except Exception as e:
            logger.warning(f"OpenAI API error: {e}")
        return None

    @classmethod
    def _call_groq(cls, question: str, retrieved_chunks: List[Dict[str, Any]], language: str) -> Optional[str]:
        try:
            system_prompt, user_prompt = cls._build_llm_prompt(question, retrieved_chunks, language)
            url = "https://api.groq.com/openai/v1/chat/completions"
            headers = {"Authorization": f"Bearer {settings.GROQ_API_KEY}"}
            payload = {
                "model": settings.GROQ_MODEL,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                "temperature": 0.2
            }
            with httpx.Client(timeout=20.0) as client:
                res = client.post(url, headers=headers, json=payload)
                if res.status_code == 200:
                    return res.json()["choices"][0]["message"]["content"]
        except Exception as e:
            logger.warning(f"Groq API error: {e}")
        return None
