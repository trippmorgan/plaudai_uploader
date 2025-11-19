"""
PlaudAI Uploader - Database Upload Service
Handles patient creation, transcript storage, and logging
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