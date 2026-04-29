"""
Owner document storage helpers — upload, extraction, chunking, indexing.

Extracted from backend/routers/agent_v2.py to keep the HTTP boundary file focused
on FastAPI routing concerns.
"""

import os
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import HTTPException

from modules.agent.models import AgentDocument, AgentMemory

# ---------------------------------------------------------------------------
# Document constraints
# ---------------------------------------------------------------------------

OWNER_DOCUMENT_MAX_BYTES = 2 * 1024 * 1024
OWNER_DOCUMENT_MAX_FILES = 25
OWNER_DOCUMENT_ALLOWED_EXTENSIONS = {
    ".txt",
    ".md",
    ".markdown",
    ".csv",
    ".json",
    ".html",
    ".htm",
    ".xml",
    ".yml",
    ".yaml",
    ".tsv",
}
OWNER_DOCUMENT_ALLOWED_MIME_TYPES = {
    "text/plain",
    "text/markdown",
    "text/csv",
    "text/tab-separated-values",
    "application/json",
    "application/ld+json",
    "text/html",
    "application/xml",
    "text/xml",
    "application/x-yaml",
    "text/yaml",
}
OWNER_DOCUMENT_CHUNK_SIZE = 1200
OWNER_DOCUMENT_CHUNK_OVERLAP = 200

# Aliases to keep agent_v2.py internal names working during the transition
_OWNER_DOCUMENT_MAX_BYTES = OWNER_DOCUMENT_MAX_BYTES
_OWNER_DOCUMENT_MAX_FILES = OWNER_DOCUMENT_MAX_FILES
_OWNER_DOCUMENT_ALLOWED_EXTENSIONS = OWNER_DOCUMENT_ALLOWED_EXTENSIONS
_OWNER_DOCUMENT_ALLOWED_MIME_TYPES = OWNER_DOCUMENT_ALLOWED_MIME_TYPES
_OWNER_DOCUMENT_CHUNK_SIZE = OWNER_DOCUMENT_CHUNK_SIZE
_OWNER_DOCUMENT_CHUNK_OVERLAP = OWNER_DOCUMENT_CHUNK_OVERLAP


# ---------------------------------------------------------------------------
# Name / path sanitisation
# ---------------------------------------------------------------------------

def _sanitize_document_name(raw_name: Optional[str], fallback: str = "document.txt") -> str:
    cleaned = (raw_name or fallback).replace("\\", "/").split("/")[-1].strip()
    return cleaned or fallback


def _sanitize_relative_document_path(raw_path: Optional[str], fallback_name: str) -> str:
    candidate = (raw_path or "").replace("\\", "/").strip()
    parts = [part for part in candidate.split("/") if part and part not in {".", ".."}]
    if not parts:
        return fallback_name
    return "/".join(parts)[:500]


# ---------------------------------------------------------------------------
# Text extraction and chunking
# ---------------------------------------------------------------------------

def _extract_owner_document_text(file_bytes: bytes, *, filename: str, content_type: str) -> str:
    if not file_bytes:
        raise HTTPException(status_code=400, detail=f"{filename}: file is empty")

    lowered = filename.lower()
    extension = os.path.splitext(lowered)[1]
    normalized_type = (content_type or "").split(";")[0].strip().lower()

    if extension not in OWNER_DOCUMENT_ALLOWED_EXTENSIONS and normalized_type not in OWNER_DOCUMENT_ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=400,
            detail=(
                f"{filename}: unsupported file type. Upload text, markdown, CSV, JSON, HTML, XML, or YAML documents."
            ),
        )

    if b"\x00" in file_bytes[:4096]:
        raise HTTPException(status_code=400, detail=f"{filename}: binary files are not supported yet")

    for encoding in ("utf-8-sig", "utf-8", "utf-16"):
        try:
            text = file_bytes.decode(encoding)
            break
        except UnicodeDecodeError:
            text = ""
    else:
        raise HTTPException(status_code=400, detail=f"{filename}: file encoding is not supported")

    normalized = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not normalized:
        raise HTTPException(status_code=400, detail=f"{filename}: no readable text content found")
    return normalized


def _chunk_owner_document_text(text: str) -> List[str]:
    if len(text) <= OWNER_DOCUMENT_CHUNK_SIZE:
        return [text]

    chunks: List[str] = []
    step = OWNER_DOCUMENT_CHUNK_SIZE - OWNER_DOCUMENT_CHUNK_OVERLAP
    for start in range(0, len(text), step):
        chunk = text[start:start + OWNER_DOCUMENT_CHUNK_SIZE].strip()
        if chunk:
            chunks.append(chunk)
    return chunks or [text]


# ---------------------------------------------------------------------------
# Serialisation
# ---------------------------------------------------------------------------

def _serialize_owner_document(document: AgentDocument, *, duplicate: bool = False) -> Dict[str, Any]:
    return {
        "id": document.id,
        "filename": document.filename,
        "relative_path": document.relative_path,
        "size_bytes": document.size_bytes,
        "content_type": document.content_type,
        "knowledge_status": document.knowledge_status,
        "chunk_count": document.chunk_count,
        "created_at": document.created_at.isoformat() if document.created_at else None,
        "updated_at": document.updated_at.isoformat() if document.updated_at else None,
        "duplicate": duplicate,
    }


# ---------------------------------------------------------------------------
# Memory / DB helpers
# ---------------------------------------------------------------------------

def _document_memory_query(db, *, shop_id: int, document_id: int):
    return db.query(AgentMemory).filter(
        AgentMemory.shop_id == shop_id,
        AgentMemory.memory_type == "document",
        AgentMemory.memory_meta["document_id"].as_integer() == document_id,
    )


def _reindex_owner_document_in_session(
    db,
    *,
    document: AgentDocument,
    shop_id: int,
) -> int:
    extracted_text = document.extracted_text or _extract_owner_document_text(
        document.file_blob,
        filename=document.filename,
        content_type=document.content_type,
    )
    chunks = _chunk_owner_document_text(extracted_text)
    relative_path = document.relative_path or document.filename

    _document_memory_query(db, shop_id=shop_id, document_id=document.id).delete(synchronize_session=False)

    for chunk_index, chunk in enumerate(chunks, start=1):
        db.add(
            AgentMemory(
                shop_id=shop_id,
                user_id=None,
                memory_type="document",
                content=f"From {relative_path} (chunk {chunk_index}/{len(chunks)}): {chunk}",
                source=relative_path,
                importance_score=0.82,
                memory_meta={
                    "document_id": document.id,
                    "filename": document.filename,
                    "relative_path": relative_path,
                    "chunk_index": chunk_index,
                    "chunk_count": len(chunks),
                    "checksum": document.checksum,
                },
                is_active=True,
                created_at=datetime.utcnow(),
            )
        )

    document.extracted_text = extracted_text
    document.chunk_count = len(chunks)
    document.knowledge_status = "indexed"
    document.updated_at = datetime.utcnow()
    db.flush()
    return len(chunks)


def _get_owner_document_or_404(db, *, shop_id: int, document_id: int) -> AgentDocument:
    document = (
        db.query(AgentDocument)
        .filter(
            AgentDocument.id == document_id,
            AgentDocument.shop_id == shop_id,
        )
        .first()
    )
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    return document
