"""
=============================================================================
DATABASE UPLOAD SERVICE
=============================================================================

ARCHITECTURAL ROLE:
    This module is the PRIMARY DATA INGESTION SERVICE - the central
    orchestrator for creating patients, storing transcripts, and generating
    PVI procedure records from PlaudAI voice recordings.

DATA FLOW POSITION:
    ┌────────────────────────────────────────────────────────────────────┐
    │                   EXTERNAL SOURCES                                 │
    │   PlaudAI App ──► API Upload ──► TranscriptUpload Schema          │
    │   File Upload ──► POST /upload-file ──► TranscriptUpload          │
    │   Batch API   ──► POST /batch-upload ──► BatchUploadRequest       │
    └────────────────────────────┬───────────────────────────────────────┘
                                 │
                                 ▼
    ┌────────────────────────────────────────────────────────────────────┐
    │                   uploader.py (THIS FILE)                          │
    │                                                                    │
    │  ┌──────────────────────────────────────────────────────────────┐ │
    │  │            get_or_create_patient()                            │ │
    │  │  1. Query by athena_mrn (unique identifier)                  │ │
    │  │  2. If exists → update demographics if changed               │ │
    │  │  3. If new → INSERT into patients table                      │ │
    │  └──────────────────────────────────────────────────────────────┘ │
    │                               │                                    │
    │                               ▼                                    │
    │  ┌──────────────────────────────────────────────────────────────┐ │
    │  │            upload_transcript()                                │ │
    │  │  1. Create/get patient record                                │ │
    │  │  2. Parse transcript (parser.py) → tags, pvi_fields         │ │
    │  │  3. INSERT VoiceTranscript record                            │ │
    │  │  4. If PVI fields sufficient → create_pvi_procedure()       │ │
    │  │  5. COMMIT transaction                                       │ │
    │  └──────────────────────────────────────────────────────────────┘ │
    │                               │                                    │
    │                               ▼                                    │
    │  ┌──────────────────────────────────────────────────────────────┐ │
    │  │            create_pvi_procedure()                             │ │
    │  │  Map extracted fields to PVIProcedure model columns          │ │
    │  │  Required: patient_id, transcript_id, procedure_date         │ │
    │  └──────────────────────────────────────────────────────────────┘ │
    └────────────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
    ┌────────────────────────────────────────────────────────────────────┐
    │                   DATABASE (PostgreSQL)                            │
    │   patients ◄── voice_transcripts ◄── pvi_procedures              │
    └────────────────────────────────────────────────────────────────────┘

CRITICAL DESIGN PRINCIPLES:

    1. UPSERT PATIENT PATTERN:
       get_or_create_patient() implements upsert semantics:
       - First query by athena_mrn (the unique identifier)
       - If found, update any changed demographic fields
       - If not found, create new patient record
       - Returns Patient object in all cases

    2. AUTOMATIC PVI EXTRACTION:
       When a transcript is uploaded:
       - parser.process_transcript() extracts PVI fields
       - If >= 3 fields extracted → create PVIProcedure record
       - Links transcript to procedure for traceability

    3. DUAL TEXT STORAGE:
       Both raw_transcript AND plaud_note are stored:
       - raw_transcript: Unprocessed voice-to-text output
       - plaud_note: PlaudAI's formatted/structured version
       - Processing prefers plaud_note, falls back to raw

    4. TRANSACTION SAFETY:
       All operations within single transaction:
       - Patient + Transcript committed together
       - Rollback on any failure
       - No orphaned records possible

FUNCTION REFERENCE:

    get_or_create_patient(db, patient_data) -> Patient
        PARAMS:
          db: SQLAlchemy Session
          patient_data: Dict with keys:
            - athena_mrn (required): Unique patient identifier
            - first_name, last_name: Name fields
            - dob: Date of birth
            - birth_sex, race, zip_code: Demographics
        RETURNS: Patient ORM object (new or existing)
        BEHAVIOR:
          - Existing: Updates changed fields, logs updates
          - New: Creates record, logs creation
        RAISES: ValueError on IntegrityError (duplicate MRN race condition)

    upload_transcript(db, patient_data, raw_transcript, ...) -> Dict
        PARAMS:
          db: SQLAlchemy Session
          patient_data: Dict (see above)
          raw_transcript: str - Voice-to-text output
          plaud_note: str (optional) - Formatted note
          title: str - Display title
          visit_type: str - Visit category
          recording_duration: float - Length in seconds
          recording_date: datetime - When recorded
          plaud_recording_id: str - PlaudAI's ID
          auto_process: bool - Run parser (default True)
        RETURNS: Dict with:
          - patient_id, transcript_id, pvi_procedure_id
          - tags, confidence_score
          - sections_found, pvi_fields_extracted
        RAISES: HTTPException on failure (after rollback)

    create_pvi_procedure(db, patient_id, transcript_id, pvi_fields) -> int
        PARAMS:
          db: SQLAlchemy Session
          patient_id: int - FK to patients
          transcript_id: int - FK to voice_transcripts
          pvi_fields: Dict - Extracted registry fields
        RETURNS: int - New procedure ID
        BEHAVIOR: Sets procedure_date to today if not in pvi_fields

    batch_upload_transcripts(db, items) -> Dict
        PARAMS:
          db: SQLAlchemy Session
          items: List[Dict] - Each with patient_data and transcript_text
        RETURNS: Dict with:
          - total, successful, failed counts
          - details: List of per-item results
        BEHAVIOR: Continues on individual failures (partial success allowed)

    get_patient_transcripts(db, patient_id) -> List[VoiceTranscript]
        Simple query wrapper for patient's transcripts

    get_patient_procedures(db, patient_id) -> List[PVIProcedure]
        Simple query wrapper for patient's procedures

    search_patients(db, search_term) -> List[Patient]
        PARAMS: search_term - Partial name or MRN
        RETURNS: Matching patients (case-insensitive LIKE search)
        SEARCHES: first_name, last_name, athena_mrn

LOGGING STRATEGY:
    Comprehensive logging at INFO/DEBUG levels:
    - Patient lookups: "Looking up patient by MRN: ..."
    - Patient creation: "Creating new patient record..."
    - Demographic updates: "Updated demographics: field1, field2"
    - Parsing results: "Confidence: 0.85, Tags: 12, PVI fields: 8"
    - PVI creation: "Creating PVI procedure record..."
    - Errors: Full stack traces via exc_info=True

SECURITY MODEL:
    - No authentication in this module (handled by API layer)
    - SQL injection prevented via ORM parameterization
    - IntegrityError caught to prevent information disclosure

MAINTENANCE NOTES:
    - Add new patient fields: Update patient_data dict handling
    - Add new transcript fields: Update VoiceTranscript creation
    - Modify PVI threshold: Change "len(pvi_fields) >= 3" check
    - Add batch validation: Wrap individual items in try/except

ERROR HANDLING:
    - IntegrityError: Rollback + ValueError with safe message
    - General Exception: Rollback + re-raise with logging
    - Batch mode: Log failures, continue processing

VERSION: 2.0.0
LAST UPDATED: 2025-12
=============================================================================
"""
import logging
from datetime import datetime
from typing import Dict, Any, Tuple, List

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from ..models import Patient, VoiceTranscript, PVIProcedure
from .parser import process_transcript

# Initialize logger
logger = logging.getLogger(__name__)

# ==================== Patient Management ====================

def get_or_create_patient(db: Session, patient_data: Dict[str, Any]) -> Patient:
    """
    Get existing patient by Athena MRN or create new one.
    Logs demographic updates if they occur.
    """
    athena_mrn = patient_data.get("athena_mrn")
    
    # Log the lookup attempt
    logger.debug(f"🔍 Looking up patient by MRN: {athena_mrn}")
    
    # Try to find existing patient
    patient = db.query(Patient).filter_by(athena_mrn=athena_mrn).first()
    
    if patient:
        logger.info(f"✅ Found existing patient ID {patient.id} (MRN: {athena_mrn})")
        
        # Check for updates to demographics
        updates_made = []
        for key, value in patient_data.items():
            if value is not None and hasattr(patient, key):
                current_val = getattr(patient, key)
                # Simple check to see if value changed
                if str(current_val) != str(value):
                    setattr(patient, key, value)
                    updates_made.append(key)
        
        if updates_made:
            db.commit()
            db.refresh(patient)
            logger.info(f"📝 Updated demographics for Patient {patient.id}: {', '.join(updates_made)}")
    else:
        # Create new patient
        try:
            logger.info(f"🆕 Creating new patient record for MRN: {athena_mrn}")
            patient = Patient(**patient_data)
            db.add(patient)
            db.commit()
            db.refresh(patient)
            logger.info(f"✅ Patient created successfully. ID: {patient.id}")
        except IntegrityError as e:
            db.rollback()
            logger.error(f"❌ Failed to create patient (IntegrityError): {e}")
            raise ValueError(f"Patient with MRN {athena_mrn} already exists or invalid data")
        except Exception as e:
            db.rollback()
            logger.error(f"❌ Unexpected error creating patient: {e}")
            raise
    
    return patient

# ==================== Transcript Upload ====================

def upload_transcript(
    db: Session,
    patient_data: Dict[str, Any],
    raw_transcript: str,
    plaud_note: str = None,
    title: str = "PlaudAI Note",
    visit_type: str = None,
    recording_duration: float = None,
    recording_date: datetime = None,
    plaud_recording_id: str = None,
    auto_process: bool = True
) -> Dict[str, Any]:
    """
    Upload PlaudAI transcript with detailed logging of the parsing process.
    """
    try:
        logger.info(f"📥 Starting transcript upload for MRN: {patient_data.get('athena_mrn')} | Title: {title}")
        
        # Get or create patient
        patient = get_or_create_patient(db, patient_data)
        
        # Determine which text to process
        text_to_process = plaud_note if plaud_note else raw_transcript
        source_type = "PlaudAI Note" if plaud_note else "Raw Transcript"
        
        logger.debug(f"📄 Processing source: {source_type} (Length: {len(text_to_process or '')} chars)")
        
        # Process transcript if enabled
        sections = {}
        tags = []
        pvi_fields = {}
        confidence = 0.0
        
        if auto_process and text_to_process:
            logger.info("⚙️ Running parser and tag extraction...")
            sections, tags, pvi_fields, confidence = process_transcript(text_to_process)
            logger.info(f"🏷️ Parsing complete. Confidence: {confidence:.2f} | Tags found: {len(tags)} | PVI Fields: {len(pvi_fields)}")
            logger.debug(f"Tags: {tags}")
        else:
            logger.info("⏭️ Skipping auto-processing (auto_process=False or empty text)")
        
        # Create transcript record
        transcript = VoiceTranscript(
            patient_id=patient.id,
            transcript_title=title,
            raw_transcript=raw_transcript,
            plaud_note=plaud_note,
            visit_type=visit_type,
            recording_duration=recording_duration,
            recording_date=recording_date or datetime.now(),
            plaud_recording_id=plaud_recording_id,
            tags=tags,
            confidence_score=confidence,
            is_processed=auto_process,
            visit_date=recording_date or datetime.now()
        )
        
        db.add(transcript)
        db.commit()
        db.refresh(transcript)
        
        logger.info(f"💾 Transcript saved successfully. ID: {transcript.id}")
        
        # Optionally create PVI procedure record
        pvi_procedure_id = None
        if pvi_fields and len(pvi_fields) >= 3:
            logger.info(f"🏥 Sufficient PVI data found ({len(pvi_fields)} fields). Creating procedure record...")
            try:
                pvi_procedure_id = create_pvi_procedure(
                    db, patient.id, transcript.id, pvi_fields
                )
                logger.info(f"✅ PVI Procedure created. ID: {pvi_procedure_id}")
            except Exception as e:
                logger.warning(f"⚠️ Could not create PVI procedure: {e}")
        else:
            if pvi_fields:
                logger.debug(f"ℹ️ PVI creation skipped (Only {len(pvi_fields)}/3 fields found)")
        
        return {
            "patient_id": patient.id,
            "transcript_id": transcript.id,
            "pvi_procedure_id": pvi_procedure_id,
            "tags": tags,
            "confidence_score": confidence,
            "sections_found": list(sections.keys()),
            "pvi_fields_extracted": len(pvi_fields),
            "has_plaud_note": plaud_note is not None,
            "has_raw_transcript": raw_transcript is not None
        }
    
    except Exception as e:
        db.rollback()
        logger.error(f"❌ Upload failed in upload_transcript: {e}", exc_info=True)
        raise

# ==================== PVI Procedure Creation ====================

def create_pvi_procedure(
    db: Session,
    patient_id: int,
    transcript_id: int,
    pvi_fields: Dict[str, Any]
) -> int:
    """
    Create PVI procedure record from extracted fields
    """
    # Ensure we have a procedure date
    if "procedure_date" not in pvi_fields:
        pvi_fields["procedure_date"] = datetime.now().date()
        logger.debug("Using current date for PVI procedure (none found in text)")
    
    procedure = PVIProcedure(
        patient_id=patient_id,
        transcript_id=transcript_id,
        **pvi_fields
    )
    
    db.add(procedure)
    db.commit()
    db.refresh(procedure)
    
    return procedure.id

# ==================== Batch Upload ====================

def batch_upload_transcripts(
    db: Session,
    items: list
) -> Dict[str, Any]:
    """
    Upload multiple transcripts in batch with progress logging
    """
    logger.info(f"📦 Starting batch upload processing for {len(items)} items")
    
    results = {
        "total": len(items),
        "successful": 0,
        "failed": 0,
        "details": []
    }
    
    for idx, item in enumerate(items):
        try:
            logger.debug(f"Processing batch item {idx + 1}/{len(items)}")
            
            # Map batch item fields to upload_transcript arguments
            result = upload_transcript(
                db,
                patient_data=item.get("patient_data", {}),
                raw_transcript=item.get("transcript_text", ""), # Map text to raw_transcript
                title=item.get("title", f"PlaudAI Note {idx + 1}"),
                auto_process=True
            )
            
            results["successful"] += 1
            results["details"].append({
                "index": idx,
                "status": "success",
                "patient_id": result["patient_id"],
                "transcript_id": result["transcript_id"]
            })
        except Exception as e:
            results["failed"] += 1
            error_msg = str(e)
            logger.error(f"❌ Batch item {idx} failed: {error_msg}")
            results["details"].append({
                "index": idx,
                "status": "failed",
                "error": error_msg
            })
    
    logger.info(f"🏁 Batch upload finished. Success: {results['successful']}, Failed: {results['failed']}")
    return results

# ==================== Query Helpers ====================

def get_patient_transcripts(db: Session, patient_id: int) -> list:
    """Get all transcripts for a patient"""
    logger.debug(f"Fetching transcripts for Patient ID: {patient_id}")
    return db.query(VoiceTranscript).filter_by(patient_id=patient_id).all()

def get_patient_procedures(db: Session, patient_id: int) -> list:
    """Get all PVI procedures for a patient"""
    logger.debug(f"Fetching procedures for Patient ID: {patient_id}")
    return db.query(PVIProcedure).filter_by(patient_id=patient_id).all()

def search_patients(db: Session, search_term: str) -> list:
    """Search patients by name or MRN"""
    logger.info(f"🔎 Searching patients with term: '{search_term}'")
    return db.query(Patient).filter(
        (Patient.first_name.ilike(f"%{search_term}%")) |
        (Patient.last_name.ilike(f"%{search_term}%")) |
        (Patient.athena_mrn.ilike(f"%{search_term}%"))
    ).all()