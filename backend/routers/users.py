from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from database import get_db
import models
import schemas
from auth_utils import get_password_hash, get_current_active_user

router = APIRouter()

@router.post("/users", response_model=schemas.User)
def create_user(user: schemas.UserCreate, db: Session = Depends(get_db)):
    # Check if email already exists
    db_user_email = db.query(models.User).filter(models.User.email == user.email).first()
    if db_user_email:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Check if username already exists
    db_user_username = db.query(models.User).filter(models.User.username == user.username).first()
    if db_user_username:
        raise HTTPException(status_code=400, detail="Username already taken")
    
    # Create new user
    hashed_password = get_password_hash(user.password)
    db_user = models.User(
        email=user.email,
        username=user.username,
        hashed_password=hashed_password
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

@router.get("/users/me", response_model=schemas.UserWithFavorites)
def read_users_me(current_user: models.User = Depends(get_current_active_user)):
    return current_user

@router.post("/users/favorites/{haircut_id}")
def add_favorite(
    haircut_id: int,
    current_user: models.User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    haircut = db.query(models.HaircutService).filter(models.HaircutService.id == haircut_id).first()
    if not haircut:
        raise HTTPException(status_code=404, detail="Haircut service not found")
    
    if haircut in current_user.favorites:
        raise HTTPException(status_code=400, detail="Haircut service already in favorites")
    
    current_user.favorites.append(haircut)
    db.commit()
    return {"message": "Haircut service added to favorites"}

@router.delete("/users/favorites/{haircut_id}")
def remove_favorite(
    haircut_id: int,
    current_user: models.User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    haircut = db.query(models.HaircutService).filter(models.HaircutService.id == haircut_id).first()
    if not haircut:
        raise HTTPException(status_code=404, detail="Haircut service not found")
    
    if haircut not in current_user.favorites:
        raise HTTPException(status_code=400, detail="Haircut service not in favorites")
    
    current_user.favorites.remove(haircut)
    db.commit()
    return {"message": "Haircut service removed from favorites"}

@router.get("/users/favorites", response_model=List[schemas.HaircutService])
def get_favorites(current_user: models.User = Depends(get_current_active_user)):
    return current_user.favorites 