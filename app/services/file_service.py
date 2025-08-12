import os
import uuid
from fastapi import UploadFile, HTTPException
from typing import Optional
import aiofiles
from datetime import datetime

# Configure upload directories
UPLOAD_BASE_DIR = "uploads"
ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
ALLOWED_DOCUMENT_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png"}

# Create upload directories if they don't exist
os.makedirs(f"{UPLOAD_BASE_DIR}/avatars", exist_ok=True)
os.makedirs(f"{UPLOAD_BASE_DIR}/valid_ids", exist_ok=True)
os.makedirs(f"{UPLOAD_BASE_DIR}/farm_images", exist_ok=True)


async def upload_file(file: UploadFile, folder: str) -> str:
    # Validate file extension based on folder
    file_extension = os.path.splitext(file.filename)[1].lower()
    
    if folder == "avatars":
        if file_extension not in ALLOWED_IMAGE_EXTENSIONS:
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid file type. Allowed types: {', '.join(ALLOWED_IMAGE_EXTENSIONS)}"
            )
    elif folder == "valid_ids":
        if file_extension not in ALLOWED_DOCUMENT_EXTENSIONS:
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid file type. Allowed types: {', '.join(ALLOWED_DOCUMENT_EXTENSIONS)}"
            )
    elif folder == "farm_images":
        if file_extension not in ALLOWED_IMAGE_EXTENSIONS:
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid file type. Allowed types: {', '.join(ALLOWED_IMAGE_EXTENSIONS)}"
            )
    
    # Generate unique filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    unique_id = str(uuid.uuid4())[:8]
    filename = f"{timestamp}_{unique_id}{file_extension}"
    
    file_path = os.path.join(UPLOAD_BASE_DIR, folder, filename)
    
    # Save file
    try:
        async with aiofiles.open(file_path, 'wb') as f:
            content = await file.read()
            await f.write(content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save file: {str(e)}")
    
    # Return relative path for storage in database
    return f"/{file_path.replace(os.sep, '/')}"


async def delete_file(file_url: str) -> bool:
    try:
        # Remove leading slash and convert to local path
        local_path = file_url.lstrip('/').replace('/', os.sep)
        if os.path.exists(local_path):
            os.remove(local_path)
            return True
        return False
    except Exception:
        return False


def get_file_size_mb(file: UploadFile) -> float:

    # Reset file pointer to beginning
    file.seek(0, 2)  # Seek to end
    size_bytes = file.tell()
    file.seek(0)  # Reset to beginning
    return size_bytes / (1024 * 1024)


def validate_file_size(file: UploadFile, max_size_mb: float = 10.0) -> bool:
    file_size_mb = get_file_size_mb(file)
    return file_size_mb <= max_size_mb 