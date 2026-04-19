from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session
from database import get_db
from modules.testing.models import TestingFeedback
from modules.testing.schemas import TestingFeedbackCreate, TestingFeedback as TestingFeedbackSchema

router = APIRouter(prefix="/api/feedback", tags=["testing_feedback"])


@router.post("/submit", response_model=TestingFeedbackSchema)
async def submit_feedback(
    feedback: TestingFeedbackCreate,
    db: Session = Depends(get_db)
):
    """
    Submit testing feedback from QA testers.
    No authentication required (public endpoint for testers).
    """
    try:
        # Create feedback record
        db_feedback = TestingFeedback(
            tester_name=feedback.tester_name,
            tester_email=feedback.tester_email,
            test_scenario=feedback.test_scenario,
            overall_rating=feedback.overall_rating,
            feedback_text=feedback.feedback_text,
            issues_found=feedback.issues_found,
            suggestions=feedback.suggestions,
            allow_follow_up=feedback.allow_follow_up,
            submitted_at=feedback.submitted_at or func.now()
        )
        
        db.add(db_feedback)
        db.commit()
        db.refresh(db_feedback)
        
        return db_feedback
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save feedback: {str(e)}"
        )


@router.get("/stats")
async def get_feedback_stats(db: Session = Depends(get_db)):
    """Get summary statistics of testing feedback (admin only for now)"""
    try:
        total_feedback = db.query(func.count(TestingFeedback.id)).scalar() or 0
        
        avg_rating = db.query(func.avg(TestingFeedback.overall_rating)).scalar()
        avg_rating = float(avg_rating) if avg_rating else 0
        
        feedback_by_scenario = db.query(
            TestingFeedback.test_scenario,
            func.count(TestingFeedback.id).label("count")
        ).group_by(TestingFeedback.test_scenario).all()
        
        rating_distribution = db.query(
            TestingFeedback.overall_rating,
            func.count(TestingFeedback.id).label("count")
        ).group_by(TestingFeedback.overall_rating).all()
        
        return {
            "total_feedback": total_feedback,
            "average_rating": round(avg_rating, 2),
            "by_scenario": [{"scenario": s, "count": c} for s, c in feedback_by_scenario],
            "rating_distribution": [{"rating": r, "count": c} for r, c in rating_distribution],
            "follow_up_count": db.query(func.count(TestingFeedback.id)).filter(TestingFeedback.allow_follow_up == True).scalar() or 0
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get stats: {str(e)}"
        )


@router.get("/all")
async def get_all_feedback(db: Session = Depends(get_db)):
    """Get all feedback entries (admin only for now)"""
    try:
        feedback_list = db.query(TestingFeedback).order_by(TestingFeedback.submitted_at.desc()).all()
        return feedback_list
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve feedback: {str(e)}"
        )
