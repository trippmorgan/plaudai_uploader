"""
PlaudAI Uploader - FastAPI Main Application
"""
import time
import uuid
import logging
from typing import List, Optional
from datetime import datetime

from fastapi import FastAPI, Depends, HTTPException, status, UploadFile, File, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

# Imports from local modules
from .db import Base, engine, get_db, check_connection, init_db
from .config import API_HOST, API_PORT, DEBUG
from .logging_config import configure_logging  # <--- NEW IMPORT
from .models import Patient, VoiceTranscript, PVIProcedure
from .schemas import (
    PatientCreate, PatientResponse,
    TranscriptUpload, TranscriptResponse,
    PVIProcedureResponse,
    UploadResponse,
    BatchUploadRequest, BatchUploadResponse
)
from .services.uploader import (
    upload_transcript,
    batch_upload_transcripts,
    get_patient_transcripts,
    get_patient_procedures,
    search_patients
)
from .services.gemini_synopsis import (
    generate_clinical_synopsis,
    get_latest_synopsis,
    get_all_synopses,
    get_patient_summary
)

# ==================== Logging Setup ====================
# Initialize detailed logging configuration
configure_logging()
logger = logging.getLogger(__name__)

# ==================== App Initialization ====================
app = FastAPI(
    title="PlaudAI Uploader",
    description="Voice transcript upload and processing for Surgical Command Center",
    version="1.1.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# ==================== Middleware ====================

# 1. Logging Middleware (Insert this FIRST)
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """
    Middleware to log every request, response time, and status code.
    Generates a unique Request ID for tracing.
    """
    request_id = str(uuid.uuid4())[:8]
    start_time = time.time()
    
    # Log Request Start
    logger.info(f"➡️ [{request_id}] {request.method} {request.url.path}")
    
    try:
        response = await call_next(request)
        
        # Log Response Success
        process_time = (time.time() - start_time) * 1000
        logger.info(
            f"⬅️ [{request_id}] {response.status_code} - {process_time:.2f}ms"
        )
        return response
        
    except Exception as e:
        # Log Unexpected Errors
        process_time = (time.time() - start_time) * 1000
        logger.error(
            f"❌ [{request_id}] FAILED - {process_time:.2f}ms - Error: {str(e)}", 
            exc_info=True
        )
        raise

# 2. CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify actual origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==================== Startup & Health ====================

@app.on_event("startup")
async def startup_event():
    """Initialize database on startup"""
    logger.info("🚀 Starting PlaudAI Uploader API...")
    
    # Check database connection
    if not check_connection():
        logger.critical("❌ Database connection failed! Application cannot start.")
        raise RuntimeError("Cannot connect to database")
    
    # Initialize tables
    try:
        init_db()
        logger.info("✅ Database initialized successfully")
    except Exception as e:
        logger.critical(f"❌ Database initialization failed: {e}")
        raise
    
    logger.info("✅ PlaudAI Uploader API ready to accept connections")

@app.get("/")
async def root():
    """Health check and API info"""
    return {
        "service": "PlaudAI Uploader",
        "version": "1.1.0",
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "database": "connected",
        "endpoints": {
            "upload": "/upload",
            "batch_upload": "/batch-upload",
            "patients": "/patients",
            "transcripts": "/transcripts",
            "procedures": "/procedures"
        }
    }

@app.get("/health")
async def health_check(db: Session = Depends(get_db)):
    """Detailed health check"""
    try:
        # Test database query using text() for SQLAlchemy 2.x compatibility
        from sqlalchemy import text
        db.execute(text("SELECT 1"))
        db_status = "healthy"
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        db_status = f"unhealthy: {str(e)}"
    
    return {
        "status": "healthy" if db_status == "healthy" else "degraded",
        "database": db_status,
        "timestamp": datetime.now().isoformat()
    }

# ==================== Upload Endpoints ====================

@app.post("/upload", response_model=UploadResponse)
async def upload_note(
    data: TranscriptUpload,
    db: Session = Depends(get_db)
):
    """
    Upload a PlaudAI transcript (raw transcript + optional formatted note)
    """
    try:
        logger.info(f"Processing upload for MRN: {data.athena_mrn}")
        
        patient_data = {
            "first_name": data.first_name,
            "last_name": data.last_name,
            "dob": data.dob,
            "athena_mrn": data.athena_mrn,
            "birth_sex": data.birth_sex,
            "race": data.race,
            "zip_code": data.zip_code
        }
        
        result = upload_transcript(
            db,
            patient_data=patient_data,
            raw_transcript=data.raw_transcript,
            plaud_note=data.plaud_note,
            title=data.transcript_title,
            visit_type=data.visit_type,
            recording_duration=data.recording_duration,
            recording_date=data.recording_date,
            plaud_recording_id=data.plaud_recording_id,
            auto_process=True
        )
        
        warnings = []
        if result["confidence_score"] < 0.5:
            warnings.append("Low confidence score - manual review recommended")
        if result["pvi_fields_extracted"] < 5:
            warnings.append("Few PVI fields extracted - consider adding more detail")
        if not result["has_plaud_note"]:
            warnings.append("No PlaudAI formatted note provided - using raw transcript only")
        
        logger.info(f"Upload successful for Patient ID: {result['patient_id']}, Transcript ID: {result['transcript_id']}")
        
        return UploadResponse(
            status="success",
            message=f"Transcript uploaded successfully",
            patient_id=result["patient_id"],
            transcript_id=result["transcript_id"],
            tags=result["tags"],
            confidence_score=result["confidence_score"],
            warnings=warnings if warnings else None
        )
    
    except Exception as e:
        logger.error(f"Upload failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@app.post("/batch-upload", response_model=BatchUploadResponse)
async def batch_upload(
    request: BatchUploadRequest,
    db: Session = Depends(get_db)
):
    """Upload multiple transcripts in batch"""
    try:
        logger.info(f"Starting batch upload of {len(request.items)} items")
        items = [
            {
                "patient_data": item.patient_data.dict(),
                "transcript_text": item.transcript_text,
                "title": item.transcript_title
            }
            for item in request.items
        ]
        
        result = batch_upload_transcripts(db, items)
        logger.info(f"Batch completed: {result['successful']} success, {result['failed']} failed")
        
        return BatchUploadResponse(
            status="completed",
            total=result["total"],
            successful=result["successful"],
            failed=result["failed"],
            results=result["details"]
        )
    
    except Exception as e:
        logger.error(f"Batch upload failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@app.post("/upload-file")
async def upload_file(
    file: UploadFile = File(...),
    first_name: str = "",
    last_name: str = "",
    dob: str = "",
    athena_mrn: str = "",
    db: Session = Depends(get_db)
):
    """Upload transcript from file (TXT, MD, JSON)"""
    try:
        logger.info(f"Received file upload: {file.filename} for MRN: {athena_mrn}")
        content = await file.read()
        text = content.decode('utf-8')
        
        if not all([first_name, last_name, dob, athena_mrn]):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing required patient information"
            )
        
        from datetime import datetime
        upload_data = TranscriptUpload(
            first_name=first_name,
            last_name=last_name,
            dob=datetime.fromisoformat(dob).date(),
            athena_mrn=athena_mrn,
            transcript_text=text,
            transcript_title=file.filename or "PlaudAI Upload"
        )
        
        return await upload_note(upload_data, db)
    
    except Exception as e:
        logger.error(f"File upload failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

# ==================== Query Endpoints ====================

@app.get("/patients", response_model=List[PatientResponse])
async def list_patients(
    search: Optional[str] = None,
    limit: int = 50,
    db: Session = Depends(get_db)
):
    """List patients with optional search"""
    try:
        if search:
            patients = search_patients(db, search)[:limit]
        else:
            patients = db.query(Patient).limit(limit).all()
        return patients
    except Exception as e:
        logger.error(f"Error listing patients: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@app.get("/patients/{patient_id}", response_model=PatientResponse)
async def get_patient(patient_id: int, db: Session = Depends(get_db)):
    """Get patient by ID"""
    patient = db.query(Patient).filter_by(id=patient_id).first()
    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient not found"
        )
    return patient

@app.get("/patients/{patient_id}/transcripts", response_model=List[TranscriptResponse])
async def list_patient_transcripts(
    patient_id: int,
    db: Session = Depends(get_db)
):
    transcripts = get_patient_transcripts(db, patient_id)
    return transcripts

@app.get("/patients/{patient_id}/procedures", response_model=List[PVIProcedureResponse])
async def list_patient_procedures(
    patient_id: int,
    db: Session = Depends(get_db)
):
    procedures = get_patient_procedures(db, patient_id)
    return procedures

@app.get("/transcripts/{transcript_id}", response_model=TranscriptResponse)
async def get_transcript(transcript_id: int, db: Session = Depends(get_db)):
    transcript = db.query(VoiceTranscript).filter_by(id=transcript_id).first()
    if not transcript:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transcript not found"
        )
    return transcript

# ==================== Statistics ====================

@app.get("/stats")
async def get_statistics(db: Session = Depends(get_db)):
    """Get database statistics"""
    try:
        total_patients = db.query(Patient).count()
        total_transcripts = db.query(VoiceTranscript).count()
        total_procedures = db.query(PVIProcedure).count()
        
        from datetime import timedelta
        seven_days_ago = datetime.now() - timedelta(days=7)
        recent_transcripts = db.query(VoiceTranscript).filter(
            VoiceTranscript.created_at >= seven_days_ago
        ).count()
        
        return {
            "total_patients": total_patients,
            "total_transcripts": total_transcripts,
            "total_procedures": total_procedures,
            "recent_uploads_7d": recent_transcripts,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Stats error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

# ==================== Clinical Synopsis Endpoints ====================

@app.post("/synopsis/generate/{patient_id}")
async def generate_synopsis(
    patient_id: int,
    synopsis_type: str = "comprehensive",
    days_back: int = 365,
    force_regenerate: bool = False,
    db: Session = Depends(get_db)
):
    """Generate AI-powered clinical synopsis"""
    try:
        logger.info(f"Generating synopsis for Patient {patient_id} (Type: {synopsis_type})")
        synopsis = generate_clinical_synopsis(
            db,
            patient_id=patient_id,
            synopsis_type=synopsis_type,
            days_back=days_back,
            force_regenerate=force_regenerate
        )
        
        return {
            "status": "success",
            "synopsis_id": synopsis.id,
            "patient_id": synopsis.patient_id,
            "synopsis_type": synopsis.synopsis_type,
            "synopsis_text": synopsis.synopsis_text,
            "ai_model": synopsis.ai_model,
            "tokens_used": synopsis.tokens_used,
            "data_sources": synopsis.data_sources,
            "generated_at": synopsis.created_at.isoformat()
        }
    
    except ValueError as e:
        logger.warning(f"Synopsis generation warning: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Synopsis generation failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Synopsis generation failed: {str(e)}"
        )

@app.get("/synopsis/patient/{patient_id}")
async def get_patient_synopses(
    patient_id: int,
    synopsis_type: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Get all synopses for a patient"""
    try:
        if synopsis_type:
            synopsis = get_latest_synopsis(db, patient_id, synopsis_type)
            if not synopsis:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"No {synopsis_type} synopsis found for patient {patient_id}"
                )
            return {
                "synopsis_id": synopsis.id,
                "synopsis_type": synopsis.synopsis_type,
                "synopsis_text": synopsis.synopsis_text,
                "generated_at": synopsis.created_at.isoformat()
            }
        else:
            synopses = get_all_synopses(db, patient_id)
            return {
                "patient_id": patient_id,
                "total_synopses": len(synopses),
                "synopses": [
                    {
                        "id": s.id,
                        "type": s.synopsis_type,
                        "generated_at": s.created_at.isoformat(),
                        "tokens_used": s.tokens_used
                    }
                    for s in synopses
                ]
            }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching synopses: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@app.get("/synopsis/{synopsis_id}")
async def get_synopsis_by_id(
    synopsis_id: int,
    db: Session = Depends(get_db)
):
    """Get specific synopsis by ID"""
    from .models import ClinicalSynopsis
    
    synopsis = db.query(ClinicalSynopsis).filter_by(id=synopsis_id).first()
    if not synopsis:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Synopsis not found"
        )
    
    return {
        "synopsis_id": synopsis.id,
        "patient_id": synopsis.patient_id,
        "synopsis_type": synopsis.synopsis_type,
        "synopsis_text": synopsis.synopsis_text,
        "chief_complaint": synopsis.chief_complaint,
        "history_present_illness": synopsis.history_present_illness,
        "assessment_plan": synopsis.assessment_plan,
        "ai_model": synopsis.ai_model,
        "tokens_used": synopsis.tokens_used,
        "data_sources": synopsis.data_sources,
        "generated_at": synopsis.created_at.isoformat()
    }

@app.get("/clinical/patient-summary/{mrn}")
async def get_clinical_patient_summary(
    mrn: str,
    db: Session = Depends(get_db)
):
    """
    **CLINICAL USE**: Quick patient summary by MRN
    """
    try:
        logger.info(f"Fetching clinical summary for MRN: {mrn}")
        summary = get_patient_summary(db, mrn)
        return summary
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Clinical summary failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

# ==================== Static Files & Frontend ====================

# Serve frontend - must be last!
app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")

# Run with: uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=API_HOST, port=API_PORT)