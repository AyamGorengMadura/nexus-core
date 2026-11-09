import requests
import json
import edge_tts
import asyncio
import os
from core.mood_manager import mood_manager

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "qwen2.5:7b"
VOICE = "en-US-AnaNeural"
TTS_OUTPUT_DIR = "nexus-core/assets/tts"

# Ensure TTS directory exists
os.makedirs(TTS_OUTPUT_DIR, exist_ok=True)

# Source of truth: l2d_model/expression_motion_map.json (S0)
VALID_EXPRESSIONS = {"neutral", "angry", "sad", "yandere"}
LEGACY_EXPRESSION_REMAP = {
    "happy": "neutral",
    "curious": "neutral",
    "concerned": "sad",
    "wave": "neutral",
    "nod": "neutral",
    "idle": "neutral",
}

yuki_PERSONA = """Kamu adalah yuki — teman ngobrol yang santai dan hangat, dengan sedikit sifat playful/tsundere.

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


def normalize_mood(result: dict) -> dict:
    """Clamp expression/motion ke enum yang valid buat model Live2D VT_student."""
    text = result.get("text") or "..."
    expression = (result.get("expression") or "neutral").strip().lower()
    expression = LEGACY_EXPRESSION_REMAP.get(expression, expression)
    if expression not in VALID_EXPRESSIONS:
        expression = "neutral"

    # Model saat ini expression-only — tidak ada .motion3.json
    return {
        "text": text,
        "expression": expression,
        "motion": None,
        **({"error": result["error"]} if result.get("error") else {}),
    }


def mood_message(text: str, expression: str = "neutral") -> dict:
    return normalize_mood({"text": text, "expression": expression, "motion": None})


def narrate(context_prompt: str, user_text: str, facts: dict = None, person_id: int = None) -> dict:
    fact_injection = ""
    if facts:
        lines = "\n".join(f"- {k}: {v}" for k, v in facts.items())
        fact_injection = f"""
FAKTA YANG SUDAH PASTI (jangan bantah, jangan ragu, jangan mengelak dengan bercanda):
{lines}
Kalau user menanyakan identitas/tier mereka secara langsung, JAWAB LANGSUNG
pakai fakta di atas tanpa berputar-putar atau balik bertanya.
"""

    # Mood Integration
    mood_modifier = ""
    current_expression = "neutral"
    if person_id:
        mood = mood_manager.get_current_mood(person_id)
        mood_modifier = f"\nMOOD SAAT INI: {mood}\n{mood_manager.get_mood_modifier(mood)}"
        current_expression = mood_manager.get_expression(mood)

    full_prompt = f"{context_prompt}\n{fact_injection}\n{mood_modifier}\n\nPesan dari user: {user_text}"

    payload = {
        "model": MODEL,
        "system": yuki_PERSONA,
        "prompt": full_prompt,
        "stream": False,
        "format": "json",
    }

    instruction = f"""Balas HANYA dalam format JSON:
{{ "text": "<respons natural kamu>", "expression": "{current_expression}", "motion": null }}

Aturan expression (wajib salah satu ini, cocokkan nada balasanmu):
- "neutral": biasa / santai / senyum tipis
- "angry": kesal / tsundere / ngomel ringan
- "sad": sedih / khawatir / kecewa
- "yandere": playful genit / posesif ringan / "ciee"
motion SELALU null (model belum punya motion clip)."""
    payload["prompt"] += f"\n\n{instruction}"

    try:
        resp = requests.post(OLLAMA_URL, json=payload, timeout=60)
        resp.raise_for_status()
        raw = resp.json()["response"]
        result = json.loads(raw)
        return normalize_mood(result)
    except Exception as e:
        return mood_message(
            "Maaf, aku lagi agak bingung nih. Bisa diulang?",
            expression="sad",
        ) | {"error": str(e)}

def synthesize_speech(text: str, filename: str = None) -> str:
    """Convert text to speech using edge-tts and save to file."""
    if not filename:
        import uuid
        filename = f"{uuid.uuid4()}.mp3"

    full_path = os.path.join(TTS_OUTPUT_DIR, filename)
    communicate = edge_tts.Communicate(text, VOICE)
    asyncio.run(communicate.save(full_path))
    return filename
