# nexus-core

Core Orchestrator & Router untuk sistem Nexus/Dozor.
Bagian dari ekosistem: [nexus-docs](../nexus-docs) (arsitektur), 
[cyrene](../cyrene) (conversational framework), 
[lazarus-guard](../lazarus-guard) (face verification satellite).

## Status: Phase 1 — Core Orchestrator & Event Bus ✅

- [x] SLM Router (Ollama/Qwen 2.5 3B) — klasifikasi intent
- [x] Redis Event Bus — publish event per intent
- [ ] Phase 2: Context Engine & Contextual Module

## Setup
\`\`\`bash
pip install -r requirements.txt
docker run -d --name nexus-redis -p 6379:6379 redis
ollama pull qwen2.5:3b
python interfaces/cli_interface.py
\`\`\`

## Struktur
\`\`\`
core/          # Router, Context Engine (stabil, gak boleh tau soal interface)
interfaces/    # Adapter I/O — CLI sekarang, L2D nanti
\`\`\`

Lihat [nexus-docs](../nexus-docs) untuk blueprint arsitektur lengkap.
||||||| empty tree
# Nexus Core\nOrchestration layer for Project Nexus: Dozor.
