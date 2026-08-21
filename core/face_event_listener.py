import redis
import json
import os
import threading
from core.contextual_module import get_person_by_embedding, create_unknown_person, log_interaction

r = redis.Redis(host="localhost", port=6379, decode_responses=True)


def watch_for_quit():
    """Jalan di thread terpisah, dengerin input keyboard tanpa nge-block main loop."""
    while True:
        cmd = input()
        if cmd.strip().lower() == "q":
            print("[STOP] 'q' ditekan, mematikan listener...")
            os._exit(0)  # paksa keluar proses total, gak peduli main thread lagi ngeblock di mana


def listen():
    pubsub = r.pubsub()
    pubsub.subscribe("event:face_detected")
    print("Listening for face_detected events...")
    print("Ketik 'q' lalu Enter buat berhenti.")

    # thread daemon buat dengerin quit command
    threading.Thread(target=watch_for_quit, daemon=True).start()

    for message in pubsub.listen():
        if message["type"] != "message":
            continue

        data = json.loads(message["data"])
        embedding_id = data.get("embedding_id")

        person = get_person_by_embedding(embedding_id)
        if person is None:
            person = create_unknown_person(embedding_id)
            print(f"[NEW] Unknown face registered: {person}")
        else:
            print(f"[MATCH] {person['name']} (tier: {person['trust_tier']})")

        r.set("current_detected_person_id", person["id"])
        r.set("current_detected_person_name", person["name"])
        log_interaction(person["id"], "Wajah terdeteksi kamera")


if __name__ == "__main__":
    listen()
