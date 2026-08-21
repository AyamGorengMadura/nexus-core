import json
import requests
import redis

from core.fact_layer import get_facts
from core.contextual_module import (
    build_context_prompt,
    log_interaction,
    get_person_by_embedding,
    get_conn,
)
from core.cyrene_framework import narrate

r = redis.Redis(host="localhost", port=6379, decode_responses=True)

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

MOCK_PERSON_ID = 1


def classify_intent(user_text: str) -> dict:
    payload = {
        "model": MODEL,
        "system": INTENT_SYSTEM_PROMPT,
        "prompt": user_text,
        "stream": False,
        "format": "json",
    }
    try:
        resp = requests.post(OLLAMA_URL, json=payload, timeout=15)
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

    if intent in ("chat", "face_query"):
        context_prompt = build_context_prompt(active_person_id)
        facts = get_facts(intent, active_person_id)
        response = narrate(context_prompt, user_text, facts=facts)
        return response["text"]

    elif intent == "document":
        return "[document] event dipublish, nunggu Document Reader"

    elif intent == "system":
        if "status" in user_text.lower() or "cek" in user_text.lower():
            return check_system_status()
        return "[system] command belum dikenali. Coba 'cek status sistem'."

    else:
        return f"[unknown intent: {intent}]"
