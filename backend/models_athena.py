"""
=============================================================================
ATHENA EMR INTEGRATION MODELS
=============================================================================

ARCHITECTURAL ROLE:
    These models form the ATHENA INTEGRATION LAYER - a separate data domain
    that captures raw EMR data from the Athena-Scraper Chrome extension.
    They are designed to be ADDITIVE (not modifying core models) and
    APPEND-ONLY (events are never updated or deleted).

DATA FLOW POSITION:
    ┌────────────────────────────────────────────────────────────────────┐
    │                     ATHENA EMR (Cloud)                             │
    │                          ▼                                         │
    │            Athena-Scraper Chrome Extension                         │
    │            (Intercepts API responses)                              │
    └────────────────────────────┬───────────────────────────────────────┘
                                 │ POST /ingest/athena
                                 ▼
    ┌────────────────────────────────────────────────────────────────────┐
    │                 models_athena.py (THIS FILE)                       │
    │                                                                    │
    │  ┌────────────────────────────────────────────────────────────┐   │
    │  │                   ClinicalEvent                             │   │
    │  │  (Raw EMR data - medications, problems, vitals, labs)      │   │
    │  │  APPEND-ONLY: Never modified after creation                │   │
    │  └────────────────────────────┬───────────────────────────────┘   │
    │                               │                                    │
    │           ┌───────────────────┼───────────────────┐                │
    │           ▼                   ▼                   ▼                │
    │  ┌──────────────┐  ┌──────────────────┐  ┌───────────────────┐    │
    │  │ Structured   │  │ Finding          │  │ AthenaDocument    │    │
    │  │ Finding      │  │ Evidence         │  │ (PDFs, Images)    │    │
    │  │ (Extracted)  │  │ (Provenance)     │  │                   │    │
    │  └──────────────┘  └──────────────────┘  └───────────────────┘    │
    │                                                                    │
    │  ┌────────────────────────────────────────────────────────────┐   │
    │  │              IntegrationAuditLog                            │   │
    │  │  (HIPAA compliance - tracks all access/modifications)      │   │
    │  └────────────────────────────────────────────────────────────┘   │
    └────────────────────────────────────────────────────────────────────┘

ENTITY RELATIONSHIP DIAGRAM:

    ┌─────────────────────────────────────────────────────────────────┐
    │                     ClinicalEvent                               │
    │─────────────────────────────────────────────────────────────────│
    │ id: UUID (PK)           │ Unique event identifier               │
    │ patient_id: INT (FK)    │ Links to patients.id (optional)       │
    │ athena_patient_id: STR  │ MRN from Athena (always populated)    │
    │ event_type: STR         │ medication, problem, vital, lab, etc. │
    │ raw_payload: JSONB      │ Complete unmodified Athena response   │
    │ idempotency_key: STR    │ SHA256 hash for deduplication         │
    │ captured_at: TIMESTAMP  │ When event occurred in Athena         │
    │ ingested_at: TIMESTAMP  │ When we stored it                     │
    └───────────────┬─────────────────────────────────────────────────┘
                    │ 1:N
                    ▼
    ┌─────────────────────────────────────────────────────────────────┐
    │                   StructuredFinding                             │
    │─────────────────────────────────────────────────────────────────│
    │ id: INT (PK)            │ Auto-increment                        │
    │ source_event_id: UUID   │ FK to ClinicalEvent                   │
    │ finding_type: STR       │ ABI, TBI, Stenosis, etc.              │
    │ value: STR              │ The extracted value                   │
    │ side: STR               │ Left, Right, Bilateral (CRITICAL!)    │
    │ location: STR           │ SFA, Popliteal, Carotid, etc.         │
    └───────────────┬─────────────────────────────────────────────────┘
                    │ 1:N
                    ▼
    ┌─────────────────────────────────────────────────────────────────┐
    │                   FindingEvidence                               │
    │─────────────────────────────────────────────────────────────────│
    │ id: INT (PK)            │ Auto-increment                        │
    │ finding_id: INT         │ FK to StructuredFinding               │
    │ text_excerpt: TEXT      │ Exact matched text                    │
    │ context_before: TEXT    │ ~50 chars before match                │
    │ context_after: TEXT     │ ~50 chars after match                 │
    └─────────────────────────────────────────────────────────────────┘

CRITICAL DESIGN PRINCIPLES:

    1. APPEND-ONLY EVENT STORAGE:
       ClinicalEvent records are NEVER updated or deleted.
       - Same data sent twice = duplicate detection via idempotency_key
       - Data corrections = new event with corrected data
       - Preserves complete audit trail for HIPAA compliance

    2. IDEMPOTENCY VIA SHA256 HASHING:
       idempotency_key = SHA256(patient_id + event_type + payload)
       - Ensures exact same data is never stored twice
       - Allows safe retries from Athena-Scraper
       - Unique constraint prevents insertion of duplicates

    3. OPTIONAL PATIENT LINKAGE:
       patient_id is nullable because:
       - Events can arrive before patient record exists
       - Auto-linking happens via athena_mrn matching
       - Preserves events even for unrecognized patients

    4. LATERALITY TRACKING (side field):
       Vascular surgery REQUIRES left/right distinction.
       - ABI of 0.5 on left leg vs right leg = different findings
       - Missing laterality = clinical safety risk
       - Parsed from text via regex patterns

    5. EVIDENCE PROVENANCE:
       FindingEvidence provides clinical validation:
       - Shows EXACTLY what text produced the finding
       - Doctors can verify AI extraction is correct
       - Required for medico-legal defensibility

DEDUPLICATION ALGORITHM:
    ┌──────────────────────────────────────────────────────────────────┐
    │ 1. Receive payload from Athena-Scraper                          │
    │ 2. Sort payload keys (ensures consistent hashing)               │
    │ 3. Generate key: SHA256(patient_id:event_type:json_payload)     │
    │ 4. Query: SELECT id FROM clinical_events WHERE idem_key = ?     │
    │ 5. If exists → return "duplicate" status, skip insert           │
    │ 6. If new → insert event, return "success" status               │
    └──────────────────────────────────────────────────────────────────┘

SECURITY MODEL:
    - IntegrationAuditLog tracks ALL actions (INGEST, PARSE, VIEW, ERROR)
    - Supports HIPAA audit trail requirements
    - Actor field identifies which component performed action
    - IP address logged for access tracking

HIPAA COMPLIANCE:
    - All access logged with timestamp and actor
    - Raw data preserved unmodified (source of truth)
    - No PHI in column names or indexes
    - Error messages sanitized before logging

MAINTENANCE NOTES:
    - UUID primary keys prevent enumeration attacks
    - Composite index on (athena_patient_id, captured_at) for timeline queries
    - JSONB (not JSON) for efficient PostgreSQL querying
    - Relationship back_populates ensures bidirectional navigation

INTEGRATION WITH CORE MODELS:
    - ClinicalEvent.patient_id → Patient.id (Integer, not UUID)
    - Auto-linking via athena_mrn matching in ingest.py
    - Core models (Patient, VoiceTranscript) remain unchanged

VERSION: 2.0.0
LAST UPDATED: 2025-12
=============================================================================
"""

import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, JSON
from sqlalchemy import ForeignKey, Text, Float, Index
from sqlalchemy.orm import relationship

# Import your existing Base from db.py
# This connects these models to the same database
from .db import Base


def generate_uuid():
    """Generate a new UUID string for primary keys."""
    return str(uuid.uuid4())


class ClinicalEvent(Base):
    """
    Stores raw clinical data captured from Athena.

    This is an APPEND-ONLY table - we never update or delete events.
    If data changes, we add a new event (preserving history).

    Think of this as a PostgreSQL version of raw_events.jsonl,
    but with indexes for fast searching.
    """
    __tablename__ = "clinical_events"

    # -------------------------
    # Primary Key
    # -------------------------
    id = Column(
        String(36),
        primary_key=True,
        default=generate_uuid,
        comment="Unique event ID (UUID format)"
    )

    # -------------------------
    # Patient Identification
    # -------------------------
    # Link to existing patients table (NULL if not yet linked)
    # NOTE: patients.id is Integer in the existing schema
    patient_id = Column(
        Integer,
        ForeignKey("patients.id"),
        nullable=True,
        index=True,
        comment="FK to patients table (optional)"
    )

    # Athena's patient ID (the MRN)
    # This is always populated - it's how we identify patients
    athena_patient_id = Column(
        String(50),
        index=True,
        comment="Patient MRN from Athena"
    )

    # -------------------------
    # Event Classification
    # -------------------------
    # What type of clinical data is this?
    event_type = Column(
        String(50),
        index=True,
        comment="medication, problem, vital, lab, allergy, encounter, etc."
    )

    # More specific sub-classification
    event_subtype = Column(
        String(50),
        nullable=True,
        comment="active, historical, search, etc."
    )

    # -------------------------
    # The Actual Data
    # -------------------------
    # This stores the EXACT JSON received from Athena
    # We never modify this - it's the source of truth
    raw_payload = Column(
        JSON,
        nullable=False,
        comment="Complete raw data from Athena (never modified)"
    )

    # -------------------------
    # Source Tracking
    # -------------------------
    source_system = Column(
        String(50),
        default="athena",
        comment="Always 'athena' for now, future: 'plaud', 'manual'"
    )

    source_endpoint = Column(
        Text,
        nullable=True,
        comment="The Athena API endpoint that was intercepted"
    )

    # -------------------------
    # Deduplication
    # -------------------------
    # CRITICAL: This prevents duplicate entries
    # We hash the patient_id + event_type + payload
    # If two events have the same hash, they're duplicates
    idempotency_key = Column(
        String(128),
        unique=True,
        index=True,
        comment="SHA256 hash for deduplication"
    )

    # -------------------------
    # Timestamps
    # -------------------------
    # When did Athena send this?
    captured_at = Column(
        DateTime,
        index=True,
        comment="When the event occurred in Athena"
    )

    # When did we save it?
    ingested_at = Column(
        DateTime,
        default=datetime.utcnow,
        comment="When we stored it in PostgreSQL"
    )

    # -------------------------
    # Metadata
    # -------------------------
    confidence = Column(
        Float,
        default=0.0,
        comment="Classification confidence (0.0-1.0)"
    )

    indexer_version = Column(
        String(20),
        default="2.0.0",
        comment="Version of event_indexer that classified this"
    )

    # -------------------------
    # Relationships
    # -------------------------
    # Connect to findings extracted from this event
    findings = relationship(
        "StructuredFinding",
        back_populates="source_event"
    )

    # -------------------------
    # Table Configuration
    # -------------------------
    __table_args__ = (
        # Composite index for efficient timeline queries
        Index(
            'ix_clinical_events_patient_time',
            'athena_patient_id',
            'captured_at'
        ),
    )

    def __repr__(self):
        return f"<ClinicalEvent {self.event_type} for {self.athena_patient_id}>"


class StructuredFinding(Base):
    """
    Extracted clinical values from raw events.

    Example:
        Raw event contains: "ABI is 0.9 on the left leg"
        Finding extracts:
            finding_type = "ABI"
            value = "0.9"
            side = "Left"

    This allows fast queries like:
        "Find all patients with ABI < 0.5"
    """
    __tablename__ = "structured_findings"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Patient links (patients.id is Integer)
    patient_id = Column(
        Integer,
        ForeignKey("patients.id"),
        nullable=True
    )
    athena_patient_id = Column(String(50), index=True)

    # What was found?
    finding_type = Column(
        String(50),
        index=True,
        comment="ABI, TBI, Stenosis, AneurysmSize, Rutherford, etc."
    )

    value = Column(
        String(100),
        comment="The extracted value (as string for flexibility)"
    )

    unit = Column(
        String(20),
        nullable=True,
        comment="mm, %, ratio, cm, etc."
    )

    # Laterality - CRITICAL for vascular surgery!
    side = Column(
        String(20),
        nullable=True,
        comment="Left, Right, Bilateral"
    )

    location = Column(
        String(100),
        nullable=True,
        comment="SFA, Popliteal, Carotid, Aorta, etc."
    )

    # Traceability - which event did this come from?
    source_event_id = Column(
        String(36),
        ForeignKey("clinical_events.id")
    )
    source_event = relationship(
        "ClinicalEvent",
        back_populates="findings"
    )

    # Confidence and versioning
    confidence = Column(Float, default=0.0)
    parser_version = Column(String(20), default="1.0.0")

    created_at = Column(DateTime, default=datetime.utcnow)

    # Connect to evidence
    evidences = relationship("FindingEvidence", back_populates="finding")

    def __repr__(self):
        return f"<Finding {self.finding_type}={self.value} ({self.side})>"


class FindingEvidence(Base):
    """
    Text snippets that support a finding.

    This provides PROVENANCE - doctors can verify the AI's work
    by seeing exactly what text was matched.

    Example:
        Finding: ABI = 0.9, side = Left
        Evidence:
            text_excerpt = "ABI is 0.9"
            context_before = "Left leg examination: "
            context_after = " indicating mild disease"
    """
    __tablename__ = "finding_evidences"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Link to the finding this supports
    finding_id = Column(
        Integer,
        ForeignKey("structured_findings.id")
    )
    finding = relationship(
        "StructuredFinding",
        back_populates="evidences"
    )

    # The matched text
    text_excerpt = Column(Text, comment="The exact text that was matched")

    # Surrounding context (helps verify correctness)
    context_before = Column(Text, nullable=True, comment="~50 chars before")
    context_after = Column(Text, nullable=True, comment="~50 chars after")

    # Which field contained this text?
    source_field = Column(
        String(100),
        nullable=True,
        comment="e.g., 'note_text', 'result_value'"
    )

    def __repr__(self):
        return f"<Evidence: '{self.text_excerpt[:30]}...'>"


class AthenaDocument(Base):
    """
    Actual document files (PDFs, images) from Athena.

    This is separate from findings/evidence - those are extracted DATA,
    this is the actual FILES.
    """
    __tablename__ = "athena_documents"

    id = Column(String(36), primary_key=True, default=generate_uuid)

    # patients.id is Integer in the existing schema
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=True)
    athena_patient_id = Column(String(50), index=True)

    # Document metadata
    title = Column(String(255))
    document_type = Column(
        String(50),
        comment="cta, mri, ultrasound, surgical, pathology, etc."
    )
    file_name = Column(String(255), nullable=True)
    mime_type = Column(String(100), nullable=True)

    # Storage location
    storage_path = Column(Text, nullable=True, comment="Local file path")
    athena_url = Column(Text, nullable=True, comment="Original Athena URL")

    # Link to capture event
    source_event_id = Column(
        String(36),
        ForeignKey("clinical_events.id"),
        nullable=True
    )

    document_date = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<Document: {self.title}>"


class IntegrationAuditLog(Base):
    """
    Audit trail for HIPAA compliance.

    Logs ALL actions:
    - INGEST: Data was received and stored
    - PARSE: Findings were extracted
    - VIEW: Someone looked at patient data
    - EXPORT: Data was exported/downloaded
    - ERROR: Something went wrong
    """
    __tablename__ = "integration_audit_log"

    id = Column(Integer, primary_key=True, autoincrement=True)

    action = Column(
        String(50),
        comment="INGEST, PARSE, VIEW, EXPORT, ERROR"
    )

    resource_type = Column(
        String(50),
        comment="clinical_event, finding, document"
    )

    resource_id = Column(String(100), nullable=True)

    # Additional context
    details = Column(JSON, nullable=True)
    error_message = Column(Text, nullable=True)

    # Who/what did this?
    actor = Column(String(100), default="athena_adapter")
    ip_address = Column(String(45), nullable=True)

    timestamp = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<AuditLog {self.action} on {self.resource_type}>"
