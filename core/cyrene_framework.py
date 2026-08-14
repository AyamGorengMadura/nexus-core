import requests
import json

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "qwen2.5:3b"

CYRENE_PERSONA = """Kamu adalah Cyrene — AI companion yang hangat, natural, dan responsif.
Kamu BUKAN asisten formal/robotik. Kamu ngobrol kayak teman yang perhatian.
Jawab singkat dan natural, jangan bertele-tele.
"""


def narrate(context_prompt: str, user_text: str, raw_result: str = None) -> dict:
    """
    Narration Layer.
    Input: context prompt (dari Contextual Module) + teks user +
           hasil mentah dari satelit (kalau ada, misal dari Lazarus Guard nanti).
    Output: JSON terstruktur — text + expression + motion,
            siap dikirim ke interface (CLI sekarang, L2D nanti).
    """
    full_prompt = f"{context_prompt}\n\nPesan dari user: {user_text}"
    if raw_result:
        full_prompt += f"\n\nData tambahan dari sistem: {raw_result}"

    payload = {
        "model": MODEL,
        "system": CYRENE_PERSONA,
        "prompt": full_prompt,
        "stream": False,
        "format": "json"
    }

    instruction = """Balas HANYA dalam format JSON:
{"text": "<respons natural kamu>", "expression": "<happy|neutral|curious|concerned>", "motion": "<wave|nod|idle>"}"""
    payload["prompt"] += f"\n\n{instruction}"

    try:
        resp = requests.post(OLLAMA_URL, json=payload, timeout=20)
        resp.raise_for_status()
        raw = resp.json()["response"]
        result = json.loads(raw)
        return result
    except Exception as e:
        # fallback aman kalau LLM gagal/response gak valid JSON
        return {
            "text": "Maaf, aku lagi agak bingung nih. Bisa diulang?",
            "expression": "concerned",
            "motion": "idle",
            "error": str(e)
        }
