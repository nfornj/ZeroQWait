import bcrypt
from jose import JWTError, jwt
from datetime import datetime, timedelta
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer
from typing import Optional
import os
from dotenv import load_dotenv
from modules.auth import schemas

load_dotenv()

# Secret key and algorithm for JWT
SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    raise ValueError("No SECRET_KEY set for Flask application. Did you forget to set it in .env?")
    
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

# Use auto_error=False to allow manual handling (cookie check)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/token", auto_error=False)
oauth2_scheme_optional = OAuth2PasswordBearer(tokenUrl="api/token", auto_error=False)


def _to_bytes(value: str | bytes) -> bytes:
    return value if isinstance(value, bytes) else value.encode("utf-8")

def verify_password(plain_password, hashed_password):
    if not plain_password or not hashed_password:
        return False
    try:
        return bcrypt.checkpw(_to_bytes(plain_password), _to_bytes(hashed_password))
    except ValueError:
        return False

def get_password_hash(password):
    return bcrypt.hashpw(_to_bytes(password), bcrypt.gensalt()).decode("utf-8")

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def get_current_user(request: Request, token: str = Depends(oauth2_scheme)):
    # Local import to avoid circular dependency
    from modules.auth.service import auth_service
    
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    # Check cookie if header token is missing
    if not token:
        token = request.cookies.get("access_token")
        
    if not token:
        raise credentials_exception
        
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        token_data = schemas.TokenData(username=username)
    except JWTError:
        raise credentials_exception
    
    try:
        from database import set_current_user_for_request
        user = auth_service.get_user_by_username(token_data.username)
        if not user:
            raise credentials_exception
        set_current_user_for_request(user.id)
        return user
    except HTTPException:
        raise
    except Exception:
        raise credentials_exception

def get_current_active_user(current_user: schemas.User = Depends(get_current_user)):
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user

def get_current_user_optional(token: Optional[str] = Depends(oauth2_scheme_optional)) -> Optional[schemas.User]:
    """
    Optional authentication - returns user if authenticated, None if not.
    Does not raise exception for missing/invalid tokens.
    """
    # Local import
    from modules.auth.service import auth_service
    
    if not token:
        return None
    
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            return None
        
        user = auth_service.get_user_by_username(username)
        if not user:
            return None
        
        return user
    except JWTError:
        return None
    except Exception:
        return None
