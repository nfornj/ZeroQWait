from fastapi import APIRouter, UploadFile, File, HTTPException
import os
import uuid

from services.storage_service import upload_file

router = APIRouter()

@router.post("/logo")
async def upload_logo(file: UploadFile = File(...)):
    """Upload a shop logo"""
    # Validate file type
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")
    
    # Generate unique filename
    file_extension = os.path.splitext(file.filename)[1]
    filename = f"{uuid.uuid4()}{file_extension}"
    object_key = f"uploads/logos/{filename}"
    
    # Save file to object storage
    try:
        file_bytes = await file.read()
        url = upload_file(file_bytes, object_key, file.content_type or "application/octet-stream")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Could not save file: {str(e)}")
        
    return {"url": url}
