import json
import requests
import redis

from core.document_reader import search_documents
from core.fact_layer import get_facts
from core.system_monitor import SystemMonitor, get_current_time_info
from core.contextual_module import (
    build_context_prompt,
    build_context_prompt,
    log_interaction,
    get_conn,
)
from core.yuki_framework import narrate, mood_message
from core.mood_manager import mood_manager

r = redis.Redis(host="localhost", port=6379, decode_responses=True)

DOC_SIMILARITY_THRESHOLD = 0.5

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

    # Add hardware stats to system status
    monitor = SystemMonitor()
    stats = monitor.get_stats()
    status.append(f"💻 CPU: {stats['cpu']}% | RAM: {stats['ram']}% | Battery: {stats['battery']}%")

    detected_name = r.get("current_detected_person_name")
    status.append(f"👁️  Terdeteksi kamera: {detected_name or 'tidak ada'}")

    return "\n".join(status)


def route(user_text: str) -> dict:
    """
    Return mood payload untuk CLI / WebSocket / GUI:
    {"text": str, "expression": str, "motion": null}
    """
    # OS-level Awareness: Add current time/date to context
    time_info = get_current_time_info()

    classification = classify_intent(user_text)
    intent = classification["intent"]

    event = {"text": user_text, "confidence": classification.get("confidence", 0)}
    r.publish(f"event:{intent}", str(event))

    active_person_id = get_active_person_id()
    try:
        log_interaction(active_person_id, f"[{intent}] {user_text}")
    except Exception as e:
        print(f"[Router] Warning: Could not log interaction to DB: {e}")


    # If it's a chat or specific query, we always try to find relevant context from docs
    # This expands the router's ability to handle document queries implicitly
    if intent in ("chat", "face_query", "document"):
        # Update mood based on user input
        mood_manager.update_mood_from_text(active_person_id, user_text)

        # Increase top_k to 5 to get more candidate chunks for the LLM to filter
        doc_results = search_documents(user_text, top_k=5)

        # Use a slightly lower threshold for semantic search to allow more contextual matches,
        # but still filter out completely irrelevant noise.
        relevant_docs = [row for row in doc_results if row["similarity"] >= (DOC_SIMILARITY_THRESHOLD - 0.1)]

        context_prompt = build_context_prompt(active_person_id)
        facts = get_facts(intent, active_person_id) or {}

        # Add current time/date to facts so Yuki knows it
        facts["waktu_sekarang"] = time_info

        if relevant_docs:
            doc_context = "\n\n".join(
                f"[{row['filename']}]: {row['content']}" for row in relevant_docs
            )
            facts["dokumen_relevan"] = doc_context
            facts["_instruksi_dokumen"] = (
                "Informasi berikut berasal dari dokumen internal. Gunakan informasi ini "
                "untuk memperkaya jawabanmu. Jika informasi di dokumen bertentangan dengan "
                "pengetahuan umum, prioritaskan dokumen. Jika informasi tidak ditemukan, "
                "tetap jawab sebaik mungkin namun beri tahu user bahwa informasi detail "
                "tidak ditemukan di dokumen."
            )

        return narrate(context_prompt, user_text, facts=facts, person_id=active_person_id)

    if intent == "system":
        if "status" in user_text.lower() or "cek" in user_text.lower():
            return mood_message(check_system_status(), expression="neutral")
        return mood_message(
            "[system] command belum dikenali. Coba 'cek status sistem'.",
            expression="neutral",
        )

    return mood_message(f"[unknown intent: {intent}]", expression="neutral")
