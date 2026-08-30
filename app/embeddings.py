"""
Local embeddings via sentence-transformers (no API key needed — runs on-device).
Stores/searches vectors in Supabase via pgvector, per the spec's recommendation
(one less moving part than a separate local FAISS index).
"""
from sentence_transformers import SentenceTransformer
from app.config import EMBEDDING_MODEL
from app.db import get_client

_model = None


def get_model() -> SentenceTransformer:
    """Lazy-load the model once and reuse it (loading it per-call is slow)."""
    global _model
    if _model is None:
        _model = SentenceTransformer(EMBEDDING_MODEL)
    return _model


def embed_chunks(chunks: list[str]) -> list[list[float]]:
    """Returns one embedding vector per chunk."""
    model = get_model()
    vectors = model.encode(chunks, show_progress_bar=False)
    return vectors.tolist()


def store_chunks(material_id: str, chunks: list[str]) -> None:
    """Embeds and stores chunks in the `chunks` table (see schema.sql)."""
    if not chunks:
        # Nothing to store — e.g. an empty/blank/image-only PDF with no
        # extractable text. Inserting an empty list would send a malformed
        # request to PostgREST (PGRST100: "failed to parse columns
        # parameter"), so bail out here instead.
        return
    vectors = embed_chunks(chunks)
    supabase = get_client()
    rows = [
        {"material_id": material_id, "content": chunk, "embedding": vector}
        for chunk, vector in zip(chunks, vectors)
    ]
    supabase.table("chunks").insert(rows).execute()


def search_similar_chunks(material_id: str, query: str, top_k: int = 5) -> list[str]:
    """
    Finds the chunks most relevant to `query` (e.g. a topic name) within one
    material, via a pgvector similarity RPC (see schema.sql for the function).
    """
    model = get_model()
    query_vector = model.encode([query])[0].tolist()

    supabase = get_client()
    result = supabase.rpc(
        "match_chunks",
        {
            "query_embedding": query_vector,
            "match_material_id": material_id,
            "match_count": top_k,
        },
    ).execute()

    return [row["content"] for row in result.data]