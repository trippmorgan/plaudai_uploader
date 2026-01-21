"""
=============================================================================
SHADOW CODER API ROUTES
=============================================================================

Migrated from SCC Node.js (scc-shadow-coder) to PlaudAI Python

ENDPOINTS:
    POST /api/shadow-coder/intake/plaud    - Voice note ingestion from Plaud
    POST /api/shadow-coder/intake/zapier   - Zapier webhook
    POST /api/shadow-coder/intake/batch    - Batch import
    GET  /api/shadow-coder/intake/status/{id} - Get voice note status
    GET  /api/shadow-coder/intake/recent   - Recent voice notes

    GET  /api/shadow-coder/facts/{case_id}     - Get case facts
    POST /api/shadow-coder/facts/{case_id}     - Add fact to case
    GET  /api/shadow-coder/facts/{case_id}/history - Full fact history

    GET  /api/shadow-coder/prompts/{case_id}   - Get active prompts
    GET  /api/shadow-coder/prompts/{case_id}/summary - Prompt counts
    POST /api/shadow-coder/prompts/{id}/action - Execute prompt action

    POST /api/shadow-coder/analyze         - Analyze transcript (one-shot)

=============================================================================
"""
import os
import hashlib
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel, Field
from sqlalchemy import text, create_engine
from sqlalchemy.orm import sessionmaker, Session

from ..services.shadow_coder import TranscriptExtractor, FactsService, RulesEngine

# ==================== Logging ====================
logger = logging.getLogger(__name__)

# ==================== Database Connection ====================
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    f"postgresql://{os.getenv('DB_USER', 'scc_user')}:{os.getenv('DB_PASSWORD', 'scc_password')}@{os.getenv('DB_HOST', 'localhost')}:{os.getenv('DB_PORT', '5432')}/{os.getenv('DB_NAME', 'surgical_command_center')}"
)

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ==================== Services ====================
extractor = TranscriptExtractor()


def get_facts_service(db: Session = Depends(get_db)) -> FactsService:
    return FactsService(db)


def get_rules_engine(
    db: Session = Depends(get_db),
    facts_service: FactsService = Depends(get_facts_service)
) -> RulesEngine:
    return RulesEngine(db, facts_service)


# ==================== Router ====================
router = APIRouter(prefix="/api/shadow-coder", tags=["Shadow Coder"])


# ==================== Pydantic Models ====================

class PlaudIntakeRequest(BaseModel):
    """Request body for Plaud voice note ingestion."""
    transcript: str = Field(..., min_length=1, description="Voice note transcript")
    summary: Optional[str] = None
    mrn: Optional[str] = None
    patient_name: Optional[str] = None
    captured_at: Optional[datetime] = None
    audio_ref: Optional[str] = None
    case_id: Optional[str] = None
    patient_id: Optional[str] = None
    provenance: Optional[Dict[str, Any]] = Field(default_factory=dict)

    class Config:
        json_schema_extra = {
            "example": {
                "transcript": "Patient presents with left leg claudication at two blocks...",
                "mrn": "12345678",
                "patient_name": "John Smith",
                "provenance": {"source": "plaud"}
            }
        }


class ZapierIntakeRequest(BaseModel):
    """Flexible request for Zapier webhook - accepts various field names."""
    # Zapier can send data in many formats
    transcript: Optional[str] = None
    text: Optional[str] = None
    content: Optional[str] = None
    transcription: Optional[str] = None
    note_text: Optional[str] = None
    body: Optional[str] = None

    summary: Optional[str] = None
    title: Optional[str] = None
    subject: Optional[str] = None

    mrn: Optional[str] = None
    patient_mrn: Optional[str] = None
    medical_record_number: Optional[str] = None
    MRN: Optional[str] = None
    chart_number: Optional[str] = None

    patient_name: Optional[str] = None
    name: Optional[str] = None
    patient: Optional[str] = None
    full_name: Optional[str] = None

    captured_at: Optional[datetime] = None
    date: Optional[datetime] = None
    timestamp: Optional[datetime] = None
    created_at: Optional[datetime] = None
    recording_date: Optional[datetime] = None

    audio_url: Optional[str] = None
    audio_ref: Optional[str] = None
    recording_url: Optional[str] = None
    file_url: Optional[str] = None

    zap_id: Optional[str] = None
    trigger_source: Optional[str] = None
    trigger: Optional[str] = None


class AddFactRequest(BaseModel):
    """Request to add a fact to a case."""
    fact_type: str
    value: Any
    confidence: float = 1.0
    source_type: str = "manual"
    source_ref: Optional[Dict[str, Any]] = None


class PromptActionRequest(BaseModel):
    """Request to execute a prompt action."""
    action_id: str
    note: Optional[str] = None
    resolved_by: Optional[str] = None


class AnalyzeRequest(BaseModel):
    """Request for one-shot transcript analysis."""
    transcript: str
    patient_context: Optional[Dict[str, Any]] = None


# ==================== Helper Functions ====================

def generate_content_hash(transcript: str, captured_at: Optional[datetime] = None) -> str:
    """Generate SHA-256 hash for deduplication."""
    hash_input = transcript + (captured_at.isoformat() if captured_at else datetime.now().isoformat())
    return hashlib.sha256(hash_input.encode()).hexdigest()


def resolve_case_from_mrn(mrn: Optional[str], db: Session) -> Dict[str, Any]:
    """
    Resolve case ID from MRN by looking up patient/procedure.

    Returns dict with case_id, patient_id, source
    """
    if not mrn:
        return {"case_id": str(uuid4()), "patient_id": None, "source": "generated"}

    # Try to find patient in scc_patients
    try:
        result = db.execute(
            text("SELECT id FROM scc_patients WHERE mrn = :mrn LIMIT 1"),
            {"mrn": mrn}
        )
        patient = result.fetchone()

        if patient:
            patient_id = str(patient[0])

            # Look for recent procedure
            proc_result = db.execute(
                text("""
                    SELECT id FROM procedures
                    WHERE mrn = :mrn
                    ORDER BY "createdAt" DESC
                    LIMIT 1
                """),
                {"mrn": mrn}
            )
            proc = proc_result.fetchone()

            if proc:
                return {
                    "case_id": str(proc[0]),
                    "patient_id": patient_id,
                    "source": "scc_procedure"
                }

            return {
                "case_id": patient_id,
                "patient_id": patient_id,
                "source": "scc_patient"
            }
    except Exception as e:
        logger.warning(f"Patient lookup failed: {e}")

    # Generate deterministic UUID from MRN
    hash_val = hashlib.md5(f"case-mrn-{mrn}".encode()).hexdigest()
    deterministic_uuid = f"{hash_val[:8]}-{hash_val[8:12]}-4{hash_val[13:16]}-8{hash_val[17:20]}-{hash_val[20:32]}"

    return {"case_id": deterministic_uuid, "patient_id": None, "source": "mrn_hash"}


# ==================== Intake Endpoints ====================

@router.post("/intake/plaud")
async def intake_plaud(
    request: PlaudIntakeRequest,
    db: Session = Depends(get_db)
):
    """
    Main ingestion endpoint for Plaud voice notes.

    Processes transcript, extracts facts, evaluates rules.
    """
    start_time = datetime.utcnow()

    transcript = request.transcript.strip()
    content_hash = generate_content_hash(transcript, request.captured_at)

    # Check for duplicate
    check_result = db.execute(
        text("SELECT id, provenance FROM scc_voice_notes WHERE content_hash = :hash"),
        {"hash": content_hash}
    )
    existing = check_result.fetchone()

    if existing:
        return {
            "success": True,
            "duplicate": True,
            "message": "Duplicate note suppressed",
            "voice_note_id": str(existing[0]),
            "case_id": existing[1].get("resolved_case_id") if existing[1] else None
        }

    # Resolve case from MRN
    case_resolution = resolve_case_from_mrn(request.mrn, db)
    target_case_id = request.case_id or case_resolution["case_id"]
    target_patient_id = request.patient_id or case_resolution["patient_id"]

    # Create voice note record
    provenance = {
        **(request.provenance or {}),
        "source": request.provenance.get("source", "plaud") if request.provenance else "plaud",
        "ingested_at": datetime.utcnow().isoformat(),
        "resolved_case_id": target_case_id,
        "case_resolution_source": case_resolution["source"]
    }

    insert_result = db.execute(
        text("""
            INSERT INTO scc_voice_notes (
                id, transcript, summary, content_hash, audio_ref,
                mrn, patient_name, captured_at, status, provenance,
                "createdAt", "updatedAt"
            ) VALUES (
                gen_random_uuid(), :transcript, :summary, :content_hash, :audio_ref,
                :mrn, :patient_name, :captured_at, 'processing', :provenance::jsonb,
                NOW(), NOW()
            )
            RETURNING id::text
        """),
        {
            "transcript": transcript,
            "summary": request.summary,
            "content_hash": content_hash,
            "audio_ref": request.audio_ref,
            "mrn": request.mrn,
            "patient_name": request.patient_name,
            "captured_at": request.captured_at or datetime.utcnow(),
            "provenance": str(provenance).replace("'", '"')
        }
    )
    db.commit()
    voice_note_id = insert_result.fetchone()[0]

    # Extract facts using Claude
    extraction_result = {"success": False, "facts": [], "missing_for_coding": []}
    facts_stored = 0

    if extractor.is_available:
        try:
            extraction_result = await extractor.extract_pad_facts(
                transcript,
                {"patient_name": request.patient_name, "mrn": request.mrn}
            )

            # Update voice note with extraction results
            db.execute(
                text("""
                    UPDATE scc_voice_notes
                    SET extracted_facts_raw = :facts::jsonb,
                        summary = COALESCE(:summary, summary),
                        status = :status,
                        "updatedAt" = NOW()
                    WHERE id = :id::uuid
                """),
                {
                    "id": voice_note_id,
                    "facts": str(extraction_result).replace("'", '"'),
                    "summary": extraction_result.get("summary"),
                    "status": "extracted" if extraction_result["success"] else "failed"
                }
            )
            db.commit()

            # Store extracted facts
            if extraction_result["success"] and extraction_result.get("facts"):
                facts_service = FactsService(db)
                stored = await facts_service.add_facts_batch(
                    target_case_id,
                    extraction_result["facts"],
                    voice_note_id,
                    target_patient_id
                )
                facts_stored = len(stored)

        except Exception as e:
            logger.error(f"Extraction error: {e}", exc_info=True)
            db.execute(
                text("""
                    UPDATE scc_voice_notes
                    SET status = 'failed',
                        error_log = :error::jsonb,
                        "updatedAt" = NOW()
                    WHERE id = :id::uuid
                """),
                {"id": voice_note_id, "error": f'{{"extraction_error": "{str(e)}"}}'}
            )
            db.commit()

    # Run rules engine
    rules_result = {"rules_evaluated": 0, "prompts_created": 0, "prompts_resolved": 0}
    try:
        facts_service = FactsService(db)
        rules_engine = RulesEngine(db, facts_service)
        rules_result = await rules_engine.evaluate_pad_rules(target_case_id)
    except Exception as e:
        logger.error(f"Rules evaluation error: {e}")
        rules_result["error"] = str(e)

    processing_time = int((datetime.utcnow() - start_time).total_seconds() * 1000)

    return {
        "success": True,
        "voice_note_id": voice_note_id,
        "case_id": target_case_id,
        "patient_id": target_patient_id,
        "case_resolution": case_resolution["source"],
        "extraction": {
            "success": extraction_result["success"],
            "facts_extracted": len(extraction_result.get("facts", [])),
            "facts_stored": facts_stored,
            "summary": extraction_result.get("summary"),
            "missing_for_coding": extraction_result.get("missing_for_coding", [])
        },
        "rules": {
            "evaluated": rules_result.get("rules_evaluated", 0),
            "prompts_created": rules_result.get("prompts_created", 0),
            "prompts_resolved": rules_result.get("prompts_resolved", 0),
            "error": rules_result.get("error")
        },
        "processing_time_ms": processing_time
    }


@router.post("/intake/zapier")
async def intake_zapier(
    request: ZapierIntakeRequest,
    db: Session = Depends(get_db)
):
    """
    Webhook endpoint for Zapier integration.
    Normalizes various payload formats.
    """
    # Normalize the transcript from various possible field names
    transcript = (
        request.transcript or
        request.text or
        request.content or
        request.transcription or
        request.note_text or
        request.body
    )

    if not transcript:
        raise HTTPException(
            status_code=400,
            detail="No transcript found. Tried: transcript, text, content, transcription, note_text, body"
        )

    # Build normalized request
    plaud_request = PlaudIntakeRequest(
        transcript=transcript,
        summary=request.summary or request.title or request.subject,
        mrn=request.mrn or request.patient_mrn or request.medical_record_number or request.MRN or request.chart_number,
        patient_name=request.patient_name or request.name or request.patient or request.full_name,
        captured_at=request.captured_at or request.date or request.timestamp or request.created_at or request.recording_date,
        audio_ref=request.audio_url or request.audio_ref or request.recording_url or request.file_url,
        provenance={
            "source": "zapier",
            "zap_id": request.zap_id,
            "trigger": request.trigger_source or request.trigger
        }
    )

    # Process using plaud handler
    result = await intake_plaud(plaud_request, db)
    result["source"] = "zapier"
    return result


@router.get("/intake/status/{note_id}")
async def get_intake_status(note_id: str, db: Session = Depends(get_db)):
    """Get processing status of a voice note."""
    result = db.execute(
        text("""
            SELECT id::text, status::text, mrn, patient_name, captured_at,
                   "createdAt", summary, provenance, error_log
            FROM scc_voice_notes
            WHERE id = :id::uuid
        """),
        {"id": note_id}
    )
    row = result.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Voice note not found")

    return {
        "success": True,
        "id": row[0],
        "status": row[1],
        "mrn": row[2],
        "patient_name": row[3],
        "captured_at": row[4].isoformat() if row[4] else None,
        "created_at": row[5].isoformat() if row[5] else None,
        "summary": row[6],
        "case_id": row[7].get("resolved_case_id") if row[7] else None,
        "error": row[8]
    }


@router.get("/intake/recent")
async def get_recent_intakes(
    limit: int = Query(20, ge=1, le=100),
    status: Optional[str] = None,
    mrn: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Get recent voice notes."""
    sql = """
        SELECT id::text, mrn, patient_name, status::text, captured_at,
               "createdAt", summary
        FROM scc_voice_notes
        WHERE 1=1
    """
    params = {"limit": limit}

    if status:
        sql += " AND status = :status::enum_voice_note_status"
        params["status"] = status

    if mrn:
        sql += " AND mrn = :mrn"
        params["mrn"] = mrn

    sql += ' ORDER BY "createdAt" DESC LIMIT :limit'

    result = db.execute(text(sql), params)
    rows = result.fetchall()

    return {
        "success": True,
        "count": len(rows),
        "data": [
            {
                "id": row[0],
                "mrn": row[1],
                "patient_name": row[2],
                "status": row[3],
                "captured_at": row[4].isoformat() if row[4] else None,
                "created_at": row[5].isoformat() if row[5] else None,
                "summary": row[6]
            }
            for row in rows
        ]
    }


# ==================== Facts Endpoints ====================

@router.get("/facts/{case_id}")
async def get_case_facts(
    case_id: str,
    facts_service: FactsService = Depends(get_facts_service)
):
    """Get current fact map for a case."""
    fact_map = await facts_service.get_fact_map(case_id)
    return {"success": True, "case_id": case_id, "facts": fact_map}


@router.post("/facts/{case_id}")
async def add_case_fact(
    case_id: str,
    request: AddFactRequest,
    facts_service: FactsService = Depends(get_facts_service)
):
    """Add a fact to a case."""
    fact = await facts_service.add_fact(
        case_id=case_id,
        fact_type=request.fact_type,
        value=request.value,
        confidence=request.confidence,
        source_type=request.source_type,
        source_ref=request.source_ref
    )
    return {"success": True, "fact": fact}


@router.get("/facts/{case_id}/history")
async def get_fact_history(
    case_id: str,
    fact_type: Optional[str] = None,
    facts_service: FactsService = Depends(get_facts_service)
):
    """Get full fact history for a case."""
    history = await facts_service.get_fact_history(case_id, fact_type)
    return {"success": True, "case_id": case_id, "history": history}


# ==================== Prompts Endpoints ====================

@router.get("/prompts/{case_id}")
async def get_case_prompts(
    case_id: str,
    rules_engine: RulesEngine = Depends(get_rules_engine)
):
    """Get active prompts for a case."""
    prompts = await rules_engine.get_active_prompts(case_id)
    return {"success": True, "case_id": case_id, "prompts": prompts}


@router.get("/prompts/{case_id}/summary")
async def get_prompt_summary(
    case_id: str,
    rules_engine: RulesEngine = Depends(get_rules_engine)
):
    """Get prompt counts by severity."""
    summary = await rules_engine.get_prompt_summary(case_id)
    return {"success": True, "case_id": case_id, "summary": summary}


@router.post("/prompts/{prompt_id}/action")
async def execute_prompt_action(
    prompt_id: str,
    request: PromptActionRequest,
    db: Session = Depends(get_db)
):
    """Execute an action on a prompt (resolve, snooze, dismiss)."""
    action = request.action_id.upper()

    if action == "DISMISS":
        sql = text("""
            UPDATE scc_prompt_instances
            SET status = 'dismissed',
                resolution_type = 'manual_dismiss',
                resolution_note = :note,
                resolved_by = :resolved_by,
                resolved_at = NOW(),
                "updatedAt" = NOW()
            WHERE id = :id::uuid
            RETURNING id::text
        """)
    elif action.startswith("SNOOZE"):
        hours = 24  # Default
        if "_" in action:
            try:
                hours = int(action.split("_")[1].replace("H", ""))
            except:
                pass
        sql = text(f"""
            UPDATE scc_prompt_instances
            SET status = 'snoozed',
                snoozed_until = NOW() + INTERVAL '{hours} hours',
                snooze_count = snooze_count + 1,
                "updatedAt" = NOW()
            WHERE id = :id::uuid
            RETURNING id::text
        """)
    elif action == "DOCUMENT" or action == "RESOLVE":
        sql = text("""
            UPDATE scc_prompt_instances
            SET status = 'resolved',
                resolution_type = 'attestation',
                resolution_note = :note,
                resolved_by = :resolved_by,
                resolved_at = NOW(),
                "updatedAt" = NOW()
            WHERE id = :id::uuid
            RETURNING id::text
        """)
    else:
        raise HTTPException(status_code=400, detail=f"Unknown action: {action}")

    try:
        result = db.execute(sql, {
            "id": prompt_id,
            "note": request.note,
            "resolved_by": request.resolved_by
        })
        db.commit()

        if not result.fetchone():
            raise HTTPException(status_code=404, detail="Prompt not found")

        return {"success": True, "prompt_id": prompt_id, "action": action}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


# ==================== Analysis Endpoint ====================

@router.post("/analyze")
async def analyze_transcript(request: AnalyzeRequest):
    """
    One-shot transcript analysis without storage.
    Returns extracted facts, missing elements, and coding suggestions.
    """
    if not extractor.is_available:
        raise HTTPException(
            status_code=503,
            detail="Claude API not configured. Set ANTHROPIC_API_KEY environment variable."
        )

    start_time = datetime.utcnow()

    # Extract facts
    extraction = await extractor.extract_pad_facts(
        request.transcript,
        request.patient_context
    )

    # Also extract procedure details
    procedure_details = await extractor.extract_procedure_details(request.transcript)

    processing_time = int((datetime.utcnow() - start_time).total_seconds() * 1000)

    return {
        "success": extraction["success"],
        "extraction": {
            "facts": extraction.get("facts", []),
            "summary": extraction.get("summary"),
            "missing_for_coding": extraction.get("missing_for_coding", [])
        },
        "procedure_analysis": procedure_details,
        "processing_time_ms": processing_time
    }


# ==================== Health Check ====================

@router.get("/status")
async def shadow_coder_status(db: Session = Depends(get_db)):
    """Shadow Coder service status."""
    # Check database
    try:
        db.execute(text("SELECT 1"))
        db_status = "connected"
    except:
        db_status = "disconnected"

    # Check tables exist
    tables_exist = False
    try:
        db.execute(text("SELECT 1 FROM scc_voice_notes LIMIT 1"))
        db.execute(text("SELECT 1 FROM scc_case_facts LIMIT 1"))
        db.execute(text("SELECT 1 FROM scc_prompt_instances LIMIT 1"))
        tables_exist = True
    except:
        pass

    return {
        "status": "healthy" if db_status == "connected" and tables_exist else "degraded",
        "service": "shadow-coder",
        "database": db_status,
        "tables_exist": tables_exist,
        "claude_api": "configured" if extractor.is_available else "not_configured",
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }
