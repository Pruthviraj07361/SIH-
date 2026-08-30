"""
Local embeddings via fastembed (ONNX-based — much lighter on RAM than
sentence-transformers/PyTorch, important for free-tier hosting like Render's
512MB limit). No API key needed — runs on-device.
Stores/searches vectors in Supabase via pgvector, per the spec's recommendation
(one less moving part than a separate local FAISS index).
"""
from fastembed import TextEmbedding
from app.db import get_client

# BAAI/bge-small-en-v1.5 outputs 384-dim vectors — same size as the
# all-MiniLM-L6-v2 model this replaces, so the existing `vector(384)`
# column in schema.sql and the match_chunks() RPC don't need to change.
EMBEDDING_MODEL_NAME = "BAAI/bge-small-en-v1.5"

_model = None


def get_model() -> TextEmbedding:
    """Lazy-load the model once and reuse it (loading it per-call is slow)."""
    global _model
    if _model is None:
        _model = TextEmbedding(model_name=EMBEDDING_MODEL_NAME)
    return _model


def embed_chunks(chunks: list[str]) -> list[list[float]]:
    """Returns one embedding vector per chunk."""
    model = get_model()
    vectors = model.embed(chunks)  # generator of numpy arrays
    return [v.tolist() for v in vectors]


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
    query_vector = next(model.embed([query])).tolist()

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