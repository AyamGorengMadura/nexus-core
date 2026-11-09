import time
import redis
import requests
import json
from datetime import datetime
from core.yuki_framework import narrate, mood_message
from core.mood_manager import mood_manager

r = redis.Redis(host="localhost", port=6379, decode_responses=True)

class ProactiveEngine:
    """
    Handles proactive messages from Yuki.
    Triggers greetings, break reminders, and time-based reactions.
    """
    def __init__(self):
        self.last_interaction_time = {} # person_id -> timestamp
        self.proactive_cooldown = 3600 # 1 hour cooldown between proactive messages

    def should_trigger(self, person_id: int) -> bool:
        # Check if user is currently chatting (avoid interruption)
        if r.get(f"yuki:chatting:{person_id}") == "true":
            return False

        now = time.time()
        last = self.last_interaction_time.get(person_id, 0)

        if now - last > self.proactive_cooldown:
            return True
        return False

    def generate_proactive_message(self, person_id: int) -> dict:
        now = datetime.now()
        hour = now.hour

        # Determine message based on time of day
        if 5 <= hour < 12:
            text = "Selamat pagi! Baru bangun ya? Semangat buat hari ini!"
        elif 12 <= hour < 17:
            text = "Siang! Jangan lupa makan siang dan minum air yang cukup ya."
        elif 17 <= hour < 21:
            text = "Sore! Gimana harinya? Capek ya? Istirahat dulu bentar."
        else:
            text = "Malam... udah jam segini, jangan begadang terus. Tidur gih!"

        # Get current mood for tone
        mood = mood_manager.get_current_mood(person_id)
        expression = mood_manager.get_expression(mood)

        return mood_message(text, expression=expression)

    def run_cycle(self, person_id: int):
        if self.should_trigger(person_id):
            msg = self.generate_proactive_message(person_id)
            # Publish to the same event stream the frontend listens to
            r.publish("yuki:proactive", json.dumps(msg))
            self.last_interaction_time[person_id] = time.time()

# Singleton for the engine
proactive_engine = ProactiveEngine()
