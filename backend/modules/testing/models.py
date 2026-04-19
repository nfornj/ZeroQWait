from sqlalchemy import Column, String, Integer, Text, DateTime, Boolean
from sqlalchemy.sql import func
from database import Base


class TestingFeedback(Base):
    """Store testing feedback from QA testers"""
    __tablename__ = "testing_feedback"
    
    id = Column(Integer, primary_key=True, index=True)
    tester_name = Column(String(255), nullable=False)
    tester_email = Column(String(255), nullable=False, index=True)
    test_scenario = Column(String(50), nullable=False)  # customer_queue, employee_dashboard, owner_dashboard, ai_chat, voice_mode, all
    overall_rating = Column(Integer, nullable=False)  # 1-5
    feedback_text = Column(Text, nullable=False)
    issues_found = Column(Text, nullable=True)
    suggestions = Column(Text, nullable=True)
    allow_follow_up = Column(Boolean, default=False)
    submitted_at = Column(DateTime(timezone=True), server_default=func.now())
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    def __repr__(self):
        return f"<TestingFeedback(id={self.id}, tester_name='{self.tester_name}', rating={self.overall_rating})>"
