"""
WebSocket interface untuk GUI Live2D / customer-facing chat.

Run (fish):
  source .venv/bin/activate.fish
  python interfaces/ws_interface.py

Protocol:
  Client -> Server: {"type": "chat", "text": "..."}
  Server -> Client: {"type": "reply"|"proactive", "text": "...", "expression": "...", "motion": null}
"""

from __future__ import annotations

import asyncio
import json
import sys
import os
import threading
import random
import redis
from http.server import SimpleHTTPRequestHandler
from socketserver import TCPServer
from websockets.server import serve

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from core.router import route
from core.contextual_module import build_context_prompt
from core.yuki_framework import narrate, mood_message, synthesize_speech
from core.system_monitor import SystemMonitor



from core.logger import get_logger
from config import (
    WS_HOST, WS_PORT, AUDIO_PORT, REDIS_HOST, REDIS_PORT,
    PROACTIVE_CHANNEL, TTS_OUTPUT_DIR
)

logger = get_logger("ws_interface")

def log(msg):
    logger.info(msg)

def start_audio_server():
    """Jalanin HTTP server buat serve file .mp3 dari assets/tts."""
    # Tentukan folder assets/tts absolut
    base_dir = TTS_OUTPUT_DIR

    class AudioHandler(SimpleHTTPRequestHandler):
        def translate_path(self, path):
            # Map /audio/uuid.mp3 -> assets/tts/uuid.mp3
            if path.startswith("/audio/"):
                return os.path.join(base_dir, path[7:])
            return super().translate_path(path)

    # Jalankan di port 8000
    httpd = TCPServer(("0.0.0.0", AUDIO_PORT), AudioHandler)
    log("[HTTP] Audio server started on port 8000")
    httpd.serve_forever()

HOST = WS_HOST
PORT = WS_PORT
PROACTIVE_CHANNEL = PROACTIVE_CHANNEL


r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)

clients: set = set()
proactive_queue: asyncio.Queue | None = None


GREETINGS = {
    "owner": [
        ("Oh, {name}. Akhirnya muncul juga.", "neutral"),
        ("Hmph, telat. Tapi ya udah, selamat datang, {name}.", "angry"),
        ("Hai {name}! Aku standby dari tadi.", "neutral"),
    ],
    "known": [
        ("Hai {name}, selamat datang.", "neutral"),
        ("Oh, ada {name}. Halo!", "neutral"),
    ],
    "stranger": [
        ("Hai, aku Yuki. Kamu siapa ya?", "neutral"),
        ("Halo, belum kenal nih. Siapa namamu?", "neutral"),
    ],
}


def greeting_for(event: dict) -> dict:
    name = event.get("name") or "kamu"
    recognized = event.get("recognized", name != "Unknown")
    if not recognized:
        pool = GREETINGS["stranger"]
    elif event.get("trust_tier") == "owner":
        pool = GREETINGS["owner"]
    else:
        pool = GREETINGS["known"]
    text, expr = random.choice(pool)
    return mood_message(text.format(name=name), expression=expr)


def listen_for_exit():
    """Thread terpisah untuk mendengarkan input terminal. 'q' untuk stop."""
    while True:
        try:
            char = sys.stdin.read(1)
            if char.lower() == 'q':
                log("\n[WS] Killswitch triggered! Stopping server...")
                os._exit(0)
        except EOFError:
            break


def _redis_subscriber(loop: asyncio.AbstractEventLoop):
    """Thread terpisah: subscribe Redis, push event ke asyncio queue."""
    try:
        pubsub = r.pubsub()
        pubsub.subscribe(PROACTIVE_CHANNEL)
        log(f"[WS] subscribed Redis channel: {PROACTIVE_CHANNEL}")
        for message in pubsub.listen():
            if message["type"] != "message":
                continue
            try:
                data = json.loads(message["data"])
            except json.JSONDecodeError:
                continue
            if proactive_queue is not None:
                loop.call_soon_threadsafe(proactive_queue.put_nowait, data)
    except Exception as e:
        log(f"[WS] Redis subscriber error: {e}")


async def broadcast(payload: dict):
    if not clients:
        return
    raw = json.dumps(payload, ensure_ascii=False)
    dead = []
    for ws in clients:
        try:
            await ws.send(raw)
        except Exception:
            dead.append(ws)
    for ws in dead:
        clients.discard(ws)


async def handle_proactive_events():
    """Ambil event face dari queue, gunakan greeting pre-baked untuk hemat resource Ollama."""
    global proactive_queue
    proactive_queue = asyncio.Queue()
    while True:
        event = await proactive_queue.get()

        # Handle system alerts directly, bypass greeting_for
        if event.get("type") == "system_alert":
            text = event.get("text", "Sistem ada masalah!")
            expr = event.get("expression", "angry")
        else:
            mood = greeting_for(event)
            text = mood["text"]
            expr = mood["expression"]

        # TTS Generation for proactive
        audio_file = await asyncio.to_thread(synthesize_speech, text)
        await broadcast(
            {
                "type": "proactive",
                "text": text,
                "expression": expr,
                "motion": None,
                "audio": audio_file,
            }
        )


async def handle_client(websocket):
    clients.add(websocket)
    peer = getattr(websocket, "remote_address", None)
    log(f"[WS] client connected: {peer} (total={len(clients)})")
    try:
        await websocket.send(
            json.dumps(
                {
                    "type": "hello",
                    "text": "Yuki online.",
                    "expression": "neutral",
                    "motion": None,
                }
            )
        )
        async for raw in websocket:
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                await websocket.send(
                    json.dumps(
                        {**mood_message("Pesan tidak valid (bukan JSON).", "sad"), "type": "error"}
                    )
                )
                continue

            if msg.get("type") != "chat":
                await websocket.send(
                    json.dumps(
                        {**mood_message("type harus 'chat'.", "neutral"), "type": "error"}
                    )
                )
                continue

            text = (msg.get("text") or "").strip()
            if not text:
                continue

            try:
                mood = await asyncio.to_thread(route, text)
                # TTS Generation
                audio_file = await asyncio.to_thread(synthesize_speech, mood["text"])
            except Exception as e:
                log(f"[WS] route()/tts error: {e}")
                mood = mood_message(
                    "Maaf, ada error di backend. Cek log nexus.", expression="sad"
                )
                audio_file = None

            await websocket.send(
                json.dumps(
                    {
                        "type": "reply",
                        "text": mood["text"],
                        "expression": mood["expression"],
                        "motion": mood.get("motion"),
                        "audio": audio_file,
                    },
                    ensure_ascii=False,
                )
            )
    finally:
        clients.discard(websocket)
        log(f"[WS] client disconnected: {peer} (total={len(clients)})")


async def main():
    try:
        r.ping()
        log("[WS] Redis: ok")
    except Exception as e:
        log(f"[WS] Redis unreachable ({e}) — proactive-speech nonaktif sampai Redis hidup")

    loop = asyncio.get_running_loop()
    threading.Thread(target=_redis_subscriber, args=(loop,), daemon=True).start()
    threading.Thread(target=listen_for_exit, daemon=True).start()
    threading.Thread(target=start_audio_server, daemon=True).start()
    asyncio.create_task(handle_proactive_events())

    # System Monitor Integration
    def on_system_alert(alert_text):
        # Publish alert to Redis so handle_proactive_events can pick it up and broadcast
        # We wrap it in a format that greeting_for or handle_proactive_events can handle
        # Since greeting_for expects an event with name/trust_tier, we'll bypass it
        # and send a direct proactive message.
        log(f"[SystemMonitor] Alert: {alert_text}")
        # We push to Redis to keep it consistent with the proactive flow
        r.publish(PROACTIVE_CHANNEL, json.dumps({
            "type": "system_alert",
            "text": alert_text,
            "expression": "angry"
        }))

    monitor = SystemMonitor()
    monitor.start(on_system_alert)

    log(f"[WS] starting on ws://{HOST}:{PORT} ...")
    async with serve(handle_client, HOST, PORT) as server:
        log(f"[WS] Nexus WebSocket listening on ws://{HOST}:{PORT}")
        log('[WS] GUI: kirim {"type":"chat","text":"halo"}')
        await server.serve_forever()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log("[WS] stopped")
    except OSError as e:
        log(f"[WS] gagal bind port {PORT}: {e}")
        sys.exit(1)
