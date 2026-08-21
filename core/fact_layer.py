from core.contextual_module import get_conn
from psycopg2.extras import RealDictCursor

# intent -> facts yang WAJIB disuntik sebelum narration.
# Intent yang gak ada di sini jalan tanpa fact injection (pure conversational).
INTENT_FACT_REQUIREMENTS = {
    "face_query": ["identity", "trust_tier"],
}


def get_facts(intent: str, person_id: int) -> dict | None:
    """
    Return dict fakta terstruktur — TIDAK PERNAH return kalimat/prose.
    None kalau intent ini gak butuh fakta apa pun.
    """
    required = INTENT_FACT_REQUIREMENTS.get(intent)
    if not required:
        return None

    conn = get_conn()
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT * FROM persons WHERE id = %s", (person_id,))
        person = cur.fetchone()
    conn.close()

    if not person:
        return None

    facts = {}
    if "identity" in required:
        facts["name"] = person["name"]
    if "trust_tier" in required:
        facts["trust_tier"] = person["trust_tier"]
    return facts
