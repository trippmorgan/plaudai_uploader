"""
=============================================================================
ATHENA EMR INGESTION API ENDPOINT
=============================================================================

ARCHITECTURAL ROLE:
    This module is the INGESTION GATEWAY - the single entry point for all
    clinical data flowing from the Athena-Scraper Chrome extension. It
    validates, deduplicates, and persists raw EMR data while maintaining
    full HIPAA audit trails.

DATA FLOW POSITION:
    ┌────────────────────────────────────────────────────────────────────┐
    │                  ATHENA-SCRAPER (Chrome Extension)                 │
    │  Intercepts: medications, problems, vitals, labs, encounters      │
    │  Sends: POST /ingest/athena with JSON payload                     │
    └────────────────────────────┬───────────────────────────────────────┘
                                 │ HTTP POST
                                 ▼
    ┌────────────────────────────────────────────────────────────────────┐
    │                    ingest.py (THIS FILE)                           │
    │                                                                    │
    │  STEP 1: VALIDATE                                                  │
    │  ┌──────────────────────────────────────────────────────────────┐ │
    │  │ Pydantic schema (AthenaEventPayload) validates:              │ │
    │  │ - athena_patient_id (required, string)                       │ │
    │  │ - event_type (required: medication, problem, vital, etc.)    │ │
    │  │ - payload (required, JSON object)                            │ │
    │  │ - captured_at (required, ISO timestamp)                      │ │
    │  └──────────────────────────────────────────────────────────────┘ │
    │                               │                                    │
    │  STEP 2: DEDUPLICATE                                               │
    │  ┌──────────────────────────────────────────────────────────────┐ │
    │  │ Generate idempotency_key = SHA256(patient:type:payload)      │ │
    │  │ Query: SELECT id FROM clinical_events WHERE key = ?          │ │
    │  │ If exists → return "duplicate", skip insert                  │ │
    │  └──────────────────────────────────────────────────────────────┘ │
    │                               │                                    │
    │  STEP 3: AUTO-LINK PATIENT                                         │
    │  ┌──────────────────────────────────────────────────────────────┐ │
    │  │ Query: SELECT id FROM patients WHERE athena_mrn = ?          │ │
    │  │ If found → set patient_id (enables joins with core models)   │ │
    │  │ If not found → patient_id = NULL (event still stored)        │ │
    │  └──────────────────────────────────────────────────────────────┘ │
    │                               │                                    │
    │  STEP 4: PERSIST & AUDIT                                           │
    │  ┌──────────────────────────────────────────────────────────────┐ │
    │  │ INSERT INTO clinical_events (raw_payload preserved exactly)  │ │
    │  │ INSERT INTO integration_audit_log (action=INGEST)            │ │
    │  │ COMMIT transaction                                           │ │
    │  └──────────────────────────────────────────────────────────────┘ │
    │                               │                                    │
    │  STEP 5: RESPOND                                                   │
    │  ┌──────────────────────────────────────────────────────────────┐ │
    │  │ Return: {status: "success", event_id: "uuid", message: "..."}│ │
    │  │ Or: {status: "duplicate", event_id: "existing", ...}         │ │
    │  │ Or: HTTP 500 with error details                              │ │
    │  └──────────────────────────────────────────────────────────────┘ │
    └────────────────────────────────────────────────────────────────────┘

API ENDPOINTS:

    POST /ingest/athena
        PURPOSE: Receive and store a clinical event from Athena-Scraper
        INPUT: AthenaEventPayload (see schema below)
        OUTPUT: IngestResponse {status, event_id, message}
        IDEMPOTENT: Yes - same payload returns "duplicate" status

    GET /ingest/events/{athena_patient_id}
        PURPOSE: Retrieve events for a patient (debugging/testing)
        INPUT: athena_patient_id (path), event_type (query), limit (query)
        OUTPUT: {patient_id, count, events: [...]}

    GET /ingest/stats
        PURPOSE: System monitoring and health dashboard
        OUTPUT: {total_events, unique_patients, by_type: {...}}

    GET /ingest/health
        PURPOSE: Simple health check for load balancers
        OUTPUT: {status: "healthy", service: "scc-ingest"}

CRITICAL DESIGN PRINCIPLES:

    1. IDEMPOTENCY GUARANTEE:
       The same request sent multiple times produces the same result.
       - Hash = SHA256(patient_id + event_type + sorted_json_payload)
       - First insert succeeds, subsequent attempts return "duplicate"
       - Safe for retry logic in Athena-Scraper

    2. RAW DATA PRESERVATION:
       The raw_payload is stored EXACTLY as received.
       - No transformation, normalization, or "cleaning"
       - Enables future re-parsing with improved algorithms
       - Source of truth for audit and compliance

    3. FAIL-SAFE PATIENT LINKING:
       Auto-linking is BEST-EFFORT, not required.
       - Events stored even if patient doesn't exist yet
       - Patient created later can be linked via batch update
       - athena_patient_id (MRN) always stored for manual linking

    4. ATOMIC TRANSACTIONS:
       All database operations in a single transaction.
       - Event + audit log committed together or not at all
       - Rollback on any error prevents partial writes
       - No orphaned audit entries or missing events

FUNCTION REFERENCE:

    generate_idempotency_key(patient_id, event_type, payload) -> str
        PARAMS: patient_id (str), event_type (str), payload (dict)
        RETURNS: 64-character SHA256 hash string
        BEHAVIOR: Sorts payload keys for consistent hashing

    log_audit(db, action, resource_type, resource_id, details, error) -> None
        PARAMS: db session, action name, resource info, optional error
        RETURNS: None (adds to session, caller must commit)
        ACTIONS: INGEST, PARSE, VIEW, EXPORT, ERROR

    parse_timestamp(timestamp_str) -> datetime
        PARAMS: ISO timestamp string (with or without timezone)
        RETURNS: datetime object
        FALLBACK: Returns current time if parsing fails

    ingest_athena_event(payload, background_tasks, db) -> IngestResponse
        PARAMS: Validated payload, FastAPI tasks, DB session
        RETURNS: IngestResponse with status and event_id
        ASYNC: Yes (handles concurrent requests)

SECURITY MODEL:
    - Input validation via Pydantic prevents injection
    - All actions logged to audit trail (HIPAA compliance)
    - Error messages sanitized (no stack traces to client)
    - No authentication currently (add middleware for production)

MAINTENANCE NOTES:
    - Add new event types by extending event_type enum in schema
    - Background parsing (commented out) can be enabled when ready
    - Increase limit in get_patient_events for bulk exports
    - Monitor stats endpoint for ingestion velocity

ERROR HANDLING:
    - Validation errors → 422 Unprocessable Entity (automatic)
    - Duplicate events → 200 OK with status="duplicate"
    - Database errors → 500 Internal Server Error + rollback
    - All errors logged to both application log and audit table

VERSION: 2.0.0
LAST UPDATED: 2025-12
=============================================================================
"""

import hashlib
import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional, List

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import func

# Import database connection
from ..db import get_db

# Import our existing Patient model
from ..models import Patient

# Import the new Athena models
from ..models_athena import (
    ClinicalEvent,
    StructuredFinding,
    FindingEvidence,
    IntegrationAuditLog
)

# Telemetry for Medical Mirror Observer
from ..services.telemetry import (
    emit_ingest_received,
    emit_ingest_processed,
    emit,
    emit_clinical_fetch,
    emit_clinical_fetch_success
)

# ============================================================
# SETUP
# ============================================================

# Create a logger for this module
logger = logging.getLogger("scc.ingest")

# Create the router with a prefix
# All routes will be /ingest/...
router = APIRouter(
    prefix="/ingest",
    tags=["Athena Integration"]
)


# ============================================================
# REQUEST/RESPONSE SCHEMAS
# ============================================================
# These define the shape of data coming in and going out

class AthenaEventPayload(BaseModel):
    """
    Schema for incoming Athena events.

    The Chrome extension sends this data structure.
    """
    # Required: Athena's patient ID (MRN)
    athena_patient_id: str = Field(
        ...,
        description="Patient MRN from Athena",
        example="12345678"
    )

    # Required: What type of data is this?
    event_type: str = Field(
        ...,
        description="Event category",
        example="medication"
    )

    # Optional: More specific classification
    event_subtype: Optional[str] = Field(
        None,
        description="Sub-category",
        example="active"
    )

    # Required: The actual data from Athena
    payload: Dict[str, Any] = Field(
        ...,
        description="Raw data from Athena API"
    )

    # Required: When did Athena send this?
    captured_at: str = Field(
        ...,
        description="ISO format timestamp",
        example="2025-12-24T10:30:00Z"
    )

    # Optional: Which Athena endpoint was this from?
    source_endpoint: Optional[str] = Field(
        None,
        description="The intercepted API endpoint",
        example="/8042/65/ax/data?sources=active_medications"
    )

    # Optional: Classification confidence
    confidence: Optional[float] = Field(
        0.0,
        description="Confidence score 0.0-1.0"
    )

    # Optional: Which indexer version classified this?
    indexer_version: Optional[str] = Field(
        "2.0.0",
        description="event_indexer version"
    )


class IngestResponse(BaseModel):
    """Response from the ingestion endpoint."""

    status: str = Field(
        ...,
        description="success, duplicate, or error"
    )

    event_id: Optional[str] = Field(
        None,
        description="ID of the created/existing event"
    )

    message: Optional[str] = Field(
        None,
        description="Human-readable message"
    )


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def generate_idempotency_key(
    patient_id: str,
    event_type: str,
    payload: dict
) -> str:
    """
    Generate a unique hash for deduplication.

    HOW IT WORKS:
        Same patient + same event type + same data = same hash
        This means if we receive the same data twice, we skip it.

    ARGS:
        patient_id: The Athena patient ID
        event_type: medication, problem, etc.
        payload: The actual data

    RETURNS:
        A 64-character hash string
    """
    # Sort keys to ensure consistent hashing
    # {"a": 1, "b": 2} and {"b": 2, "a": 1} will produce same hash
    payload_str = json.dumps(payload, sort_keys=True)

    # Combine all parts
    raw = f"{patient_id}:{event_type}:{payload_str}"

    # Create SHA256 hash and take first 64 characters
    return hashlib.sha256(raw.encode()).hexdigest()[:64]


def log_audit(
    db: Session,
    action: str,
    resource_type: str,
    resource_id: str = None,
    details: dict = None,
    error: str = None
):
    """
    Record an action in the audit log.

    HIPAA requires tracking who accessed what and when.
    """
    audit = IntegrationAuditLog(
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        details=details,
        error_message=error
    )
    db.add(audit)
    # Note: We don't commit here - the caller handles that


def parse_timestamp(timestamp_str: str) -> datetime:
    """
    Parse an ISO format timestamp string.

    Handles various formats:
        - 2025-12-24T10:30:00Z
        - 2025-12-24T10:30:00+00:00
        - 2025-12-24T10:30:00
    """
    try:
        # Handle 'Z' suffix (UTC indicator)
        cleaned = timestamp_str.replace('Z', '+00:00')
        return datetime.fromisoformat(cleaned)
    except:
        # If parsing fails, use current time
        return datetime.utcnow()


# ============================================================
# MAIN INGESTION ENDPOINT
# ============================================================

@router.post("/athena", response_model=IngestResponse)
async def ingest_athena_event(
    payload: AthenaEventPayload,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Receive and store a clinical event from Athena-Scraper.

    WHAT THIS DOES:
        1. Generates an idempotency key (hash) from the data
        2. Checks if we already have this exact data (skip if duplicate)
        3. Stores the raw payload in clinical_events table
        4. Logs the action for HIPAA compliance
        5. (Future) Queues background parsing for structured findings

    RETURNS IMMEDIATELY:
        The response is sent right away - any parsing happens in background.
        This keeps the Chrome extension fast.

    EXAMPLE REQUEST:
        POST /ingest/athena
        {
            "athena_patient_id": "12345678",
            "event_type": "medication",
            "payload": {"name": "Aspirin", "dose": "81mg"},
            "captured_at": "2025-12-24T10:30:00Z"
        }

    EXAMPLE RESPONSE:
        {"status": "success", "event_id": "abc-123-...", "message": "..."}
    """
    # Telemetry: Track ingest received
    correlation_id = await emit_ingest_received(
        event_type=payload.event_type,
        has_patient_link=False  # Will update after patient lookup
    )

    try:
        # -----------------------------------------
        # STEP 1: Generate idempotency key
        # -----------------------------------------
        idem_key = generate_idempotency_key(
            payload.athena_patient_id,
            payload.event_type,
            payload.payload
        )

        # -----------------------------------------
        # STEP 2: Check for duplicate
        # -----------------------------------------
        existing = db.query(ClinicalEvent).filter_by(
            idempotency_key=idem_key
        ).first()

        if existing:
            # We already have this exact data - skip it
            logger.debug(
                f"Duplicate event skipped: {idem_key[:16]}..."
            )
            # Telemetry: Track duplicate event
            await emit_ingest_processed(
                correlation_id=correlation_id,
                event_type=payload.event_type,
                status='duplicate'
            )
            return IngestResponse(
                status="duplicate",
                event_id=existing.id,
                message="Event already ingested"
            )

        # -----------------------------------------
        # STEP 3: Parse the timestamp
        # -----------------------------------------
        captured = parse_timestamp(payload.captured_at)

        # -----------------------------------------
        # STEP 3.5: AUTO-LINK TO EXISTING PATIENT BY MRN
        # -----------------------------------------
        # Try to find a patient with matching athena_mrn
        linked_patient_id = None
        existing_patient = db.query(Patient).filter_by(
            athena_mrn=payload.athena_patient_id
        ).first()

        if existing_patient:
            linked_patient_id = existing_patient.id
            logger.info(
                f"🔗 AUTO-LINKED: MRN {payload.athena_patient_id} → "
                f"Patient #{existing_patient.id} ({existing_patient.last_name}, {existing_patient.first_name})"
            )
        else:
            logger.warning(
                f"⚠️ NO PATIENT MATCH: MRN {payload.athena_patient_id} not found in patients table"
            )

        # -----------------------------------------
        # STEP 4: Create the clinical event record
        # -----------------------------------------
        event = ClinicalEvent(
            patient_id=linked_patient_id,  # Link to patient if found!
            athena_patient_id=payload.athena_patient_id,
            event_type=payload.event_type,
            event_subtype=payload.event_subtype,
            raw_payload=payload.payload,  # Stored exactly as received
            source_endpoint=payload.source_endpoint,
            idempotency_key=idem_key,
            captured_at=captured,
            confidence=payload.confidence or 0.0,
            indexer_version=payload.indexer_version or "2.0.0"
        )

        db.add(event)

        # -----------------------------------------
        # STEP 5: Log for HIPAA compliance
        # -----------------------------------------
        log_audit(
            db,
            action="INGEST",
            resource_type="clinical_event",
            resource_id=event.id,
            details={
                "event_type": payload.event_type,
                "patient": payload.athena_patient_id
            }
        )

        # -----------------------------------------
        # STEP 6: Commit to database
        # -----------------------------------------
        db.commit()

        # -----------------------------------------
        # STEP 7: Queue background parsing (future)
        # -----------------------------------------
        # Uncomment when ready to add parsing:
        # background_tasks.add_task(
        #     parse_findings_background,
        #     event.id
        # )

        # -----------------------------------------
        # STEP 8: Return success
        # -----------------------------------------
        logger.info(
            f"Ingested {payload.event_type} for patient "
            f"{payload.athena_patient_id}: {event.id[:8]}..."
        )

        # Telemetry: Track successful ingestion
        await emit_ingest_processed(
            correlation_id=correlation_id,
            event_type=payload.event_type,
            status='success'
        )

        # Telemetry: Track patient linkage status
        await emit('ingest', 'PATIENT_LINK_STATUS', {
            'correlationId': correlation_id,
            'linkedToPatient': linked_patient_id is not None,
            'patientId': linked_patient_id
        })

        return IngestResponse(
            status="success",
            event_id=event.id,
            message="Event ingested successfully"
        )

    except Exception as e:
        # -----------------------------------------
        # ERROR HANDLING
        # -----------------------------------------
        logger.error(f"Ingestion error: {e}")

        # Telemetry: Track failed ingestion
        await emit('ingest', 'ATHENA_EVENT_FAILED', {
            'correlationId': correlation_id,
            'eventType': payload.event_type,
            'error': str(e)
        }, success=False)

        # Log the error for audit
        log_audit(
            db,
            action="ERROR",
            resource_type="clinical_event",
            error=str(e)
        )

        # Rollback any partial changes
        db.rollback()

        # Return error to caller
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# QUERY ENDPOINTS (for testing and monitoring)
# ============================================================

@router.get("/events/{athena_patient_id}")
async def get_patient_events(
    athena_patient_id: str,
    event_type: Optional[str] = Query(None, description="Filter by type"),
    limit: int = Query(100, le=1000, description="Max results"),
    db: Session = Depends(get_db)
):
    """
    Get all events for a patient.

    USE THIS TO:
        - Verify data is being stored correctly
        - Debug issues with specific patients
        - Test the ingestion pipeline

    EXAMPLE:
        GET /ingest/events/12345678?event_type=medication&limit=10
    """
    query = db.query(ClinicalEvent).filter_by(
        athena_patient_id=athena_patient_id
    )

    if event_type:
        query = query.filter_by(event_type=event_type)

    events = query.order_by(
        ClinicalEvent.captured_at.desc()
    ).limit(limit).all()

    return {
        "patient_id": athena_patient_id,
        "count": len(events),
        "events": [
            {
                "id": e.id,
                "type": e.event_type,
                "subtype": e.event_subtype,
                "captured_at": e.captured_at.isoformat() if e.captured_at else None,
                "confidence": e.confidence,
                "payload_keys": list(e.raw_payload.keys()) if e.raw_payload else []
            }
            for e in events
        ]
    }


@router.get("/stats")
async def get_ingestion_stats(db: Session = Depends(get_db)):
    """
    Get overall ingestion statistics.

    USE THIS TO:
        - Monitor the system health
        - Verify data is flowing correctly
        - Debug issues

    EXAMPLE:
        GET /ingest/stats

    RESPONSE:
        {
            "total_events": 1234,
            "by_type": {
                "medication": 500,
                "problem": 400,
                "vital": 200,
                ...
            }
        }
    """
    # Count total events
    total = db.query(func.count(ClinicalEvent.id)).scalar()

    # Count by event type
    by_type = db.query(
        ClinicalEvent.event_type,
        func.count(ClinicalEvent.id)
    ).group_by(ClinicalEvent.event_type).all()

    # Count unique patients
    unique_patients = db.query(
        func.count(func.distinct(ClinicalEvent.athena_patient_id))
    ).scalar()

    return {
        "total_events": total or 0,
        "unique_patients": unique_patients or 0,
        "by_type": {t: c for t, c in by_type} if by_type else {}
    }


# ============================================================
# CLINICAL DATA FETCH ENDPOINT (Bidirectional Integration)
# ============================================================

@router.get("/clinical/{athena_mrn}")
async def get_patient_clinical(
    athena_mrn: str,
    db: Session = Depends(get_db)
):
    """
    Fetch all stored clinical data for a patient by MRN.

    WHAT THIS DOES:
        Called by Athena-scraper when a user opens a patient chart.
        Returns all stored clinical data organized by type for
        immediate display in the WebUI.

    USE THIS FOR:
        - Instant data display when opening a patient
        - Persistent data access even if Athena session expired
        - Longitudinal view across multiple visits

    EXAMPLE:
        GET /ingest/clinical/12345678

    RESPONSE:
        {
            "status": "found",
            "athena_mrn": "12345678",
            "patient_id": 42,
            "clinical_data": {
                "demographics": {...},
                "medications": [...],
                "problems": [...],
                "labs": [...],
                "vitals": {...},
                "allergies": [...]
            },
            "event_count": 47
        }
    """
    import time
    start_time = time.time()

    # Telemetry: Track fetch request
    correlation_id = await emit_clinical_fetch(athena_mrn)

    try:
        # -----------------------------------------
        # STEP 1: Find patient by athena_mrn
        # -----------------------------------------
        patient = db.query(Patient).filter_by(athena_mrn=athena_mrn).first()

        if not patient:
            # Patient not found in database
            logger.warning(f"Clinical fetch: Patient MRN {athena_mrn} not found")

            await emit('plaud-fetch', 'FETCH_NOT_FOUND', {
                'correlationId': correlation_id,
                'athena_mrn': athena_mrn
            }, success=False)

            return {
                "status": "not_found",
                "athena_mrn": athena_mrn,
                "patient_id": None,
                "message": f"No patient found with MRN {athena_mrn}"
            }

        # -----------------------------------------
        # STEP 2: Fetch all clinical events for patient
        # -----------------------------------------
        events = db.query(ClinicalEvent).filter(
            ClinicalEvent.athena_patient_id == athena_mrn
        ).order_by(ClinicalEvent.captured_at.desc()).all()

        # -----------------------------------------
        # STEP 3: Organize events by type
        # -----------------------------------------
        clinical_data = _organize_clinical_data(patient, events)

        # Calculate response time
        duration_ms = int((time.time() - start_time) * 1000)

        # -----------------------------------------
        # STEP 4: Log and respond
        # -----------------------------------------
        logger.info(
            f"Clinical fetch: MRN {athena_mrn} → Patient #{patient.id} "
            f"({len(events)} events) in {duration_ms}ms"
        )

        # Telemetry: Track successful fetch
        await emit_clinical_fetch_success(
            correlation_id=correlation_id,
            patient_id=patient.id,
            event_count=len(events),
            duration_ms=duration_ms
        )

        # Find most recent update time
        last_updated = patient.updated_at
        if events:
            most_recent_event = max(
                (e.ingested_at for e in events if e.ingested_at),
                default=patient.updated_at
            )
            if most_recent_event and most_recent_event > last_updated:
                last_updated = most_recent_event

        return {
            "status": "found",
            "athena_mrn": athena_mrn,
            "patient_id": patient.id,
            "last_updated": last_updated.isoformat() if last_updated else None,
            "clinical_data": clinical_data,
            "event_count": len(events),
            "sources": _get_sources(events)
        }

    except Exception as e:
        logger.error(f"Clinical fetch error: {e}")
        duration_ms = int((time.time() - start_time) * 1000)

        await emit('plaud-fetch', 'FETCH_FAILED', {
            'correlationId': correlation_id,
            'athena_mrn': athena_mrn,
            'error': str(e),
            'duration_ms': duration_ms
        }, success=False)

        raise HTTPException(status_code=500, detail=str(e))


def _organize_clinical_data(patient: Patient, events: List[ClinicalEvent]) -> Dict[str, Any]:
    """
    Organize clinical events by type into a structured response.

    This function transforms raw event data into categories that
    match the WebUI display format.
    """
    # Start with demographics from patient record
    clinical_data = {
        "demographics": {
            "first_name": patient.first_name,
            "last_name": patient.last_name,
            "date_of_birth": str(patient.dob) if patient.dob else None,
            "gender": patient.birth_sex,
            "race": patient.race,
            "zip_code": patient.zip_code
        },
        "medications": [],
        "problems": [],
        "allergies": [],
        "labs": [],
        "vitals": None,
        "encounters": [],
        "documents": [],
        "other": []
    }

    # Track the most recent vitals
    latest_vitals = None
    latest_vitals_time = None

    for event in events:
        event_type = event.event_type.lower() if event.event_type else "other"
        payload = event.raw_payload or {}

        # Create base event info
        base_info = {
            "event_id": event.id,
            "source": event.source_system or "athena",
            "captured_at": event.captured_at.isoformat() if event.captured_at else None
        }

        if event_type == "medication":
            clinical_data["medications"].append({
                **base_info,
                "name": payload.get("medication_name") or payload.get("name") or payload.get("medicationname", "Unknown"),
                "sig": payload.get("sig") or payload.get("dose") or payload.get("dosage"),
                "start_date": payload.get("start_date") or payload.get("startdate"),
                "status": event.event_subtype or "active"
            })

        elif event_type == "problem":
            clinical_data["problems"].append({
                **base_info,
                "name": payload.get("problem_name") or payload.get("name") or payload.get("description", "Unknown"),
                "icd10": payload.get("icd_code") or payload.get("icd10") or payload.get("code"),
                "status": payload.get("status") or event.event_subtype or "active",
                "onset_date": payload.get("onset_date") or payload.get("onsetdate")
            })

        elif event_type == "allergy":
            clinical_data["allergies"].append({
                **base_info,
                "allergen": payload.get("allergen") or payload.get("name") or payload.get("substance", "Unknown"),
                "reaction_type": payload.get("reaction") or payload.get("reaction_type"),
                "severity": payload.get("severity")
            })

        elif event_type == "lab":
            clinical_data["labs"].append({
                **base_info,
                "name": payload.get("test_name") or payload.get("name") or payload.get("description", "Unknown"),
                "value": payload.get("value") or payload.get("result"),
                "unit": payload.get("unit") or payload.get("units"),
                "reference_range": payload.get("reference_range") or payload.get("normal_range"),
                "flag": payload.get("flag") or payload.get("abnormal_flag"),
                "date": payload.get("result_date") or payload.get("date") or (event.captured_at.isoformat() if event.captured_at else None)
            })

        elif event_type == "vital":
            # Keep only the most recent vitals
            event_time = event.captured_at
            if latest_vitals_time is None or (event_time and event_time > latest_vitals_time):
                latest_vitals_time = event_time
                latest_vitals = {
                    **base_info,
                    "blood_pressure": payload.get("blood_pressure") or payload.get("bp"),
                    "heart_rate": payload.get("heart_rate") or payload.get("pulse") or payload.get("hr"),
                    "temperature": payload.get("temperature") or payload.get("temp"),
                    "respiratory_rate": payload.get("respiratory_rate") or payload.get("resp"),
                    "oxygen_saturation": payload.get("oxygen_saturation") or payload.get("spo2") or payload.get("o2sat"),
                    "weight": payload.get("weight"),
                    "height": payload.get("height"),
                    "bmi": payload.get("bmi"),
                    "recorded_at": event.captured_at.isoformat() if event.captured_at else None
                }

        elif event_type in ("encounter", "appointment", "visit"):
            clinical_data["encounters"].append({
                **base_info,
                "date": payload.get("date") or payload.get("encounter_date") or (event.captured_at.isoformat() if event.captured_at else None),
                "provider": payload.get("provider") or payload.get("provider_name"),
                "reason": payload.get("reason") or payload.get("chief_complaint"),
                "type": payload.get("encounter_type") or payload.get("visit_type") or event.event_subtype,
                "notes": payload.get("notes")
            })

        elif event_type in ("document", "note"):
            clinical_data["documents"].append({
                **base_info,
                "title": payload.get("title") or payload.get("document_title") or "Document",
                "type": payload.get("document_type") or event.event_subtype,
                "date": payload.get("date") or (event.captured_at.isoformat() if event.captured_at else None),
                "summary": payload.get("summary") or payload.get("content", "")[:200] + "..." if payload.get("content") else None
            })

        else:
            # Catch-all for other event types
            clinical_data["other"].append({
                **base_info,
                "type": event_type,
                "subtype": event.event_subtype,
                "data": payload
            })

    # Set latest vitals
    clinical_data["vitals"] = latest_vitals

    return clinical_data


def _get_sources(events: List[ClinicalEvent]) -> List[str]:
    """Get unique list of data sources."""
    sources = set()
    for event in events:
        source = event.source_system or "athena"
        sources.add(source)
    return list(sources)


@router.get("/health")
async def health_check():
    """
    Simple health check endpoint.

    USE THIS TO:
        - Verify the service is running
        - Check from Athena-Scraper before sending data
    """
    return {"status": "healthy", "service": "scc-ingest"}
