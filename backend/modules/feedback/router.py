import os
import uuid
import logging
from datetime import datetime, date
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from sqlalchemy import func

from database import get_db
from shared.auth_utils import get_current_user
from modules.auth.models import User, UserRole
from modules.feedback.models import ChatFeedback
from modules.feedback.schemas import FeedbackResponse, FeedbackStatusUpdate
from services.storage_service import upload_file

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat-feedback", tags=["Chat Feedback"])

_UPLOAD_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "static", "uploads", "feedback")
_ALLOWED_IMAGE_TYPES = {"image/png", "image/jpeg", "image/jpg", "image/gif", "image/webp"}
_MAX_SCREENSHOT_BYTES = 10 * 1024 * 1024  # 10 MB


def _get_upload_dir() -> str:
    os.makedirs(_UPLOAD_DIR, exist_ok=True)
    return _UPLOAD_DIR


def _generate_ticket_id(db: Session) -> str:
    """Generate ZQ-YYYYMMDD-NNNN ticket ID (sequential within day)."""
    today_str = date.today().strftime("%Y%m%d")
    prefix = f"ZQ-{today_str}-"
    count = db.query(func.count(ChatFeedback.id)).filter(
        ChatFeedback.ticket_id.like(f"{prefix}%")
    ).scalar() or 0
    return f"{prefix}{count + 1:04d}"


def _require_super_admin(current_user: User = Depends(get_current_user)):
    if current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return current_user


# ── Public: submit feedback ────────────────────────────────────────────────────

@router.post("/submit")
async def submit_feedback(
    description: str = Form(...),
    session_id: Optional[str] = Form(None),
    name: Optional[str] = Form(None),
    email: Optional[str] = Form(None),
    page_context: Optional[str] = Form(None),
    screenshot: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
):
    """Submit in-chat feedback with optional screenshot attachment."""
    screenshot_filename: Optional[str] = None

    # Validate and save screenshot
    if screenshot and screenshot.filename:
        if screenshot.content_type not in _ALLOWED_IMAGE_TYPES:
            raise HTTPException(status_code=400, detail="Screenshot must be a PNG, JPG, GIF, or WebP image")

        contents = await screenshot.read()
        if len(contents) > _MAX_SCREENSHOT_BYTES:
            raise HTTPException(status_code=400, detail="Screenshot must be smaller than 10 MB")

        ext = os.path.splitext(screenshot.filename)[-1].lower() or ".png"
        safe_ext = ext if ext in {".png", ".jpg", ".jpeg", ".gif", ".webp"} else ".png"
        unique_name = f"{uuid.uuid4().hex}{safe_ext}"
        object_key = f"feedback/screenshots/{unique_name}"

        screenshot_filename = upload_file(contents, object_key, screenshot.content_type or "application/octet-stream")
        logger.info("Feedback screenshot uploaded to object storage: %s", object_key)

    ticket_id = _generate_ticket_id(db)
    feedback = ChatFeedback(
        ticket_id=ticket_id,
        session_id=session_id,
        name=name,
        email=email,
        description=description,
        page_context=page_context,
        screenshot_filename=screenshot_filename,
        status="open",
    )
    db.add(feedback)
    db.commit()
    db.refresh(feedback)

    logger.info(f"Feedback submitted: {ticket_id}")
    return {
        "ticket_id": ticket_id,
        "message": "Thank you! Your feedback has been received.",
        "status": "open",
    }


# ── Admin: list, view, update ──────────────────────────────────────────────────

@router.get("/", response_model=List[FeedbackResponse])
def list_feedback(
    status_filter: Optional[str] = None,
    db: Session = Depends(get_db),
    _: User = Depends(_require_super_admin),
):
    """List all feedback entries (admin only). Optionally filter by status."""
    query = db.query(ChatFeedback).order_by(ChatFeedback.submitted_at.desc())
    if status_filter:
        query = query.filter(ChatFeedback.status == status_filter)
    items = query.all()
    return [_to_response(item) for item in items]


@router.get("/{ticket_id}", response_model=FeedbackResponse)
def get_feedback(
    ticket_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(_require_super_admin),
):
    """Get a single feedback entry by ticket ID (admin only)."""
    item = db.query(ChatFeedback).filter(ChatFeedback.ticket_id == ticket_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Feedback not found")
    return _to_response(item)


@router.patch("/{ticket_id}")
def update_feedback(
    ticket_id: str,
    body: FeedbackStatusUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(_require_super_admin),
):
    """Update feedback status and/or admin notes (admin only)."""
    allowed = {"open", "reviewed", "closed"}
    if body.status not in allowed:
        raise HTTPException(status_code=400, detail=f"status must be one of: {', '.join(allowed)}")

    item = db.query(ChatFeedback).filter(ChatFeedback.ticket_id == ticket_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Feedback not found")

    item.status = body.status
    if body.admin_notes is not None:
        item.admin_notes = body.admin_notes
    db.commit()
    return {"ticket_id": ticket_id, "status": item.status}


@router.get("/screenshot/{filename}")
def get_screenshot(
    filename: str,
    _: User = Depends(_require_super_admin),
):
    """Serve a feedback screenshot (admin only). Prevents path traversal."""
    # Strictly validate filename — no path separators allowed
    if "/" in filename or "\\" in filename or ".." in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")

    file_path = os.path.join(_get_upload_dir(), filename)
    if not os.path.isfile(file_path):
        raise HTTPException(status_code=404, detail="Screenshot not found")

    return FileResponse(file_path)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _to_response(item: ChatFeedback) -> FeedbackResponse:
    screenshot_url = None
    if item.screenshot_filename:
        if item.screenshot_filename.startswith(("http://", "https://")):
            screenshot_url = item.screenshot_filename
        else:
            screenshot_url = f"/api/chat-feedback/screenshot/{item.screenshot_filename}"
    return FeedbackResponse(
        id=item.id,
        ticket_id=item.ticket_id,
        session_id=item.session_id,
        name=item.name,
        email=item.email,
        description=item.description,
        page_context=item.page_context,
        screenshot_url=screenshot_url,
        status=item.status,
        admin_notes=item.admin_notes,
        submitted_at=item.submitted_at,
    )
