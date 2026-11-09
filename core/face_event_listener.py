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


PROACTIVE_PERSON_COOLDOWN = 300   # per orang dikenal, 5 menit
PROACTIVE_GLOBAL_GAP = 60         # jeda minimum antar sapaan APA PUN


def _is_recognized(person: dict) -> bool:
    return not str(person.get("embedding_id") or "").startswith("unknown_")


def publish_proactive(person: dict, is_new: bool):
    recognized = _is_recognized(person)
    # semua unknown berbagi satu slot, bukan per-ID (tiap flicker bikin ID baru)
    who = f"person:{person.get('id')}" if recognized else "unknown"

    # unknown yang muncul sesaat setelah orang dikenal disapa = hampir pasti flicker
    if not recognized and r.exists("greeted_recently:known"):
        return

    # Cek cooldown per person dan gap global
    if r.exists(f"greeted:{who}") or r.exists("greet:global_gap"):
        return

    r.set(f"greeted:{who}", "1", ex=PROACTIVE_PERSON_COOLDOWN)
    r.set("greet:global_gap", "1", ex=PROACTIVE_GLOBAL_GAP)
    if recognized:
        r.set("greeted_recently:known", "1", ex=PROACTIVE_PERSON_COOLDOWN)

    payload = {
        "name": person.get("name", "Unknown"),
        "person_id": person.get("id"),
        "trust_tier": person.get("trust_tier", "unknown"),
        "is_new": is_new,
        "recognized": recognized,
    }
    r.publish("proactive-speech", json.dumps(payload))
    print(f"[PROACTIVE] published for {payload['name']} (is_new={is_new})")


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

        # Session Lock: Remember identity until it's gone for a while
        identity_key = str(person["id"])

        # If identity changes, update the last known identity and trigger proactive
        if identity_key != _last_proactive_identity:
            _last_proactive_identity = identity_key
            publish_proactive(person, is_new=is_new)


if __name__ == "__main__":
    listen()
