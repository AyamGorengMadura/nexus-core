import redis
import json
import os
import threading
from core.contextual_module import get_person_by_embedding, create_unknown_person, log_interaction

r = redis.Redis(host="localhost", port=6379, decode_responses=True)

# Hindari spam proactive tiap frame — hanya saat identitas berganti
_last_proactive_identity = None


def watch_for_quit():
    """Jalan di thread terpisah, dengerin input keyboard tanpa nge-block main loop."""
    while True:
        cmd = input()
        if cmd.strip().lower() == "q":
            print("[STOP] 'q' ditekan, mematikan listener...")
            os._exit(0)


def publish_proactive(person: dict, is_new: bool):
    """Minta ws_interface (kalau hidup) supaya Yuki nyapa duluan."""
    payload = {
        "person_id": person["id"],
        "name": person["name"],
        "trust_tier": person.get("trust_tier", "unknown"),
        "event": "face_new" if is_new else "face_changed",
    }
    r.publish("proactive-speech", json.dumps(payload))
    print(f"[PROACTIVE] published for {person['name']} ({payload['event']})")


def listen():
    global _last_proactive_identity

    pubsub = r.pubsub()
    pubsub.subscribe("event:face_detected")
    print("Listening for face_detected events...")
    print("Ketik 'q' lalu Enter buat berhenti.")

    threading.Thread(target=watch_for_quit, daemon=True).start()

    for message in pubsub.listen():
        if message["type"] != "message":
            continue

        data = json.loads(message["data"])
        embedding_id = data.get("embedding_id")

        person = get_person_by_embedding(embedding_id)
        is_new = person is None
        if is_new:
            person = create_unknown_person(embedding_id)
            print(f"[NEW] Unknown face registered: {person}")
        else:
            print(f"[MATCH] {person['name']} (tier: {person['trust_tier']})")

        r.set("current_detected_person_id", person["id"], ex=10)
        r.set("current_detected_person_name", person["name"], ex=10)
        log_interaction(person["id"], "Wajah terdeteksi kamera")

        identity_key = str(person["id"])
        if identity_key != _last_proactive_identity:
            _last_proactive_identity = identity_key
            publish_proactive(person, is_new=is_new)


if __name__ == "__main__":
    listen()
