import requests
import pypdf
from core.contextual_module import get_conn
from psycopg2.extras import RealDictCursor
import os
import shutil

INCOMING_DIR = "documents/incoming"
PROCESSED_DIR = "documents/processed"

OLLAMA_URL = "http://localhost:11434/api/embeddings"
EMBED_MODEL = "nomic-embed-text"

CHUNK_SIZE = 500      # karakter per chunk
CHUNK_OVERLAP = 50    # overlap biar konteks gak kepotong di tengah kalimat


def ingest_all_pending(uploaded_by: int = None) -> list[dict]:
    """Proses semua PDF di documents/incoming/, pindahin ke processed/ setelah selesai."""
    results = []
    for filename in os.listdir(INCOMING_DIR):
        if not filename.lower().endswith(".pdf"):
            continue

        filepath = os.path.join(INCOMING_DIR, filename)
        try:
            result = ingest_pdf(filepath, uploaded_by=uploaded_by)
            results.append(result)

            # pindahin ke processed/ biar gak keingest dobel
            shutil.move(filepath, os.path.join(PROCESSED_DIR, filename))
            print(f"✅ {filename}: {result['chunks']} chunks")
        except Exception as e:
            print(f"❌ Gagal proses {filename}: {e}")

    return results

def get_embedding(text: str) -> list[float]:
    resp = requests.post(
        OLLAMA_URL,
        json={"model": EMBED_MODEL, "prompt": text},
        timeout=30
    )
    resp.raise_for_status()
    return resp.json()["embedding"]


def chunk_text(text: str) -> list[str]:
    chunks = []
    start = 0
    while start < len(text):
        end = start + CHUNK_SIZE
        chunks.append(text[start:end])
        start = end - CHUNK_OVERLAP
    return chunks


def ingest_pdf(filepath: str, uploaded_by: int = None) -> dict:
    """Baca PDF, chunk, embed, simpan ke database."""
    reader = pypdf.PdfReader(filepath)
    full_text = "\n".join(page.extract_text() or "" for page in reader.pages)

    if not full_text.strip():
        raise ValueError("PDF tidak mengandung teks yang bisa diekstrak (kemungkinan hasil scan).")

    filename = filepath.split("/")[-1]
    chunks = chunk_text(full_text)

    conn = get_conn()
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            "INSERT INTO documents (filename, uploaded_by) VALUES (%s, %s) RETURNING id",
            (filename, uploaded_by)
        )
        doc_id = cur.fetchone()["id"]

        for i, chunk in enumerate(chunks):
            emb = get_embedding(chunk)
            cur.execute(
                """INSERT INTO document_chunks (document_id, chunk_index, content, embedding)
                   VALUES (%s, %s, %s, %s)""",
                (doc_id, i, chunk, emb)
            )
    conn.commit()
    conn.close()

    return {"document_id": doc_id, "filename": filename, "chunks": len(chunks)}


def search_documents(query: str, top_k: int = 3) -> list[dict]:
    """Cari chunk paling relevan dengan pertanyaan user."""
    query_emb = get_embedding(query)

    conn = get_conn()
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """SELECT dc.content, d.filename,
                      1 - (dc.embedding <=> %s::vector) AS similarity
               FROM document_chunks dc
               JOIN documents d ON dc.document_id = d.id
               ORDER BY dc.embedding <=> %s::vector
               LIMIT %s""",
            (query_emb, query_emb, top_k)
        )
        results = cur.fetchall()
    conn.close()
    return results


def list_documents() -> list[dict]:
    conn = get_conn()
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """SELECT d.id, d.filename, d.uploaded_at, COUNT(dc.id) AS chunk_count
               FROM documents d
               LEFT JOIN document_chunks dc ON dc.document_id = d.id
               GROUP BY d.id ORDER BY d.id"""
        )
        results = cur.fetchall()
    conn.close()
    return results