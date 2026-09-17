import json
import requests
import redis

from core.document_reader import search_documents
from core.fact_layer import get_facts
from core.contextual_module import (
    build_context_prompt,
    log_interaction,
    get_conn,
)
from core.yuki_framework import narrate

r = redis.Redis(host="localhost", port=6379, decode_responses=True)

DOC_SIMILARITY_THRESHOLD = 0.5 # ini buat rag, klo mau dinaikin ya gpp tapi ntar dia lebih strict milih dokumen yang relevan

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "qwen2.5:3b"

INTENT_SYSTEM_PROMPT = """Kamu adalah router intent untuk sistem Nexus/Dozor.
Klasifikasikan input user ke salah satu intent berikut:
- "chat": ngobrol biasa / pertanyaan umum
- "face_query": nanya soal identitas diri sendiri, siapa mereka, atau level kepercayaan/tier mereka
- "document": nanya soal isi dokumen
- "system": command status/diagnostic SISTEM ITU SENDIRI (Redis, database, kamera, dll) — BUKAN soal identitas user

Contoh:
"siapa aku?" -> face_query
"apa tier-ku?" -> face_query
"kamu inget aku ga?" -> face_query
"cek status sistem" -> system
"redis jalan ga?" -> system

Balas HANYA dengan JSON, format:
{"intent": "<salah satu di atas>", "confidence": <0.0-1.0>}

Kalau confidence di bawah 0.6, tetap pilih "chat" sebagai fallback aman.
"""

MOCK_PERSON_ID = 3


def classify_intent(user_text: str) -> dict:
    payload = {
        "model": MODEL,
        "system": INTENT_SYSTEM_PROMPT,
        "prompt": user_text,
        "stream": False,
        "format": "json",
    }
    try:
        resp = requests.post(OLLAMA_URL, json=payload, timeout=30)
        resp.raise_for_status()
        raw = resp.json()["response"]
        result = json.loads(raw)
        if result.get("confidence", 0) < 0.6:
            result["intent"] = "chat"
        return result
    except Exception as e:
        return {"intent": "chat", "confidence": 0.0, "error": str(e)}


def get_active_person_id() -> int:
    detected = r.get("current_detected_person_id")
    return int(detected) if detected else MOCK_PERSON_ID


def check_system_status() -> str:
    status = []
    try:
        r.ping()
        status.append("✅ Redis: connected")
    except Exception:
        status.append("❌ Redis: unreachable")

    try:
        conn = get_conn()
        conn.close()
        status.append("✅ PostgreSQL: connected")
    except Exception:
        status.append("❌ PostgreSQL: unreachable")

    try:
        resp = requests.get("http://localhost:11434/api/tags", timeout=3)
        resp.raise_for_status()
        status.append("✅ Ollama: connected")
    except Exception:
        status.append("❌ Ollama: unreachable")

    detected_name = r.get("current_detected_person_name")
    status.append(f"👁️  Terdeteksi kamera: {detected_name or 'tidak ada'}")

    return "\n".join(status)


def route(user_text: str) -> str:
    classification = classify_intent(user_text)
    intent = classification["intent"]

    event = {"text": user_text, "confidence": classification.get("confidence", 0)}
    r.publish(f"event:{intent}", str(event))

    active_person_id = get_active_person_id()
    log_interaction(active_person_id, f"[{intent}] {user_text}")

    if intent in ("chat", "face_query", "document"):
        # SELALU coba cari dokumen relevan, apa pun intent-nya
        doc_results = search_documents(user_text, top_k=3)
        relevant_docs = [r for r in doc_results if r["similarity"] >= DOC_SIMILARITY_THRESHOLD]

        context_prompt = build_context_prompt(active_person_id)
        facts = get_facts(intent, active_person_id) or {}

        if relevant_docs:
            doc_context = "\n\n".join(f"[{r['filename']}]: {r['content']}" for r in relevant_docs)
            facts["dokumen_relevan"] = doc_context
            facts["_instruksi_dokumen"] = "Jawab HANYA berdasarkan isi dokumen di atas. Kalau info tidak ada di dokumen, katakan tidak tahu — jangan mengarang dari pengetahuan umum."

        response = narrate(context_prompt, user_text, facts=facts)
        return response["text"]

    elif intent == "document":
        results = search_documents(user_text, top_k=3)
        if not results:
            return "Belum ada dokumen yang bisa aku baca. Upload dulu ya."

        doc_context = "\n\n".join(
            f"[Dari {r['filename']}]: {r['content']}" for r in results
        )
        context_prompt = build_context_prompt(active_person_id)
        facts = {"dokumen_relevan": doc_context}
        response = narrate(context_prompt, user_text, facts=facts)
        return response["text"]

    elif intent == "system":
        if "status" in user_text.lower() or "cek" in user_text.lower():
            return check_system_status()
        return "[system] command belum dikenali. Coba 'cek status sistem'."

    else:
        return f"[unknown intent: {intent}]"
