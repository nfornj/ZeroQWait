"""
SearchCustomerContext — pgvector-backed semantic search tool.

Embeds the query using all-MiniLM-L6-v2 (same model as the semantic cache)
and retrieves the k most similar conversation_history rows via cosine distance.

Usage (from any LangGraph node or pydantic-ai tool):
    results = await search_customer_context(query="book appointment haircut", shop_id=5, k=5)
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional

from sqlalchemy import text

from database import SessionLocal

logger = logging.getLogger(__name__)

_encoder = None  # Lazy-loaded sentence transformer


def _get_encoder():
    """Return a cached SentenceTransformer instance (lazy load)."""
    global _encoder
    if _encoder is None:
        from sentence_transformers import SentenceTransformer

        _encoder = SentenceTransformer("all-MiniLM-L6-v2")
    return _encoder


def _embed(text_: str) -> List[float]:
    """Return a normalised 384-dim embedding for *text_*."""
    enc = _get_encoder()
    vector = enc.encode(text_, normalize_embeddings=True)
    return vector.tolist()


async def search_customer_context(
    query: str,
    shop_id: Optional[int] = None,
    session_id: Optional[str] = None,
    k: int = 5,
    min_similarity: float = 0.30,
) -> List[Dict[str, Any]]:
    """
    Semantic search over conversation_history using pgvector cosine similarity.

    Args:
        query: Natural-language query to embed and match against stored messages.
        shop_id: Optional filter — only return messages from sessions that belong
                 to this shop (matched via QueueItem → Queue.shop_id through a
                 session_id naming convention of "shop_{shop_id}_*").
        session_id: Optional exact session_id filter.
        k: Maximum number of results to return.
        min_similarity: Cosine similarity threshold (0–1). Lower = more results.

    Returns:
        List of dicts: {id, session_id, role, content, created_at, similarity}
    """
    try:
        embedding = await asyncio.get_event_loop().run_in_executor(None, _embed, query)
        embedding_str = "[" + ",".join(f"{v:.8f}" for v in embedding) + "]"
    except Exception as exc:
        logger.error("SearchCustomerContext: embedding failed: %s", exc)
        return []

    # Build query — cosine similarity = 1 - cosine_distance
    sql_parts = [
        "SELECT id, session_id, role, content, created_at,",
        "       1 - (embedding <=> :emb::vector) AS similarity",
        "FROM conversation_history",
        "WHERE embedding IS NOT NULL",
        "  AND 1 - (embedding <=> :emb::vector) >= :min_sim",
    ]
    params: Dict[str, Any] = {"emb": embedding_str, "min_sim": min_similarity}

    if session_id:
        sql_parts.append("  AND session_id = :sid")
        params["sid"] = session_id
    elif shop_id is not None:
        # session_ids for a shop follow the pattern "shop_{shop_id}_*"
        sql_parts.append("  AND session_id LIKE :sid_pattern")
        params["sid_pattern"] = f"shop_{shop_id}_%"

    sql_parts += [
        "ORDER BY embedding <=> :emb::vector",
        "LIMIT :k",
    ]
    params["k"] = k

    sql = "\n".join(sql_parts)

    try:
        db = SessionLocal()
        try:
            rows = db.execute(text(sql), params).fetchall()
            return [
                {
                    "id": r.id,
                    "session_id": r.session_id,
                    "role": r.role,
                    "content": r.content,
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                    "similarity": round(float(r.similarity), 4),
                }
                for r in rows
            ]
        finally:
            db.close()
    except Exception as exc:
        logger.error("SearchCustomerContext: DB query failed: %s", exc)
        return []
