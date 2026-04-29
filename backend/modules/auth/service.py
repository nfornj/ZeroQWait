from sqlalchemy.orm import Session
from database import SessionLocal
from modules.auth.models import User
from modules.auth import schemas
from shared.auth_utils import verify_password, get_password_hash
from typing import Optional

class AuthService:
    def get_db(self):
        return SessionLocal()

    def get_user_by_username(self, username: str) -> schemas.User:
        db = self.get_db()
        try:
            user = db.query(User).filter(User.username == username).first()
            if user:
                 return schemas.User.model_validate(user)
            return None
        finally:
            db.close()

    def get_user_by_email(self, email: str) -> schemas.User:
        db = self.get_db()
        try:
            user = db.query(User).filter(User.email == email).first()
            if user:
                return schemas.User.model_validate(user)
            return None
        finally:
            db.close()

    def get_user_by_id(self, user_id: int) -> Optional[schemas.User]:
        db = self.get_db()
        try:
            user = db.query(User).filter(User.id == user_id).first()
            if user:
                return schemas.User.model_validate(user)
            return None
        finally:
            db.close()


    def create_user(self, user_create: schemas.UserCreate) -> schemas.User:
        db = self.get_db()
        try:
            hashed_password = get_password_hash(user_create.password)
            db_user = User(
                email=user_create.email,
                username=user_create.username,
                hashed_password=hashed_password,
                role=user_create.role
            )
            db.add(db_user)
            db.commit()
            db.refresh(db_user)
            return schemas.User.model_validate(db_user)
        finally:
            db.close()

    def authenticate_user(self, username: str, password: str):
        # We need raw DB object for password check usually? 
        # No, schemas.User doesn't have password.
        # We need to query DB directly here anyway.
        db = self.get_db()
        try:
            # Try finding by username first
            user = db.query(User).filter(User.username == username).first()
            
            # If not found, try finding by email
            if not user:
                user = db.query(User).filter(User.email == username).first()
                
            if not user:
                return False
            
            if not verify_password(password, user.hashed_password):
                return False
                
            # Return dict or schema? 
            # auth_utils returned dict or object behaving like dict.
            # We return schema.
            return schemas.User.model_validate(user)
        finally:
            db.close()

    def update_user_password(self, user_id: int, new_password: str) -> bool:
        db = self.get_db()
        try:
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                return False
            user.hashed_password = get_password_hash(new_password)
            db.commit()
            return True
        except Exception:
            db.rollback()
            return False
        finally:
            db.close()

auth_service = AuthService()
