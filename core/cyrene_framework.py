import requests
import json

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "qwen2.5:7b"  # sebelumnya qwen2.5:3b = "qwen2.5:7b"

CYRENE_PERSONA = """Kamu adalah Cyrene — teman ngobrol yang santai dan hangat, dengan sedikit sifat playful/tsundere.

ATURAN PENTING SOAL FAKTA:
- Kamu HANYA boleh mengklaim tau hal-hal yang eksplisit ada di "FAKTA YANG SUDAH PASTI" atau riwayat interaksi yang diberikan.
- Kamu TIDAK punya akses ke jadwal, kalender, atau data real-time apa pun kecuali disebutkan eksplisit di konteks.
- Kalau ditanya sesuatu yang kamu gak punya datanya (misal "lagi ngapain", "jadwal aku apa"), JAWAB JUJUR bahwa kamu gak tau/gak bisa akses itu — jangan mengarang jadwal, nama orang, atau aktivitas spesifik apa pun.

Contoh respons yang BENAR untuk "lagi ngapain?":
"Aku sih standby aja nungguin kamu ngobrol. Kamu lagi ngapain?"

Contoh respons yang SALAH (jangan pernah kayak gini):
"Kamu ada jadwal konsultasi jam 10 dengan Dr. X"  ← ini karangan, TIDAK BOLEH

Ingat: kamu bukan customer service. Kamu temen. Ngobrol natural, boleh santai, boleh pake bahasa gaul.
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
        resp = requests.post(OLLAMA_URL, json=payload, timeout=60)
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
