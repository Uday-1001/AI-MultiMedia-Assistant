from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, BackgroundTasks
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel
from typing import List, Optional, Dict
import os
import uuid
import shutil
from ..database.connection import get_db, SessionLocal
from ..database.models import UploadedFile, User
from ..services.transcription import transcription_service
from ..services.ingestion import ingestion_service
from ..services.embeddings import embedding_service
from ..vectorstore.chroma import chroma_service
from ..config.settings import settings

router = APIRouter(prefix="/upload", tags=["upload"])

# Global dictionary to track progress of background tasks
processing_progress: Dict[int, dict] = {}


router = APIRouter(prefix="/upload", tags=["upload"])


class UploadResponse(BaseModel):
    file_id: int
    filename: str
    file_type: str
    status: str
    message: str


class DocumentMetadata(BaseModel):
    document_id: str
    filename: str
    file_type: str
    file_size: int
    upload_date: str


@router.post("/", response_model=UploadResponse)
async def upload_file(
    file: UploadFile = File(...),
    db = Depends(get_db)
):
    """
    Accepts a multimedia file or document from the user, saves it to disk, 
    and registers it in the database for asynchronous processing.
    """
    file_type = ingestion_service.get_file_type(file.filename)
    if not file_type:
        raise HTTPException(status_code=400, detail="We don't support this file format just yet. Please try a different one.")
    
    file_id = uuid.uuid4().hex[:8]
    file_extension = os.path.splitext(file.filename)[1]
    saved_filename = f"{file_id}{file_extension}"
    save_path = os.path.join(settings.UPLOAD_DIR, saved_filename)
    
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    
    with open(save_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    file_size = os.path.getsize(save_path)
    
    database_file_record = UploadedFile(
        filename=saved_filename,
        original_filename=file.filename,
        file_type=file_type,
        file_size=file_size,
        file_path=save_path,
        status="uploaded"
    )
    db.add(database_file_record)
    db.commit()
    db.refresh(database_file_record)
    
    return UploadResponse(
        file_id=database_file_record.id,
        filename=database_file_record.original_filename,
        file_type=file_type,
        status="uploaded",
        message="File uploaded successfully. Ready for processing."
    )


@router.post("/{file_id}/process", response_model=UploadResponse)
async def process_file(file_id: int, background_tasks: BackgroundTasks, db = Depends(get_db)):
    """
    Triggers the background processing pipeline (transcription, OCR, text extraction) 
    for an uploaded file.
    """
    database_file_record = db.query(UploadedFile).filter(UploadedFile.id == file_id).first()
    if not database_file_record:
        raise HTTPException(status_code=404, detail="We couldn't locate that file. Please try uploading it again.")
    
    if database_file_record.status == "processing":
        return UploadResponse(
            file_id=database_file_record.id,
            filename=database_file_record.original_filename,
            file_type=database_file_record.file_type,
            status="processing",
            message="File is already processing."
        )

    database_file_record.status = "processing"
    db.commit()
    
    # Initialize progress store
    processing_progress[file_id] = {"current": 0, "total": 0, "status": "processing", "message": "Starting..."}
    
    background_tasks.add_task(_process_file_task, file_id)

    return UploadResponse(
        file_id=database_file_record.id,
        filename=database_file_record.original_filename,
        file_type=database_file_record.file_type,
        status="processing",
        message="File processing started in the background."
    )


class ProgressResponse(BaseModel):
    file_id: int
    status: str
    current: int
    total: int
    message: str


@router.get("/{file_id}/status", response_model=ProgressResponse)
async def get_process_status(file_id: int, db = Depends(get_db)):
    """
    Returns the real-time processing status and progress percentage of an uploaded file.
    """
    database_file_record = db.query(UploadedFile).filter(UploadedFile.id == file_id).first()
    if not database_file_record:
        raise HTTPException(status_code=404, detail="We couldn't locate that file. Please try uploading it again.")

    progress = processing_progress.get(file_id, {"current": 0, "total": 0, "status": database_file_record.status, "message": ""})
    
    # If the DB says error but progress dictionary hasn't caught up (or was cleared)
    if database_file_record.status == "error":
        return ProgressResponse(file_id=file_id, status="error", current=0, total=0, message=database_file_record.processing_error or "Unknown error")
    
    # If the DB says processed
    if database_file_record.status == "processed":
        return ProgressResponse(file_id=file_id, status="processed", current=progress["total"], total=progress["total"], message="Done")
        
    return ProgressResponse(file_id=file_id, status=database_file_record.status, current=progress["current"], total=progress["total"], message=progress["message"])

@router.get("/{file_id}/view")
async def view_uploaded_file(file_id: int, db = Depends(get_db)):
    """
    Serves the original uploaded file so the user can open or preview it directly in the browser.
    """
    database_file_record = db.query(UploadedFile).filter(UploadedFile.id == file_id).first()
    if not database_file_record:
        raise HTTPException(status_code=404, detail="We couldn't locate that file.")
    if not os.path.exists(database_file_record.file_path):
        raise HTTPException(status_code=404, detail="The file no longer exists on disk.")
    return FileResponse(
        path=database_file_record.file_path,
        filename=database_file_record.original_filename,
        media_type="application/octet-stream"
    )


def _process_file_task(file_id: int):
    """Background task that handles transcription, OCR, and indexing."""
    db = SessionLocal()
    try:
        database_file_record = db.query(UploadedFile).filter(UploadedFile.id == file_id).first()
        if not database_file_record:
            return

        def update_progress(current: int, total: int, progress_message: str = ""):
            processing_progress[file_id] = {"current": current, "total": total, "status": "processing", "message": progress_message}

        if database_file_record.file_type == "video":
            update_progress(0, 100, "🎬 Listening to video and creating transcript...")
            transcript, transcript_path, segments = transcription_service.transcribe_video(
                database_file_record.file_path, settings.TRANSCRIPT_DIR
            )
            database_file_record.transcript_path = transcript_path
        elif database_file_record.file_type == "audio":
            update_progress(0, 100, "🎧 Listening to audio and creating transcript...")
            transcript, transcript_path, segments = transcription_service.transcribe_audio_file(
                database_file_record.file_path, settings.TRANSCRIPT_DIR
            )
            database_file_record.transcript_path = transcript_path
        else:
            segments = None
            update_progress(0, 100, "📄 Extracting text from document...")
        
        documents = ingestion_service.process_document(
            file_path=database_file_record.file_path,
            file_id=database_file_record.id,
            filename=database_file_record.original_filename,
            file_type=database_file_record.file_type,
            transcript_path=database_file_record.transcript_path,
            segment_timestamps=segments,
            progress_callback=update_progress
        )
        
        texts = [document.page_content for document in documents]
        metadatas = [document.metadata for document in documents]
        ids = [f"{database_file_record.id}_{i}" for i in range(len(documents))]

        # Guard: nothing to index — file produced no extractable text
        if not texts:
            raise Exception("No text could be extracted from this file, even after attempting OCR. The file may be heavily corrupted, password-protected, or contain only images with no recognisable characters.")

        update_progress(99, 100, "🧠 Organizing knowledge base...")

        if chroma_service.vectorstore is None:
            embedding_service.get_embeddings()
            chroma_service.initialize(embedding_service.get_embeddings())

        chroma_service.add_documents(texts, metadatas, ids)
        
        database_file_record.status = "processed"
        database_file_record.processing_error = None
        db.commit()
        
        update_progress(100, 100, "Done")

    except Exception as processing_error:
        db.rollback()
        database_file_record = db.query(UploadedFile).filter(UploadedFile.id == file_id).first()
        if database_file_record:
            database_file_record.status = "error"
            database_file_record.processing_error = str(processing_error)
            db.commit()
        processing_progress[file_id] = {"current": 0, "total": 0, "status": "error", "message": str(processing_error)}
    finally:
        db.close()