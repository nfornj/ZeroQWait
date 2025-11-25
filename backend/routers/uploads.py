from fastapi import APIRouter, UploadFile, File, HTTPException
import shutil
import os
import uuid
from typing import Optional

router = APIRouter()

UPLOAD_DIR = "static/uploads"

@router.post("/logo")
async def upload_logo(file: UploadFile = File(...)):
    """Upload a shop logo"""
    # Validate file type
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")
    
    # Generate unique filename
    file_extension = os.path.splitext(file.filename)[1]
    filename = f"{uuid.uuid4()}{file_extension}"
    file_path = os.path.join(UPLOAD_DIR, filename)
    
    # Save file
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Could not save file: {str(e)}")
        
    # Return URL
    # Assuming the server is running on localhost:8000 for now. 
    # In production, this should be an env var or constructed dynamically.
    return {"url": f"http://localhost:8000/static/uploads/{filename}"}
