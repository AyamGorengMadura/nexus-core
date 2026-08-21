import requests
import json

OLLAMA_URL = "http://localhost:11434/api/generate"
NARRATOR_MODEL = "qwen2.5:7b"

CYRENE_PERSONA = """Kamu adalah Cyrene — AI companion yang hangat, natural, dan responsif.
Kamu BUKAN asisten formal/robotik. Kamu ngobrol kayak teman yang perhatian.
Jawab singkat dan natural, jangan bertele-tele.
"""


def narrate(context_prompt: str, user_text: str, facts: dict = None) -> dict:
    fact_injection = ""
    if facts:
        lines = "\n".join(f"- {k}: {v}" for k, v in facts.items())
        fact_injection = f"""
FAKTA YANG SUDAH PASTI (jangan bantah, jangan ragu, jangan mengelak dengan bercanda):
{lines}
Kalau user menanyakan identitas/tier mereka secara langsung, JAWAB LANGSUNG
pakai fakta di atas tanpa berputar-putar atau balik bertanya.
"""

    full_prompt = f"{context_prompt}\n{fact_injection}\n\nPesan dari user: {user_text}"

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
        return {
            "text": "Maaf, aku lagi agak bingung nih. Bisa diulang?",
            "expression": "concerned",
            "motion": "idle",
            "error": str(e)
        }
