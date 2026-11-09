import os
from pathlib import Path

# Project Roots
BASE_DIR = Path(__file__).resolve().parent.parent
CORE_DIR = Path(__file__).resolve().parent

# Asset Paths
TTS_OUTPUT_DIR = CORE_DIR / "assets" / "tts"

# Server Config
WS_HOST = "0.0.0.0"
WS_PORT = 8765
AUDIO_PORT = 8000

# Redis Config
REDIS_HOST = "localhost"
REDIS_PORT = 6379
PROACTIVE_CHANNEL = "proactive-speech"

# Database Config
DB_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "dbname": "nexus",
    "user": "postgres",
    "password": "nexus"
}

# LLM Config
OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_TAGS_URL = "http://localhost:11434/api/tags"
MODEL_ROUTER = "qwen2.5:3b"
MODEL_NARRATE = "qwen2.5:7b"

# TTS Config
VOICE = "en-US-AnaNeural"

# App Constants
DOC_SIMILARITY_THRESHOLD = 0.5
MOCK_PERSON_ID = 3
