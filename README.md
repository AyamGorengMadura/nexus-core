# nexus-core

Core Orchestrator & Router untuk sistem Nexus/Dozor.
Bagian dari ekosistem: [nexus-docs](../nexus-docs) (arsitektur), 
[cyrene](../cyrene) (conversational framework), 
[lazarus-guard](../lazarus-guard) (face verification satellite).

## Status

- [x] Phase 1 — Core Orchestrator & Event Bus
  - [x] SLM Router (Ollama/Qwen 2.5 3B) — klasifikasi intent
  - [x] Redis Event Bus — publish event per intent
- [x] Phase 2 — Context Engine & Contextual Module
  - [x] PostgreSQL + pgvector — skema `persons`, `interaction_logs`
  - [x] Trust tier enforcement (owner-only, `set_trust_tier`)
  - [x] Context Injection Pipeline (`build_context_prompt`)
  - [x] Wired ke router.py (mock `person_id` — nunggu Lazarus Guard di Phase 4)
- [ ] Phase 3 — Cyrene Framework & Cyrene L2D (WIP)
  - [x] Narration Layer — Qwen 2.5 7B (narrator), Qwen 2.5 3B (router, split by function)
  - [x] Fact Layer — deterministic fact injection per-intent
  - [x] Grounding constraint — narrator no longer fabricates ungrounded claims
  - [x] Full 6-scenario test suite passing (identity, tier, chat, open-ended, combined, system)
  - [x] Admin Tool (core/admin.py) — kelola trust tier tanpa SQL manual
  - [x] Fixed: stale camera-detection state (Redis TTL)
  - [ ] Emotion tags (expression/motion) — output ada, belum ada consumer
  - [ ] Cyrene L2D — belum dibangun sama sekali
- [ ] Phase 4 — Lazarus Guard & Telegram Alert

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
