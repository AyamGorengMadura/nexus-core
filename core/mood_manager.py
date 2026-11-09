import json
import os
import redis
from datetime import datetime

r = redis.Redis(host="localhost", port=6379, decode_responses=True)

class MoodManager:
    """
    Manages Yuki's emotional state based on user interactions.
    States: Neutral, Happy, Sad, Angry, Tsundere.
    """
    STATES = {
        "Neutral": "neutral",
        "Happy": "yandere",  # Mapping to valid L2D expressions (using yandere for playful/happy)
        "Sad": "sad",
        "Angry": "angry",
        "Tsundere": "angry"   # Tsundere often manifests as 'angry' in expressions
    }

    MOOD_KEYWORDS = {
        "Happy": ["senang", "bahagia", "keren", "pintar", "lucu", "sayang", "love", "thanks", "terima kasih"],
        "Sad": ["sedih", "kecewa", "payah", "bodoh", "benci", "marah", "kesal"],
        "Angry": ["berisik", "diam", "gak berguna", "stop", "jahat"],
        "Tsundere": ["tsundere", "malu", "baka", "apa sih"],
    }

    def __init__(self):
        self.default_mood = "Neutral"

    def get_current_mood(self, person_id: int) -> str:
        mood = r.get(f"yuki:mood:{person_id}")
        return mood if mood else self.default_mood

    def set_mood(self, person_id: int, mood: str):
        if mood in self.STATES:
            r.set(f"yuki:mood:{person_id}", mood)
            # Expire mood after 1 hour to return to neutral
            r.expire(f"yuki:mood:{person_id}", 3600)

    def update_mood_from_text(self, person_id: int, text: str):
        text_lower = text.lower()

        # Simple keyword-based mood shift
        for mood, keywords in self.MOOD_KEYWORDS.items():
            if any(kw in text_lower for kw in keywords):
                self.set_mood(person_id, mood)
                return mood

        # If no keyword, mood slowly drifts back to Neutral or stays
        return self.get_current_mood(person_id)

    def get_expression(self, mood: str) -> str:
        return self.STATES.get(mood, "neutral")

    def get_mood_modifier(self, mood: str) -> str:
        """Returns a prompt modifier to adjust Yuki's tone based on mood."""
        modifiers = {
            "Neutral": "Gunakan nada bicara yang santai, hangat, dan natural.",
            "Happy": "Kamu merasa sangat senang dan bersemangat! Gunakan nada yang ceria, lebih banyak ekspresi kegembiraan, dan sedikit lebih manja.",
            "Sad": "Kamu merasa sedikit sedih atau kecewa. Nada bicaramu lebih pelan, kurang bersemangat, dan sedikit melankolis.",
            "Angry": "Kamu sedang kesal! Gunakan nada yang ketus, singkat, dan menunjukkan rasa tidak suka.",
            "Tsundere": "Kamu sedang dalam mode tsundere. Kamu peduli tapi malu mengakuinya, jadi kamu bicara dengan nada agak ketus/galak tapi sebenarnya perhatian (classic 'Baka!')."
        }
        return modifiers.get(mood, modifiers["Neutral"])

mood_manager = MoodManager()
