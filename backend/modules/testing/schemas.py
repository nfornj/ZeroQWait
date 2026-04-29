from pydantic import BaseModel, ConfigDict, EmailStr
from datetime import datetime
from typing import Optional


class TestingFeedbackBase(BaseModel):
    tester_name: str
    tester_email: EmailStr
    test_scenario: str
    overall_rating: int  # 1-5
    feedback_text: str
    issues_found: Optional[str] = None
    suggestions: Optional[str] = None
    allow_follow_up: bool = False


class TestingFeedbackCreate(TestingFeedbackBase):
    submitted_at: Optional[datetime] = None


class TestingFeedback(TestingFeedbackBase):
    id: int
    submitted_at: datetime
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
