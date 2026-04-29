from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime


class FeedbackSubmit(BaseModel):
    session_id: Optional[str] = None
    name: Optional[str] = None
    email: Optional[str] = None
    description: str
    page_context: Optional[str] = None


class FeedbackResponse(BaseModel):
    id: int
    ticket_id: str
    session_id: Optional[str]
    name: Optional[str]
    email: Optional[str]
    description: str
    page_context: Optional[str]
    screenshot_url: Optional[str]
    status: str
    admin_notes: Optional[str]
    submitted_at: datetime

    model_config = ConfigDict(from_attributes=True)


class FeedbackStatusUpdate(BaseModel):
    status: str  # open | reviewed | closed
    admin_notes: Optional[str] = None
