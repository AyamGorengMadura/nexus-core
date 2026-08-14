import requests
import json
import redis
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
r = redis.Redis(host="localhost", port=6379, decode_responses=True)

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

        # fallback guard kalau confidence rendah
        if result.get("confidence", 0) < 0.6:
            result["intent"] = "chat"
        return result
    except Exception as e:
        # fallback total kalau Ollama gagal / response gak valid
        return {"intent": "chat", "confidence": 0.0, "error": str(e)}


def route(user_text: str) -> str:
    classification = classify_intent(user_text)
    intent = classification["intent"]

    # publish event ke channel sesuai intent
    event = {"text": user_text, "confidence": classification.get("confidence", 0)}
    r.publish(f"event:{intent}", str(event))

    if intent == "chat":
        return f"[chat] (belum nyambung ke Cyrene Framework) — kamu bilang: {user_text}"
    elif intent == "face_query":
        return "[face_query] event dipublish ke Redis, nunggu Lazarus Guard"
    elif intent == "document":
        return "[document] event dipublish ke Redis, nunggu Document Reader"
    elif intent == "system":
        return "[system] event dipublish ke Redis, belum ada handler"
    else:
        return f"[unknown intent: {intent}]"
    """Entry point utama. Nanti ini yang manggil satelit sesuai intent."""
    classification = classify_intent(user_text)
    print(f"[DEBUG] intent={classification}")  # sementara, buat verifikasi
    intent = classification["intent"]

    # Placeholder — nanti tiap intent manggil modul/satelit beneran
    if intent == "chat":
        return f"[chat] (belum nyambung ke Cyrene Framework) — kamu bilang: {user_text}"
    elif intent == "face_query":
        return "[face_query] (belum nyambung ke Lazarus Guard)"
    elif intent == "document":
        return "[document] (belum nyambung ke Document Reader)"
    elif intent == "system":
        return "[system] (belum ada command handler)"
    else:
        return f"[unknown intent: {intent}]"
