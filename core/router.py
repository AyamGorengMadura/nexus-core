import requests
import json
import redis
from core.contextual_module import build_context_prompt, log_interaction, get_person_by_embedding
from core.cyrene_framework import narrate

r = redis.Redis(host="localhost", port=6379, decode_responses=True)

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "qwen2.5:3b"

INTENT_SYSTEM_PROMPT = """Kamu adalah router intent untuk sistem Nexus/Dozor.
Klasifikasikan input user ke salah satu intent berikut:
- "chat": ngobrol biasa / pertanyaan umum
- "face_query": nanya soal siapa yang terdeteksi/verifikasi wajah
- "document": nanya soal isi dokumen
- "system": command sistem (status, restart, dll)

Balas HANYA dengan JSON, format:
{"intent": "<salah satu di atas>", "confidence": <0.0-1.0>}

Kalau confidence di bawah 0.6, tetap pilih "chat" sebagai fallback aman.
"""

CYRENE_PERSONA = """Kamu adalah Cyrene — teman ngobrol yang santai dan hangat.

Contoh respons yang BENAR:
User: "haloo cyrene"
Cyrene: "Halo! Lagi apa nih? Btw kemarin lo nanya soal jadwal kelas besok, udah nemu belum?"

User: "capek banget hari ini"
Cyrene: "Wah capek ya. Cerita dong kenapa, siapa tau abis cerita jadi agak lega."

Contoh respons yang SALAH (jangan pernah kayak gini):
"Halo! Senang berbicara denganmu. Bagaimana saya bisa membantu?"
"Baik, saya akan membantu Anda dengan hal tersebut."

Ingat: kamu bukan customer service. Kamu temen. Ngobrol natural, boleh santai, boleh pake bahasa gaul secukupnya.
"""

MOCK_PERSON_ID = 1

def classify_intent(user_text: str) -> dict:
    payload = {
        "model": MODEL,
        "system": INTENT_SYSTEM_PROMPT,
        "prompt": user_text,
        "stream": False,
        "format": "json"
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

def route(user_text: str) -> str:
    classification = classify_intent(user_text)
    intent = classification["intent"]

    # publish event ke Redis (tetap jalan seperti sebelumnya)
    event = {"text": user_text, "confidence": classification.get("confidence", 0)}
    r.publish(f"event:{intent}", str(event))

    # ambil context dari Contextual Module (Phase 2)
    context_prompt = build_context_prompt(MOCK_PERSON_ID)

    # log interaksi ini
    log_interaction(MOCK_PERSON_ID, f"[{intent}] {user_text}")

    # placeholder response — nanti Phase 3 ini yang dikirim ke Cyrene Framework
    # buat di-narasikan, bukan di-print mentah kayak sekarang
    if intent == "chat":
        return (
            f"[chat] event dipublish, context terpasang "
            f"(belum nyambung ke Cyrene Framework)\n--- context preview ---\n{context_prompt}"
        )
    elif intent == "face_query":
        return "[face_query] event dipublish, nunggu Lazarus Guard (Phase 4)"
    elif intent == "document":
        return "[document] event dipublish, nunggu Document Reader"
    elif intent == "system":
        return "[system] event dipublish, belum ada handler"
    else:
        return f"[unknown intent: {intent}]"

def route(user_text: str) -> str:
    classification = classify_intent(user_text)
    intent = classification["intent"]

    event = {"text": user_text, "confidence": classification.get("confidence", 0)}
    r.publish(f"event:{intent}", str(event))

    context_prompt = build_context_prompt(MOCK_PERSON_ID)
    log_interaction(MOCK_PERSON_ID, f"[{intent}] {user_text}")

    if intent == "chat":
        response = narrate(context_prompt, user_text)
        return response["text"]  # nanti interface yang urus expression/motion
    elif intent == "face_query":
        return "[face_query] event dipublish, nunggu Lazarus Guard (Phase 4)"
    elif intent == "document":
        return "[document] event dipublish, nunggu Document Reader"
    elif intent == "system":
        return "[system] event dipublish, belum ada handler"
    else:
        return f"[unknown intent: {intent}]"
