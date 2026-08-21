import psycopg2
from psycopg2.extras import RealDictCursor
from pymupdf import name
DB_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "dbname": "nexus",
    "user": "postgres",
    "password": "nexus"
}

def get_conn():
    return psycopg2.connect(**DB_CONFIG)

def get_person_by_embedding(embedding_id: str):
    conn = get_conn()
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT * FROM persons WHERE embedding_id = %s", (embedding_id,))
        result = cur.fetchone()
    conn.close()
    return result

def create_unknown_person(embedding_id: str):
    conn = get_conn()
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """INSERT INTO persons (name, embedding_id, trust_tier)
               VALUES (%s, %s, 'unknown') RETURNING *""",
            ("Unknown", embedding_id)
        )
        result = cur.fetchone()
    conn.commit()
    conn.close()
    return result

def set_trust_tier(person_id: int, new_tier: str, requested_by: str):
    if requested_by != "owner":
        raise PermissionError("Hanya owner yang boleh mengubah trust tier.")

    valid_tiers = {"owner", "family", "guest", "unknown", "blocked"}
    if new_tier not in valid_tiers:
        raise ValueError(f"Trust tier tidak valid: {new_tier}")

    conn = get_conn()
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            "UPDATE persons SET trust_tier = %s WHERE id = %s RETURNING *",
            (new_tier, person_id)
        )
        result = cur.fetchone()
    conn.commit()
    conn.close()
    return result

def log_interaction(person_id: int, summary: str):
    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO interaction_logs (person_id, summary) VALUES (%s, %s)",
            (person_id, summary)
        )
    conn.commit()
    conn.close()
def get_recent_interactions(person_id: int, limit: int = 5):
    conn = get_conn()
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """SELECT summary, timestamp FROM interaction_logs
               WHERE person_id = %s
               ORDER BY timestamp DESC LIMIT %s""",
            (person_id, limit)
        )
        result = cur.fetchall()
    conn.close()
    return result


def build_context_prompt(person_id: int) -> str:
    """
    Context Injection Pipeline.
    Narik trust tier + riwayat interaksi seseorang, susun jadi
    system prompt yang siap disuntik ke LLM (Cyrene Framework).
    """
    conn = get_conn()
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT * FROM persons WHERE id = %s", (person_id,))
        person = cur.fetchone()
    conn.close()

    if not person:
        return "Tidak ada data untuk orang ini. Perlakukan sebagai unknown."

    tier = person["trust_tier"]
    name = person["name"]

    # Behavior gate sesuai trust tier (lihat Bagian 5.5 blueprint)
    tier_rules = {
        "owner": "Berikan akses penuh ke semua konteks — jadwal, riwayat, preferensi.",
        "family": "Boleh berbagi info umum, tapi batasi detail personal/sensitif.",
        "guest": "Jaga jarak — jangan share info personal, jawab seperlunya saja.",
        "unknown": "Fokus hanya pada identifikasi. Jangan berbagi informasi apa pun.",
        "blocked": "Tolak interaksi. Jangan berikan informasi apa pun."
    }
    rule = tier_rules.get(tier, tier_rules["unknown"])

    interactions = get_recent_interactions(person_id)
    history_text = "\n".join(
        f"- {i['timestamp'].strftime('%Y-%m-%d %H:%M')}: {i['summary']}"
        for i in interactions
    ) if interactions else "Belum ada riwayat interaksi."

    # di contextual_module.py, ganti baris terakhir prompt:
    prompt = f"""Kamu adalah Cyrene, asisten AI yang sedang berbicara dengan: {name}
    Trust tier orang ini: {tier}
    Aturan perilaku: {rule}

    Riwayat interaksi terakhir:
    {history_text}

    Jawab dengan natural, sesuai aturan perilaku di atas.
    Jangan sebutkan kata "trust tier" atau level akses secara teknis ke orang tersebut.
    Kalau ditanya soal level akses/kepercayaan, jawab secara natural sesuai konteks
    (misal kalau owner: "Ya jelas dong, kamu kan yang bikin aku" — bukan ngarang
    alasan kenapa belum bisa kasih tau)."""
    return prompt
