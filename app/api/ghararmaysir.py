import os
import shutil
import uuid
import asyncio

from fastapi import APIRouter, File, UploadFile, HTTPException
from pydantic import BaseModel, Field

from app.tasks.ghararmaysir_tasks import process_contract_analysis # Import the Celery task
from app.services.firebase_service import get_contract_analysis_by_id # Import Firebase services
from typing import Any

process_contract_analysis: Any

# --- Define API Router ---
router = APIRouter()

# --- Define Data Models ---
class ContractAnalysisResponse(BaseModel):
    task_id: str = Field(..., description="Unique ID for the background task.")
    status: str = Field(..., description="Current status of the task (e.g., 'processing').")
    message: str = Field(..., description="User-friendly message about the task status.")

class ContractAnalysisStatus(BaseModel):
    status: str = Field(..., description="Final status of the contract analysis (e.g., 'completed', 'failed').")
    result: dict | None = Field(None, description="The result data, if the task is completed.")

# --- API Endpoint ---
@router.post("/", response_model=ContractAnalysisResponse)
async def analyze_document_syariah(file: UploadFile = File(...)):
    """
    Endpoint to upload and analyze a contract document (PDF/DOCX) for syariah compliance.
    """
    task_id = str(uuid.uuid4())
    filename = file.filename if file.filename is not None else ""
    file_extension = os.path.splitext(filename)[1]
    # Check for file extension validity (PDF, DOCX, etc.)
    if file_extension.lower() not in ['.pdf', '.docx']:
        raise HTTPException(status_code=400, detail="Tipe file tidak didukung. Harap unggah file PDF atau DOCX.")

    UPLOAD_DIR = os.path.join(os.getcwd(), "docs")
    os.makedirs(UPLOAD_DIR, exist_ok=True)

    file_path = os.path.join(UPLOAD_DIR, f"{uuid.uuid4()}.pdf")

    try:
        # simpan file
        with open(file_path, "wb") as buffer:
            buffer.write(await file.read())

        # Ensure Celery task can be called
        if 'delay' not in dir(process_contract_analysis):
            raise RuntimeError("Celery task 'process_halal_scan' is not properly configured. Is Redis/Celery running?")
            
        # Dispatch the long-running task to Celery
        process_contract_analysis.delay(file_path, task_id)
        
        return ContractAnalysisResponse(
            task_id=task_id, 
            status="processing", 
            message="Dokumen diterima. Analisis sedang berjalan di background."
        )
    except Exception as e:
        if os.path.exists(file_path):
            os.remove(file_path)
        raise HTTPException(status_code=500, detail=f"Terjadi kesalahan saat memproses dokumen: {e}")

@router.get("/{task_id}", response_model=ContractAnalysisStatus)
async def get_analysis_status(task_id: str):
    """
    Endpoint to check the status of a contract analysis task.
    """
    # Note: get_contract_analysis_by_id should be implemented in firebase_service.py
    result = await get_contract_analysis_by_id(task_id)
    
    if result:
        return ContractAnalysisStatus(status="completed", result=result)
    else:
        return ContractAnalysisStatus(status="processing", result=None)

