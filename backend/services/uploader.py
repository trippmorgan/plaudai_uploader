"""
PlaudAI Uploader - Database Upload Service
Handles patient creation and transcript storage
"""
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from typing import Dict, Any, Tuple
import logging
from datetime import datetime

from ..models import Patient, VoiceTranscript, PVIProcedure
from .parser import process_transcript

logger = logging.getLogger(__name__)

# ==================== Patient Management ====================

def get_or_create_patient(db: Session, patient_data: Dict[str, Any]) -> Patient:
    """
    Get existing patient by Athena MRN or create new one
    """
    athena_mrn = patient_data.get("athena_mrn")
    
    # Try to find existing patient
    patient = db.query(Patient).filter_by(athena_mrn=athena_mrn).first()
    
    if patient:
        logger.info(f"Found existing patient: {athena_mrn}")
        # Update patient info if provided
        for key, value in patient_data.items():
            if value is not None and hasattr(patient, key):
                setattr(patient, key, value)
        db.commit()
        db.refresh(patient)
    else:
        # Create new patient
        try:
            patient = Patient(**patient_data)
            db.add(patient)
            db.commit()
            db.refresh(patient)
            logger.info(f"Created new patient: {athena_mrn}")
        except IntegrityError as e:
            db.rollback()
            logger.error(f"Failed to create patient: {e}")
            raise ValueError(f"Patient with MRN {athena_mrn} already exists or invalid data")
    
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
    Upload PlaudAI transcript with both raw transcript and formatted note
    
    Args:
        db: Database session
        patient_data: Patient demographic information
        raw_transcript: Raw voice-to-text transcript from PlaudAI
        plaud_note: PlaudAI's configured/formatted note (optional)
        title: Optional title for the transcript
        visit_type: Type of visit (office, procedure, follow-up, etc.)
        recording_duration: Duration in seconds
        recording_date: When recording was made
        plaud_recording_id: Original PlaudAI recording ID
        auto_process: Whether to automatically parse and tag
    
    Returns:
        Dictionary with upload results including patient_id, transcript_id, tags
    """
    try:
        # Get or create patient
        patient = get_or_create_patient(db, patient_data)
        
        # Determine which text to process for tagging
        # Prefer plaud_note if available, fallback to raw_transcript
        text_to_process = plaud_note if plaud_note else raw_transcript
        
        # Process transcript if enabled
        sections = {}
        tags = []
        pvi_fields = {}
        confidence = 0.0
        
        if auto_process and text_to_process:
            sections, tags, pvi_fields, confidence = process_transcript(text_to_process)
        
        # Create transcript record with PlaudAI-specific fields
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
        
        logger.info(f"Created transcript {transcript.id} for patient {patient.id}")
        
        # Optionally create PVI procedure record if enough fields extracted
        pvi_procedure_id = None
        if pvi_fields and len(pvi_fields) >= 3:  # Minimum fields threshold
            try:
                pvi_procedure_id = create_pvi_procedure(
                    db, patient.id, transcript.id, pvi_fields
                )
            except Exception as e:
                logger.warning(f"Could not create PVI procedure: {e}")
        
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
        logger.error(f"Upload failed: {e}")
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
    
    procedure = PVIProcedure(
        patient_id=patient_id,
        transcript_id=transcript_id,
        **pvi_fields
    )
    
    db.add(procedure)
    db.commit()
    db.refresh(procedure)
    
    logger.info(f"Created PVI procedure {procedure.id} for transcript {transcript_id}")
    return procedure.id

# ==================== Batch Upload ====================

def batch_upload_transcripts(
    db: Session,
    items: list
) -> Dict[str, Any]:
    """
    Upload multiple transcripts in batch
    
    Args:
        db: Database session
        items: List of dicts with 'patient_data' and 'transcript_text'
    
    Returns:
        Summary of batch upload results
    """
    results = {
        "total": len(items),
        "successful": 0,
        "failed": 0,
        "details": []
    }
    
    for idx, item in enumerate(items):
        try:
            result = upload_transcript(
                db,
                patient_data=item.get("patient_data", {}),
                summary_text=item.get("transcript_text", ""),
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
            results["details"].append({
                "index": idx,
                "status": "failed",
                "error": str(e)
            })
            logger.error(f"Batch item {idx} failed: {e}")
    
    return results

# ==================== Query Helpers ====================

def get_patient_transcripts(db: Session, patient_id: int) -> list:
    """Get all transcripts for a patient"""
    return db.query(VoiceTranscript).filter_by(patient_id=patient_id).all()

def get_patient_procedures(db: Session, patient_id: int) -> list:
    """Get all PVI procedures for a patient"""
    return db.query(PVIProcedure).filter_by(patient_id=patient_id).all()

def search_patients(db: Session, search_term: str) -> list:
    """Search patients by name or MRN"""
    return db.query(Patient).filter(
        (Patient.first_name.ilike(f"%{search_term}%")) |
        (Patient.last_name.ilike(f"%{search_term}%")) |
        (Patient.athena_mrn.ilike(f"%{search_term}%"))
    ).all()