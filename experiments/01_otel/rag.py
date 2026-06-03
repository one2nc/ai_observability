"""RAG pipeline: chunk, embed, store (pgvector), retrieve, generate. Instrumented with vanilla OTel."""

import logging
import os

import openai
import psycopg2
from opentelemetry import trace
from pgvector.psycopg2 import register_vector

log = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)

REQUIRED_ENV = ["EMBED_API_KEY", "EMBED_BASE_URL", "EMBED_MODEL", "EMBED_DIM", "CHAT_API_KEY", "CHAT_BASE_URL", "CHAT_MODEL", "DATABASE_URL"]


def _check_env() -> None:
    """Fail fast if required env vars are missing."""
    missing = [k for k in REQUIRED_ENV if not os.environ.get(k)]
    if missing:
        raise RuntimeError(f"Missing required environment variables: {', '.join(missing)}")


_check_env()

EMBED_MODEL = os.environ["EMBED_MODEL"]
EMBED_DIM = int(os.environ["EMBED_DIM"])
CHAT_MODEL = os.environ["CHAT_MODEL"]
CHUNK_SIZE = int(os.environ.get("CHUNK_SIZE", "500"))
CHUNK_OVERLAP = int(os.environ.get("CHUNK_OVERLAP", "50"))
TOP_K = int(os.environ.get("TOP_K", "5"))


def _embed_client() -> openai.OpenAI:
    """Client for embeddings."""
    return openai.OpenAI(
        api_key=os.environ["EMBED_API_KEY"],
        base_url=os.environ["EMBED_BASE_URL"],
    )


def _chat_client() -> openai.OpenAI:
    """Client for chat completions."""
    return openai.OpenAI(
        api_key=os.environ["CHAT_API_KEY"],
        base_url=os.environ["CHAT_BASE_URL"],
    )


def get_db_conn():
    """Return a psycopg2 connection with pgvector registered."""
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    with conn.cursor() as cur:
        cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
    conn.commit()
    register_vector(conn)
    return conn


def ensure_table(conn) -> None:
    """Create the chunks table if it does not exist."""
    with conn.cursor() as cur:
        cur.execute(f"""
            CREATE TABLE IF NOT EXISTS chunks (
                id SERIAL PRIMARY KEY,
                source TEXT NOT NULL,
                content TEXT NOT NULL,
                embedding vector({EMBED_DIM})
            )
        """)
    conn.commit()


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Split text into overlapping chunks."""
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start = end - overlap
    return chunks


def embed(texts: list[str]) -> list[list[float]]:
    """Call embeddings API."""
    with tracer.start_as_current_span("rag.embed", attributes={"embed.model": EMBED_MODEL, "embed.num_texts": len(texts)}):
        client = _embed_client()
        resp = client.embeddings.create(model=EMBED_MODEL, input=texts)
        return [item.embedding for item in resp.data]


def store_chunks(conn, source: str, chunks: list[str], embeddings: list[list[float]]) -> int:
    """Insert chunks + embeddings into pgvector."""
    with tracer.start_as_current_span("rag.store", attributes={"store.source": source, "store.num_chunks": len(chunks)}):
        with conn.cursor() as cur:
            for chunk, emb in zip(chunks, embeddings):
                cur.execute(
                    "INSERT INTO chunks (source, content, embedding) VALUES (%s, %s, %s)",
                    (source, chunk, emb),
                )
        conn.commit()
        return len(chunks)


def retrieve(conn, query: str, top_k: int = TOP_K) -> list[dict]:
    """Embed query and retrieve top-k similar chunks."""
    with tracer.start_as_current_span("rag.retrieve", attributes={"retrieve.top_k": top_k}):
        query_embedding = embed([query])[0]
        with tracer.start_as_current_span("rag.vector_search"):
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT content, 1 - (embedding <=> %s::vector) AS similarity
                    FROM chunks
                    ORDER BY embedding <=> %s::vector
                    LIMIT %s
                    """,
                    (query_embedding, query_embedding, top_k),
                )
                rows = cur.fetchall()
        results = [{"content": row[0], "similarity": float(row[1])} for row in rows]
        span = trace.get_current_span()
        span.set_attribute("retrieve.num_results", len(results))
        return results


def generate(query: str, context_chunks: list[dict]) -> str:
    """Send retrieved context + query to LLM for answer generation."""
    with tracer.start_as_current_span("rag.generate", attributes={"generate.model": CHAT_MODEL, "generate.num_context_chunks": len(context_chunks)}):
        context = "\n---\n".join(c["content"] for c in context_chunks)
        system_prompt = (
            "You are a helpful assistant. Answer the user's question using ONLY the provided context. "
            "Do NOT add any information that is not explicitly present in the context. "
            "If the context does not contain enough information, say 'I don't have enough information to answer this.'"
        )
        user_prompt = f"Context:\n{context}\n\nQuestion: {query}"

        client = _chat_client()
        resp = client.chat.completions.create(
            model=CHAT_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        return resp.choices[0].message.content or ""


def ingest_file(file_content: str, source: str) -> int:
    """Full ingest pipeline: chunk -> embed -> store. Idempotent (replaces existing chunks for same source)."""
    with tracer.start_as_current_span("rag.ingest", attributes={"ingest.source": source}):
        conn = get_db_conn()
        ensure_table(conn)
        with conn.cursor() as cur:
            cur.execute("DELETE FROM chunks WHERE source = %s", (source,))
        conn.commit()
        chunks = chunk_text(file_content)
        if not chunks:
            return 0
        embeddings = embed(chunks)
        count = store_chunks(conn, source, chunks, embeddings)
        conn.close()
        return count


def ask(query: str) -> dict:
    """Full ask pipeline: embed query -> retrieve -> generate."""
    with tracer.start_as_current_span("rag.ask"):
        conn = get_db_conn()
        ensure_table(conn)
        context_chunks = retrieve(conn, query)
        conn.close()
        if not context_chunks:
            return {"answer": "No relevant documents found.", "sources": []}
        answer = generate(query, context_chunks)
        answer = generate(query, context_chunks)
        sources = [{"content": c["content"], "similarity": round(c["similarity"], 3)} for c in context_chunks]
        return {"answer": answer, "sources": sources}
