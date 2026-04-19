from sqlalchemy import Column, String, Integer, Text, DateTime
from sqlalchemy.sql import func
from database import Base


class ChatFeedback(Base):
    """In-chat feedback submitted via /feedback command — stores issue description + screenshot."""
    __tablename__ = "chat_feedback"

    id = Column(Integer, primary_key=True, index=True)
    ticket_id = Column(String(25), unique=True, nullable=False, index=True)  # ZQ-20260419-0001
    session_id = Column(String(255), nullable=True, index=True)
    name = Column(String(255), nullable=True)
    email = Column(String(255), nullable=True)
    description = Column(Text, nullable=False)
    page_context = Column(String(100), nullable=True)   # e.g. "landing_page", "shop_page"
    screenshot_filename = Column(String(500), nullable=True)  # relative path under static/uploads/feedback/
    status = Column(String(20), nullable=False, default="open")  # open | reviewed | closed
    admin_notes = Column(Text, nullable=True)
    submitted_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"<ChatFeedback(ticket_id='{self.ticket_id}', status='{self.status}')>"
