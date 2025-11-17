"""
PlaudAI Uploader - FastAPI Main Application
"""
from fastapi import FastAPI, Depends, HTTPException, status, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from typing import List, Optional
import logging
from datetime import datetime

from .db import Base, engine, get_db, check_connection, init_db
from .config import API_HOST, API_PORT, DEBUG
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

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="PlaudAI Uploader",
    description="Voice transcript upload and processing for Surgical Command Center",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS middleware
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
    logger.info("Starting PlaudAI Uploader API...")
    
    # Check database connection
    if not check_connection():
        logger.error("Database connection failed!")
        raise RuntimeError("Cannot connect to database")
    
    # Initialize tables
    try:
        init_db()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        raise
    
    logger.info("PlaudAI Uploader API ready")

@app.get("/")
async def root():
    """Health check and API info"""
    return {
        "service": "PlaudAI Uploader",
        "version": "1.0.0",
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
        # Test database query
        db.execute("SELECT 1")
        db_status = "healthy"
    except Exception as e:
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
    
    - Automatically creates or updates patient record by Athena MRN
    - Parses transcript for medical tags
    - Extracts PVI registry fields
    - Stores both raw transcript and PlaudAI's formatted note
    - Returns confidence score and processing results
    """
    try:
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
        logger.error(f"Upload failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@app.post("/batch-upload", response_model=BatchUploadResponse)
async def batch_upload(
    request: BatchUploadRequest,
    db: Session = Depends(get_db)
):
    """
    Upload multiple transcripts in batch
    
    - Max 50 items per request
    - Returns summary of successful and failed uploads
    """
    try:
        items = [
            {
                "patient_data": item.patient_data.dict(),
                "transcript_text": item.transcript_text,
                "title": item.transcript_title
            }
            for item in request.items
        ]
        
        result = batch_upload_transcripts(db, items)
        
        return BatchUploadResponse(
            status="completed",
            total=result["total"],
            successful=result["successful"],
            failed=result["failed"],
            results=result["details"]
        )
    
    except Exception as e:
        logger.error(f"Batch upload failed: {e}")
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
    """
    Upload transcript from file (TXT, MD, JSON)
    """
    try:
        # Read file content
        content = await file.read()
        text = content.decode('utf-8')
        
        # Validate required fields
        if not all([first_name, last_name, dob, athena_mrn]):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing required patient information"
            )
        
        # Create upload data
        from datetime import datetime
        upload_data = TranscriptUpload(
            first_name=first_name,
            last_name=last_name,
            dob=datetime.fromisoformat(dob).date(),
            athena_mrn=athena_mrn,
            transcript_text=text,
            transcript_title=file.filename or "PlaudAI Upload"
        )
        
        # Use regular upload endpoint
        return await upload_note(upload_data, db)
    
    except Exception as e:
        logger.error(f"File upload failed: {e}")
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
    """Get all transcripts for a patient"""
    transcripts = get_patient_transcripts(db, patient_id)
    return transcripts

@app.get("/patients/{patient_id}/procedures", response_model=List[PVIProcedureResponse])
async def list_patient_procedures(
    patient_id: int,
    db: Session = Depends(get_db)
):
    """Get all PVI procedures for a patient"""
    procedures = get_patient_procedures(db, patient_id)
    return procedures

@app.get("/transcripts/{transcript_id}", response_model=TranscriptResponse)
async def get_transcript(transcript_id: int, db: Session = Depends(get_db)):
    """Get transcript by ID"""
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
        
        # Recent uploads (last 7 days)
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
    """
    Generate AI-powered clinical synopsis from patient's data
    
    - **patient_id**: Database patient ID
    - **synopsis_type**: comprehensive, visit_summary, problem_list, procedure_summary
    - **days_back**: How many days of history to include (default 365)
    - **force_regenerate**: Force new generation even if recent synopsis exists
    
    Requires GOOGLE_API_KEY to be configured
    """
    try:
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
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Synopsis generation failed: {e}")
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
    """
    Get all synopses for a patient, optionally filtered by type
    """
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
    
    Returns demographics + latest comprehensive synopsis
    Perfect for pulling up patient info during clinical encounters
    """
    try:
        summary = get_patient_summary(db, mrn)
        return summary
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

# Run with: uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=API_HOST, port=API_PORT)