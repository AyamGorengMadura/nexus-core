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

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

import redis
from websockets.asyncio.server import serve

from core.router import route
from core.contextual_module import build_context_prompt
from core.yuki_framework import narrate, mood_message

HOST = "0.0.0.0"
PORT = 8765
PROACTIVE_CHANNEL = "proactive-speech"

r = redis.Redis(host="localhost", port=6379, decode_responses=True)

clients: set = set()
proactive_queue: asyncio.Queue | None = None


def log(msg: str) -> None:
    print(msg, flush=True)


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
    """Ambil event face dari queue, generate ucapan Yuki, push ke semua GUI."""
    global proactive_queue
    proactive_queue = asyncio.Queue()
    while True:
        event = await proactive_queue.get()
        name = event.get("name", "seseorang")
        person_id = event.get("person_id")
        tier = event.get("trust_tier", "unknown")

        try:
            context = build_context_prompt(int(person_id)) if person_id else ""
            facts = {"name": name, "trust_tier": tier}
            mood = narrate(
                context,
                (
                    f"[sistem: {name} baru terdeteksi di depan kamera "
                    f"(tier: {tier}). Sambut mereka secara natural, singkat.]"
                ),
                facts=facts,
            )
        except Exception as e:
            mood = mood_message(f"Oh, hai {name}!", expression="neutral")
            mood["error"] = str(e)

        await broadcast(
            {
                "type": "proactive",
                "text": mood["text"],
                "expression": mood["expression"],
                "motion": mood.get("motion"),
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

            mood = await asyncio.to_thread(route, text)
            await websocket.send(
                json.dumps(
                    {
                        "type": "reply",
                        "text": mood["text"],
                        "expression": mood["expression"],
                        "motion": mood.get("motion"),
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
    asyncio.create_task(handle_proactive_events())

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
