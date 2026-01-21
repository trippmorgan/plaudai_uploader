"""
=============================================================================
ALBANY VASCULAR SPECIALIST CENTER - AI CLINICAL DOCUMENTATION SYSTEM
=============================================================================

ARCHITECTURAL ROLE:
    This is the APPLICATION ENTRYPOINT - the FastAPI application root that:
    1. Initializes all system components (database, logging, routes)
    2. Defines the HTTP API surface for client interaction
    3. Orchestrates request/response flow through middleware
    4. Connects frontend, backend services, and external integrations

DATA FLOW POSITION:
    ┌─────────────────────────────────────────────────────────────────┐
    │                     EXTERNAL CLIENTS                            │
    │   (Browser/Frontend) ──► (Athena-Scraper) ──► (PlaudAI App)    │
    └────────────────────────────┬────────────────────────────────────┘
                                 │ HTTP Requests
                                 ▼
    ┌─────────────────────────────────────────────────────────────────┐
    │                      main.py (THIS FILE)                        │
    │  ┌─────────────┐  ┌─────────────┐  ┌──────────────────────┐    │
    │  │  Middleware │  │   Routes    │  │   Static Files       │    │
    │  │  (Logging)  │──►  (API)     │  │   (Frontend/PDFs)    │    │
    │  └─────────────┘  └──────┬──────┘  └──────────────────────┘    │
    └──────────────────────────┼──────────────────────────────────────┘
                               ▼
    ┌─────────────────────────────────────────────────────────────────┐
    │                      SERVICE LAYER                              │
    │  uploader.py │ gemini_synopsis.py │ parser.py │ pdf_generator  │
    └──────────────────────────┬──────────────────────────────────────┘
                               ▼
    ┌─────────────────────────────────────────────────────────────────┐
    │                      DATA LAYER                                 │
    │          db.py ──► models.py ──► PostgreSQL                    │
    └─────────────────────────────────────────────────────────────────┘

CRITICAL DESIGN PRINCIPLES:
    1. DEPENDENCY INJECTION: Database sessions injected via FastAPI Depends()
       - Ensures proper session lifecycle (create → use → cleanup)
       - Enables testability through mock injection
       - Prevents connection leaks via try/finally pattern in get_db()

    2. SEPARATION OF CONCERNS:
       - Routes: HTTP interface (validation, serialization, error handling)
       - Services: Business logic (parsing, AI generation, uploads)
       - Models: Data structure and persistence

    3. FAIL-FAST STARTUP: Application refuses to start if database unavailable
       - Prevents partial availability and zombie processes
       - Forces explicit resolution of infrastructure issues

    4. STATELESS REQUEST HANDLING: No server-side session state
       - Enables horizontal scaling behind load balancer
       - Each request is self-contained with JWT/auth if needed

SECURITY MODEL:
    - CORS: Currently permissive (allow_origins=["*"]) - suitable for
      development or trusted network only. MUST be restricted for production.
    - Input Validation: Pydantic schemas enforce type safety on all inputs
    - SQL Injection: ORM parameterization prevents injection attacks
    - Error Handling: Exceptions caught and logged; stack traces hidden from clients
    - Audit Trail: All ingestion actions logged to IntegrationAuditLog table

MAINTENANCE NOTES:
    - Add new routes by: (1) Create router in routes/, (2) Import here,
      (3) Register with app.include_router()
    - Static file serving is LAST - ensures API routes take precedence
    - Background tasks use FastAPI's BackgroundTasks (not Celery)
    - Health check at /health validates database connectivity
    - Logs format: [REQUEST_ID] METHOD PATH - enables distributed tracing

FILE DEPENDENCIES:
    - .db: Database engine, session factory, Base class
    - .config: Environment configuration (ports, keys, debug flags)
    - .logging_config: Structured logging setup
    - .models: SQLAlchemy ORM models (Patient, VoiceTranscript, etc.)
    - .schemas: Pydantic request/response models
    - .services/*: Business logic implementations
    - .routes/*: Modular API endpoints (e.g., ingest for Athena)

VERSION: 2.0.0
LAST UPDATED: 2025-12
=============================================================================
"""
import os
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
from .logging_config import configure_logging
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
    search_patients,
    get_or_create_patient,
    create_pvi_procedure
)
from .services.gemini_synopsis import (
    generate_clinical_synopsis,
    get_latest_synopsis,
    get_all_synopses,
    get_patient_summary,
    calculate_age
)
from .services.parser import generate_tags, extract_pvi_fields
from .services.category_parser import parse_by_category, generate_category_summary
from .services.clinical_query import process_clinical_query
from .services.gemini_parser import parse_with_gemini, generate_record_summary

# Telemetry for Medical Mirror Observer
from .services.telemetry import (
    emit,
    emit_upload_received,
    emit_upload_processed,
    emit_upload_failed,
    emit_patients_queried,
    emit_clinical_query,
    emit_clinical_response
)

# Athena Integration Router
from .routes.ingest import router as ingest_router

# ORCC Integration Router
from .routes.orcc import router as orcc_router

# ==================== Logging Setup ====================
configure_logging()
logger = logging.getLogger(__name__)

# ==================== App Initialization ====================
app = FastAPI(
    title="Albany Vascular AI Clinical System",
    description="Vascular Surgery AI Uploader and Surgical Note Generator - Advanced clinical documentation with AI-powered transcript processing, PVI registry integration, and automated synopsis generation",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# ==================== Middleware ====================

@app.middleware("http")
async def log_requests(request: Request, call_next):
    """
    Middleware to log every request, response time, and status code.
    Generates a unique Request ID for tracing.
    """
    request_id = str(uuid.uuid4())[:8]
    start_time = time.time()
    
    logger.info(f"➡️ [{request_id}] {request.method} {request.url.path}")
    
    try:
        response = await call_next(request)
        process_time = (time.time() - start_time) * 1000
        logger.info(f"⬅️ [{request_id}] {response.status_code} - {process_time:.2f}ms")
        return response
    except Exception as e:
        process_time = (time.time() - start_time) * 1000
        logger.error(f"❌ [{request_id}] FAILED - {process_time:.2f}ms - Error: {str(e)}", exc_info=True)
        raise

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==================== Register Routers ====================
app.include_router(ingest_router)  # Athena Integration: /ingest/*
app.include_router(orcc_router)    # ORCC Integration: /api/procedures, /api/patients

# ==================== Startup & Health ====================

@app.on_event("startup")
async def startup_event():
    """Initialize database on startup"""
    logger.info("🚀 Starting Albany Vascular AI Clinical System...")

    if not check_connection():
        logger.critical("❌ Database connection failed! Application cannot start.")
        raise RuntimeError("Cannot connect to database")

    try:
        init_db()
        logger.info("✅ Database initialized successfully")
    except Exception as e:
        logger.critical(f"❌ Database initialization failed: {e}")
        raise

    logger.info("✅ Albany Vascular AI Clinical System ready to accept connections")

# REMOVED: Root route was blocking static file serving of frontend/index.html
# The /health endpoint provides the same health info
# @app.get("/")
# async def root():
#     return {...}  # Health info moved to /health endpoint

@app.get("/health")
async def health_check(db: Session = Depends(get_db)):
    """Detailed health check"""
    try:
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
    Upload a voice transcript with AI-powered category-specific parsing

    Supports operative notes, imaging reports, lab results, and office visit notes
    """
    # Telemetry: Track upload received
    correlation_id = await emit_upload_received(
        has_patient_info=bool(data.first_name and data.athena_mrn),
        record_type=data.record_category or "office_visit",
        mrn=data.athena_mrn
    )

    try:
        category = data.record_category or "office_visit"
        logger.info(f"Processing {category} upload for MRN: {data.athena_mrn}")
        
        patient_data = {
            "first_name": data.first_name,
            "last_name": data.last_name,
            "dob": data.dob,
            "athena_mrn": data.athena_mrn,
            "birth_sex": data.birth_sex,
            "race": data.race,
            "zip_code": data.zip_code
        }
        
        # Get or create patient
        patient = get_or_create_patient(db, patient_data)
        
        # Determine which text to parse
        text_to_parse = data.plaud_note if data.plaud_note else data.raw_transcript
        
        # Category-specific Gemini parsing
        logger.info(f"⚙️ Running category-specific parsing for {category}...")
        category_data = parse_by_category(text_to_parse, category)
        category_summary = generate_category_summary(category_data, category)
        
        # Also run general medical tagging
        tags = generate_tags(text_to_parse)
        
        # Extract PVI fields only for operative notes
        pvi_fields = {}
        if category == "operative_note":
            pvi_fields = extract_pvi_fields(text_to_parse)
        
        # Calculate confidence
        confidence = 1.0 if 'error' not in category_data else 0.3
        
        # Create transcript record
        transcript = VoiceTranscript(
            patient_id=patient.id,
            transcript_title=data.transcript_title or f"{category.replace('_', ' ').title()} - {datetime.now().strftime('%Y-%m-%d')}",
            raw_transcript=data.raw_transcript,
            plaud_note=data.plaud_note,
            record_category=category,
            record_subtype=data.record_subtype,
            category_specific_data=category_data,
            visit_type=data.visit_type,
            recording_duration=data.recording_duration,
            recording_date=data.recording_date or datetime.now(),
            plaud_recording_id=data.plaud_recording_id,
            tags=tags,
            confidence_score=confidence,
            is_processed=True,
            visit_date=data.recording_date or datetime.now()
        )
        
        db.add(transcript)
        db.commit()
        db.refresh(transcript)
        
        # Create PVI procedure if applicable
        pvi_procedure_id = None
        if pvi_fields and len(pvi_fields) >= 3:
            logger.info(f"🏥 Creating PVI procedure record...")
            try:
                pvi_procedure_id = create_pvi_procedure(db, patient.id, transcript.id, pvi_fields)
            except Exception as e:
                logger.warning(f"⚠️ Could not create PVI procedure: {e}")
        
        warnings = []
        if confidence < 0.5:
            warnings.append("Low confidence - manual review recommended")
        if 'error' in category_data:
            warnings.append(f"Category parsing issue: {category_data.get('error', 'Unknown error')}")
        
        logger.info(f"✅ {category} record saved: ID {transcript.id}")

        # Telemetry: Track successful upload with data quality metrics
        await emit_upload_processed(
            correlation_id=correlation_id,
            patient_id=patient.id,
            transcript_id=transcript.id,
            confidence=confidence,
            category=category,
            tags_count=len(tags) if tags else 0
        )

        # Telemetry: Track data quality (fields present/missing)
        await emit('upload', 'DATA_QUALITY_ASSESSMENT', {
            'correlationId': correlation_id,
            'fieldsPresent': {
                'firstName': bool(data.first_name),
                'lastName': bool(data.last_name),
                'dob': bool(data.dob),
                'mrn': bool(data.athena_mrn),
                'birthSex': bool(data.birth_sex),
                'race': bool(data.race),
                'zipCode': bool(data.zip_code),
                'rawTranscript': bool(data.raw_transcript),
                'plaudNote': bool(data.plaud_note),
                'recordingDate': bool(data.recording_date),
                'visitType': bool(data.visit_type)
            },
            'hasStructuredData': bool(category_data and 'error' not in category_data),
            'hasPviFields': bool(pvi_fields and len(pvi_fields) >= 3)
        })

        return UploadResponse(
            status="success",
            message=f"{category.replace('_', ' ').title()} uploaded successfully",
            patient_id=patient.id,
            transcript_id=transcript.id,
            tags=tags,
            confidence_score=confidence,
            warnings=warnings if warnings else None
        )

    except Exception as e:
        logger.error(f"❌ Upload failed: {e}", exc_info=True)
        # Telemetry: Track failed upload
        await emit_upload_failed(correlation_id=correlation_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@app.post("/upload-medical-record")
async def upload_medical_record(
    data: dict,
    db: Session = Depends(get_db)
):
    """
    Upload categorized medical record with Gemini parsing
    
    Request body:
    {
      "patient": {"first_name": "...", "last_name": "...", "dob": "...", "athena_mrn": "..."},
      "record_type": "operative_note|office_visit|ultrasound|ct_scan|mri|xray|lab_result",
      "record_subtype": "Optional specific type",
      "record_date": "YYYY-MM-DD",
      "title": "Record title",
      "raw_content": "PlaudAI transcript text",
      "provider_name": "Optional provider name"
    }
    """
    try:
        logger.info(f"📥 Processing {data.get('record_type')} record")
        
        # Get or create patient
        patient_data = data['patient']
        patient = get_or_create_patient(db, patient_data)
        
        # Parse with Gemini
        patient_context = {
            "name": f"{patient.first_name} {patient.last_name}",
            "mrn": patient.athena_mrn,
            "age": calculate_age(patient.dob)
        }
        
        parsed_data = parse_with_gemini(
            text=data['raw_content'],
            record_type=data['record_type'],
            patient_context=patient_context
        )
        
        # Generate summary
        summary = generate_record_summary(parsed_data, data['record_type'])
        
        # Extract tags (use existing parser)
        tags = generate_tags(data['raw_content'])
        
        # Create medical record
        record = MedicalRecord(
            patient_id=patient.id,
            record_type=data['record_type'],
            record_subtype=data.get('record_subtype'),
            record_date=data['record_date'],
            title=data['title'],
            raw_content=data['raw_content'],
            structured_content=parsed_data,
            gemini_summary=summary,
            provider_name=data.get('provider_name'),
            tags=tags,
            confidence_score=1.0 if 'error' not in parsed_data else 0.3
        )
        
        db.add(record)
        db.commit()
        db.refresh(record)
        
        logger.info(f"✅ Medical record saved: ID {record.id}")
        
        return {
            "status": "success",
            "record_id": record.id,
            "patient_id": patient.id,
            "record_type": record.record_type,
            "gemini_summary": summary,
            "structured_data": parsed_data,
            "tags": tags
        }
        
    except Exception as e:
        logger.error(f"❌ Medical record upload failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

# ... (rest of your endpoints remain the same)

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
        
        upload_data = TranscriptUpload(
            first_name=first_name,
            last_name=last_name,
            dob=datetime.fromisoformat(dob).date(),
            athena_mrn=athena_mrn,
            raw_transcript=text,
            transcript_title=file.filename or "Voice Transcript Upload"
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

        # Telemetry: Track patient query
        await emit_patients_queried(
            result_count=len(patients),
            query_type='search' if search else 'list'
        )

        return patients
    except Exception as e:
        logger.error(f"Error listing patients: {e}")
        await emit('query', 'PATIENTS_QUERY_FAILED', {'error': str(e)}, success=False)
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
    """Get specific transcript by ID"""
    transcript = db.query(VoiceTranscript).filter_by(id=transcript_id).first()
    if not transcript:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transcript not found"
        )
    return transcript

# ==================== EMR Category Endpoints ====================

@app.get("/patients/{patient_id}/records-by-category")
async def get_records_by_category(
    patient_id: int,
    category: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Get patient records, optionally filtered by category
    
    Categories: operative_note, imaging, lab_result, office_visit, or 'all'
    """
    query = db.query(VoiceTranscript).filter_by(patient_id=patient_id)
    
    if category and category != "all":
        query = query.filter_by(record_category=category)
    
    records = query.order_by(VoiceTranscript.recording_date.desc()).all()
    
    return {
        "patient_id": patient_id,
        "category": category or "all",
        "total": len(records),
        "records": [
            {
                "id": r.id,
                "category": r.record_category or "office_visit",
                "subtype": r.record_subtype,
                "date": r.recording_date.isoformat() if r.recording_date else None,
                "title": r.transcript_title,
                "summary": generate_category_summary(
                    r.category_specific_data or {},
                    r.record_category or "office_visit"
                ),
                "structured_data": r.category_specific_data,
                "tags": r.tags,
                "confidence_score": r.confidence_score
            }
            for r in records
        ]
    }

@app.get("/patients/{patient_id}/emr-chart")
async def get_emr_chart(
    patient_id: int,
    db: Session = Depends(get_db)
):
    """
    Get complete EMR chart organized by category
    """
    patient = db.query(Patient).filter_by(id=patient_id).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    
    # Get all records
    records = db.query(VoiceTranscript).filter_by(patient_id=patient_id).order_by(
        VoiceTranscript.recording_date.desc()
    ).all()
    
    # Organize by category
    chart = {
        "patient": {
            "id": patient.id,
            "name": f"{patient.first_name} {patient.last_name}",
            "mrn": patient.athena_mrn,
            "dob": str(patient.dob),
            "age": calculate_age(patient.dob)
        },
        "operative_notes": [],
        "imaging": [],
        "lab_results": [],
        "office_visits": []
    }
    
    for r in records:
        record_data = {
            "id": r.id,
            "date": r.recording_date.isoformat() if r.recording_date else None,
            "title": r.transcript_title,
            "subtype": r.record_subtype,
            "summary": generate_category_summary(
                r.category_specific_data or {},
                r.record_category or "office_visit"
            ),
            "structured_data": r.category_specific_data
        }
        
        category = r.record_category or "office_visit"
        if category == "operative_note":
            chart["operative_notes"].append(record_data)
        elif category == "imaging":
            chart["imaging"].append(record_data)
        elif category == "lab_result":
            chart["lab_results"].append(record_data)
        else:
            chart["office_visits"].append(record_data)
    
    return chart

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

# ==================== Clinical Query Endpoint ====================

@app.post("/clinical/query")
async def clinical_query_endpoint(
    request: dict,
    db: Session = Depends(get_db)
):
    """
    Natural language clinical query interface
    """
    query = request.get("query", "").strip()

    if not query:
        logger.warning("Empty query received")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Query cannot be empty"
        )

    logger.info(f"📥 Clinical query received: '{query[:50]}...'")

    # Telemetry: Track query submission
    correlation_id = await emit_clinical_query(
        query_length=len(query),
        patient_found=False  # Will update after processing
    )

    try:
        result = process_clinical_query(query, db)

        if result["status"] == "error":
            logger.warning(f"⚠️ Query failed: {result.get('message')}")
            await emit('ai-query', 'QUERY_FAILED', {
                'correlationId': correlation_id,
                'error': result.get('message', 'Unknown error')
            }, success=False)
            return result

        logger.info(f"✅ Query successful for patient: {result['patient']['mrn']}")

        # Telemetry: Track successful response
        await emit_clinical_response(
            correlation_id=correlation_id,
            response_length=len(result.get('response', '')),
            data_sources=result.get('data_sources', {})
        )

        return result

    except Exception as e:
        logger.error(f"❌ Clinical query endpoint error: {e}", exc_info=True)
        await emit('ai-query', 'QUERY_FAILED', {
            'correlationId': correlation_id,
            'error': str(e)
        }, success=False)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Query processing failed: {str(e)}"
        )
# ==================== PDF Generation Endpoint ====================

@app.post("/generate-pdf/{transcript_id}")
async def generate_pdf_for_record(
    transcript_id: int,
    db: Session = Depends(get_db)
):
    """
    Generate PDF for a specific medical record
    
    Returns download URL for the generated PDF
    """
    from .services.pdf_generator import generate_medical_record_pdf
    from .services.gemini_synopsis import calculate_age
    
    try:
        # Get transcript
        transcript = db.query(VoiceTranscript).filter_by(id=transcript_id).first()
        if not transcript:
            raise HTTPException(status_code=404, detail="Transcript not found")
        
        # Get patient
        patient = db.query(Patient).filter_by(id=transcript.patient_id).first()
        if not patient:
            raise HTTPException(status_code=404, detail="Patient not found")
        
        # Prepare patient data
        patient_data = {
            "name": f"{patient.first_name} {patient.last_name}",
            "mrn": patient.athena_mrn,
            "dob": str(patient.dob),
            "age": calculate_age(patient.dob)
        }
        
        # Generate PDF
        category = transcript.record_category or "office_visit"
        category_data = transcript.category_specific_data or {}
        raw_text = transcript.plaud_note if transcript.plaud_note else transcript.raw_transcript
        
        pdf_path = generate_medical_record_pdf(
            patient_data=patient_data,
            category=category,
            category_data=category_data,
            raw_transcript=raw_text
        )
        
        # Get filename
        filename = os.path.basename(pdf_path)
        
        return {
            "status": "success",
            "message": "PDF generated successfully",
            "pdf_path": pdf_path,
            "pdf_url": f"/clinical_pdfs/{filename}",
            "filename": filename
        }
    
    except Exception as e:
        logger.error(f"PDF generation failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@app.post("/generate-synopsis-pdf/{patient_id}")
async def generate_synopsis_pdf_endpoint(
    patient_id: int,
    synopsis_type: str = "comprehensive",
    days_back: int = 365,
    db: Session = Depends(get_db)
):
    """
    Generate AI synopsis and create PDF in one call
    """
    from .services.pdf_generator import generate_synopsis_pdf
    from .services.gemini_synopsis import calculate_age
    
    try:
        # Generate or get synopsis
        synopsis = generate_clinical_synopsis(
            db,
            patient_id=patient_id,
            synopsis_type=synopsis_type,
            days_back=days_back
        )
        
        # Get patient
        patient = db.query(Patient).filter_by(id=patient_id).first()
        
        patient_data = {
            "name": f"{patient.first_name} {patient.last_name}",
            "mrn": patient.athena_mrn,
            "age": calculate_age(patient.dob)
        }
        
        # Generate PDF
        pdf_path = generate_synopsis_pdf(
            patient_data=patient_data,
            synopsis_text=synopsis.synopsis_text,
            synopsis_type=synopsis_type
        )
        
        filename = os.path.basename(pdf_path)
        
        return {
            "status": "success",
            "synopsis_id": synopsis.id,
            "pdf_path": pdf_path,
            "pdf_url": f"/clinical_pdfs/{filename}",
            "filename": filename
        }
    
    except Exception as e:
        logger.error(f"Synopsis PDF generation failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
# ==================== Static Files & Frontend ====================

# Serve generated PDFs
app.mount("/clinical_pdfs", StaticFiles(directory="clinical_pdfs"), name="clinical_pdfs")

# Serve frontend - must be last!
app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")

# Run with: uvicorn backend.main:app --reload --host 0.0.0.0 --port 8001
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=API_HOST, port=API_PORT)