import os
import shutil
import uuid

from fastapi import APIRouter, File, UploadFile, HTTPException
from pydantic import BaseModel, Field

from app.tasks.halalscan_tasks import process_halal_scan
from app.services.firebase_service import get_halal_status_by_id
from typing import Any

# Define API Router
router = APIRouter()

process_halal_scan: Any

# Define Data Models
class HalalScanResponse(BaseModel):
    task_id: str = Field(..., description="Unique ID for the background task.")
    status: str = Field(..., description="Current status of the task (e.g., 'processing').")
    message: str = Field(..., description="User-friendly message about the task status.")

class HalalScanStatus(BaseModel):
    status: str = Field(..., description="Final status of the HalalScan (e.g., 'completed', 'failed').")
    result: dict | None = Field(None, description="The result data, if the task is completed.")

# API Endpoint
@router.post("/", response_model=HalalScanResponse)
async def scan_halal_product(file: UploadFile = File(...)):
    """
    Endpoint for HalalScan feature. Receives an image file, saves it,
    and dispatches a background task to process it.
    """
    task_id = str(uuid.uuid4())
    UPLOAD_DIR = os.path.join(os.getcwd(), "uploads")
    os.makedirs(UPLOAD_DIR, exist_ok=True)

    file_path = os.path.join(UPLOAD_DIR, f"{task_id}.jpeg")

    try:
        # simpan file
        with open(file_path, "wb") as buffer:
            buffer.write(await file.read())

        # Ensure Celery task can be called
        if 'delay' not in dir(process_halal_scan):
            raise RuntimeError("Celery task 'process_halal_scan' is not properly configured. Is Redis/Celery running?")
            
        # Dispatch the long-running task to Celery
        process_halal_scan.delay(task_id, file_path)
        
        return HalalScanResponse(
            task_id=task_id, 
            status="processing", 
            message="Permintaan pemindaian diterima. Status dapat dicek secara berkala."
        )
    except Exception as e:
        # Clean up the temporary file if an error occurred
        if os.path.exists(file_path):
            os.remove(file_path)
        raise HTTPException(status_code=500, detail=f"Terjadi kesalahan saat memproses permintaan: {e}")

@router.get("/{task_id}")
async def get_scan_status(task_id: str):
    """
    Endpoint to check the status of a HalalScan task.
    """
    result = await get_halal_status_by_id(task_id)
    
    if result:
        return HalalScanStatus(status="completed", result=result)
    else:
        return HalalScanStatus(status="processing", result=None)