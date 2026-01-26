# Albany Vascular Specialist Center

## PlaudAI - Unified Vascular Surgery Platform

**Advanced Clinical Documentation & Surgical Command System**

PlaudAI is the unified backend for Albany Vascular's surgical platform, combining:
- **Voice-to-Documentation**: Turn voice recordings into structured surgical notes
- **Shadow Coder**: AI-powered charge coding assistance (PAD compliance)
- **ORCC Integration**: Real-time surgical readiness tracking
- **Task Management**: Workflow coordination for surgical teams
- **EMR Integration**: Bidirectional sync with Athena

---

## Quick Start (For Beginners)

### What is PlaudAI?
A web platform that helps vascular surgeons:
1. **Document**: Turn voice dictations into organized notes
2. **Code**: Ensure proper charge coding with AI assistance
3. **Track**: Manage surgical readiness and patient workflows
4. **Coordinate**: Real-time updates across the surgical team

### Starting the Server

```bash
# SSH to Server1
ssh server1@100.75.237.36

# Start PlaudAI
cd ~/plaudai_uploader
conda activate plaudai
uvicorn backend.main:app --host 0.0.0.0 --port 8001
```

### Accessing the System

| Interface | URL | Purpose |
|-----------|-----|---------|
| **PlaudAI Web** | http://100.75.237.36:8001/index.html | Voice upload & documentation |
| **API Docs** | http://100.75.237.36:8001/docs | Interactive API explorer |
| **Health Check** | http://100.75.237.36:8001/health | Service status |

### Quick API Test

```bash
# Check server health
curl http://100.75.237.36:8001/health

# List patients
curl http://100.75.237.36:8001/api/patients

# Create a task
curl -X POST http://100.75.237.36:8001/api/tasks \
  -H "Content-Type: application/json" \
  -d '{"title": "Pre-op workup", "patient_mrn": "12345", "priority": "high"}'
```

---

## Architecture Overview

### System Components (2026)

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      ALBANY VASCULAR PLATFORM                            │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│   FRONTENDS                           BACKEND (PlaudAI @ 8001)           │
│   ─────────                           ────────────────────────           │
│                                                                          │
│   ┌─────────────┐                    ┌────────────────────────┐         │
│   │ PlaudAI Web │───────────────────▶│ /api/patients          │         │
│   │ (Voice UI)  │                    │ /api/procedures        │         │
│   └─────────────┘                    │ /api/parse             │         │
│                                       │ /api/synopsis          │         │
│   ┌─────────────┐                    ├────────────────────────┤         │
│   │ ORCC        │───────────────────▶│ /api/tasks             │ NEW     │
│   │ (Surgical)  │                    │ /api/shadow-coder/*    │ NEW     │
│   └─────────────┘                    │ /ws (WebSocket)        │ NEW     │
│                                       ├────────────────────────┤         │
│   ┌─────────────┐                    │ /ingest/athena         │         │
│   │ Athena      │───────────────────▶│ /ingest/clinical/{mrn} │         │
│   │ Scraper     │                    └──────────┬─────────────┘         │
│   └─────────────┘                               │                        │
│                                                  ▼                        │
│                                       ┌────────────────────────┐         │
│                                       │  PostgreSQL (5432)     │         │
│                                       │  surgical_command_     │         │
│                                       │  center                │         │
│                                       └────────────────────────┘         │
└─────────────────────────────────────────────────────────────────────────┘
```

### Single-Server Architecture (Port 8001)

This application uses a **single-server monolithic architecture**:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         BROWSER                                          │
│  User visits: http://100.75.237.36:8001/index.html                      │
└─────────────────────────────┬───────────────────────────────────────────┘
                              │
                              │ (1) HTTP GET /index.html
                              ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    FastAPI Server (Port 8001)                            │
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────────────┐│
│  │ SERVES BOTH:                                                         ││
│  │                                                                      ││
│  │  1. STATIC FILES (Frontend)          2. REST API (Backend)          ││
│  │     /index.html ← WebUI                 /upload ← Transcripts       ││
│  │     /static/* ← CSS/JS                  /patients ← Patient data    ││
│  │                                          /ingest/athena ← EMR data   ││
│  │                                          /clinical/query ← AI chat   ││
│  └─────────────────────────────────────────────────────────────────────┘│
└─────────────────────────────┬───────────────────────────────────────────┘
                              │
                              │ (2) Frontend JavaScript calls API
                              │     API_BASE = 'http://100.75.237.36:8001'
                              │     (defined in frontend/index.html:861)
                              ▼
                    ┌─────────────────┐
                    │   PostgreSQL    │
                    │   Port 5432     │
                    └─────────────────┘
```

**Why this design?**

| Aspect | Explanation |
|--------|-------------|
| **Single Port (8001)** | FastAPI serves both frontend HTML and backend API on the same port. No need for separate servers. |
| **No CORS Issues** | Since frontend and API are on the same origin (same host:port), browsers don't block requests. |
| **Simple Deployment** | One process to manage. No nginx reverse proxy needed for development. |
| **API_BASE Hardcoded** | The frontend's `API_BASE` in `frontend/index.html:861` points to `http://100.75.237.36:8001` - this is the server's Tailscale IP. |

**Key Configuration Points:**
- **Backend port**: `8001` (set in uvicorn startup command)
- **Frontend API target**: `http://100.75.237.36:8001` (hardcoded in `frontend/index.html:861`)
- **If port changes**: Must update BOTH the startup command AND `API_BASE` in index.html

---

# Technical Documentation

## Table of Contents

1. [System Architecture](#system-architecture)
2. [Data Flow Model](#data-flow-model)
3. [Component Reference](#component-reference)
4. [Security Model](#security-model)
5. [Database Schema](#database-schema)
6. [API Reference](#api-reference)
7. [Integration Patterns](#integration-patterns)
8. [Maintenance Guide](#maintenance-guide)

---

## System Architecture

### High-Level Architecture Diagram

```
                                    ALBANY VASCULAR AI CLINICAL SYSTEM
    ┌──────────────────────────────────────────────────────────────────────────────────────┐
    │                                                                                      │
    │  ┌─────────────────┐     ┌─────────────────┐     ┌─────────────────────────────────┐│
    │  │                 │     │                 │     │                                 ││
    │  │  ATHENA EMR     │────▶│  ATHENA-SCRAPER │────▶│  PLAUDAI INGESTION SERVICE     ││
    │  │  (External)     │     │  (Chrome Ext)   │     │  POST /ingest/athena           ││
    │  │                 │     │                 │     │                                 ││
    │  └─────────────────┘     └─────────────────┘     └───────────────┬─────────────────┘│
    │                                                                   │                  │
    │  ┌─────────────────┐                                             │                  │
    │  │                 │                                             ▼                  │
    │  │  PLAUDAI VOICE  │     ┌─────────────────┐     ┌─────────────────────────────────┐│
    │  │  RECORDER       │────▶│  TRANSCRIPT     │────▶│  CLINICAL EVENT PROCESSOR      ││
    │  │  (External)     │     │  UPLOAD API     │     │  - Auto-link by MRN            ││
    │  │                 │     │  POST /upload   │     │  - Idempotency deduplication   ││
    │  └─────────────────┘     └─────────────────┘     │  - HIPAA audit logging         ││
    │                                                   └───────────────┬─────────────────┘│
    │                                                                   │                  │
    │  ┌─────────────────┐     ┌─────────────────┐                     │                  │
    │  │                 │     │                 │                     ▼                  │
    │  │  WEB FRONTEND   │◀───▶│  FASTAPI        │     ┌─────────────────────────────────┐│
    │  │  (HTML/JS)      │     │  REST API       │◀───▶│  POSTGRESQL DATABASE           ││
    │  │                 │     │                 │     │  surgical_command_center       ││
    │  └─────────────────┘     └─────────────────┘     │                                 ││
    │                                                   │  Tables:                        ││
    │  ┌─────────────────┐     ┌─────────────────┐     │  - patients                     ││
    │  │                 │     │                 │     │  - voice_transcripts            ││
    │  │  GEMINI AI      │◀───▶│  CLINICAL QUERY │     │  - clinical_synopses            ││
    │  │  (Google)       │     │  SERVICE        │     │  - pvi_procedures               ││
    │  │                 │     │                 │     │  - clinical_events              ││
    │  └─────────────────┘     └─────────────────┘     │  - structured_findings          ││
    │                                                   │  - integration_audit_log        ││
    │                                                   └─────────────────────────────────┘│
    └──────────────────────────────────────────────────────────────────────────────────────┘
```

### Architectural Principles

| Principle | Implementation | Rationale |
|-----------|----------------|-----------|
| **Separation of Concerns** | Routes, Services, Models layers | Maintainability, testability |
| **Idempotency** | SHA256 hash-based deduplication | Prevents duplicate clinical data |
| **Append-Only Events** | Clinical events never modified | Audit trail, HIPAA compliance |
| **Auto-Linking** | MRN-based patient matching | Data integrity across systems |
| **Graceful Degradation** | JSONL fallback in Athena-Scraper | Resilience to network failures |

### Design Decisions

1. **FastAPI over Flask**: Async support, automatic OpenAPI docs, Pydantic validation
2. **SQLAlchemy ORM**: Type safety, relationship management, migration support
3. **PostgreSQL**: JSONB for flexible payloads, robust indexing, ACID compliance
4. **Stateless API**: Horizontal scaling capability, no session management
5. **File-based Logging**: Persistent audit trail, grep-able diagnostics

---

## Data Flow Model

### Primary Data Flows

#### Flow 1: Athena EMR → PlaudAI (Real-time Clinical Data)

```
┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│ Athena EMR   │───▶│ Chrome Ext   │───▶│ POST         │───▶│ clinical_    │
│ API Response │    │ Intercepts   │    │ /ingest/     │    │ events       │
│              │    │ XHR Data     │    │ athena       │    │ table        │
└──────────────┘    └──────────────┘    └──────────────┘    └──────────────┘
                                               │
                                               ▼
                                        ┌──────────────┐
                                        │ Auto-Link    │
                                        │ by MRN to    │
                                        │ patients.id  │
                                        └──────────────┘
```

**Data Transformation:**
```python
# Input (from Athena-Scraper)
{
    "athena_patient_id": "18889107",      # MRN
    "event_type": "medication",
    "payload": {"name": "Aspirin", ...},
    "captured_at": "2025-12-28T10:00:00Z"
}

# Processing
1. Generate idempotency_key = SHA256(patient_id + event_type + payload)
2. Check for duplicate (skip if exists)
3. Query patients WHERE athena_mrn = athena_patient_id
4. Set patient_id foreign key if match found
5. Insert into clinical_events
6. Log to integration_audit_log
```

#### Flow 2: Voice Transcript → Structured Data

```
┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│ PlaudAI      │───▶│ POST         │───▶│ Parser       │───▶│ voice_       │
│ Transcript   │    │ /upload      │    │ Service      │    │ transcripts  │
│ (Markdown)   │    │              │    │              │    │ table        │
└──────────────┘    └──────────────┘    └──────────────┘    └──────────────┘
                                               │
                                               ▼
                                        ┌──────────────┐
                                        │ Gemini AI    │───▶ clinical_synopses
                                        │ Synopsis     │───▶ pvi_procedures
                                        └──────────────┘
```

### Event Processing Pipeline

```python
# Idempotency Key Generation
def generate_idempotency_key(patient_id: str, event_type: str, payload: dict) -> str:
    """
    Creates deterministic hash for deduplication.

    Algorithm:
        1. Sort payload keys for consistent ordering
        2. Concatenate: "{patient_id}:{event_type}:{json_payload}"
        3. Apply SHA256, take first 64 characters

    Properties:
        - Same input always produces same output
        - Different payloads produce different keys
        - Collision probability: ~10^-77
    """
    payload_str = json.dumps(payload, sort_keys=True)
    raw = f"{patient_id}:{event_type}:{payload_str}"
    return hashlib.sha256(raw.encode()).hexdigest()[:64]
```

---

## Component Reference

### Directory Structure

```
plaudai_uploader/
├── backend/
│   ├── main.py              # FastAPI application entry point
│   ├── config.py            # Environment configuration loader
│   ├── db.py                # Database connection and session management
│   ├── models.py            # Core SQLAlchemy ORM models
│   ├── models_athena.py     # Athena integration models
│   ├── schemas.py           # Pydantic request/response schemas
│   ├── logging_config.py    # Structured logging configuration
│   ├── routes/
│   │   ├── __init__.py
│   │   └── ingest.py        # Athena ingestion endpoints
│   └── services/
│       ├── uploader.py      # Transcript processing logic
│       ├── parser.py        # Text parsing and tagging
│       ├── gemini_parser.py # AI-powered extraction
│       ├── gemini_synopsis.py # Clinical synopsis generation
│       ├── clinical_query.py  # Natural language queries
│       ├── category_parser.py # Record categorization
│       └── pdf_generator.py   # PDF report generation
├── frontend/
│   └── index.html           # Web user interface
├── migrations/
│   └── add_athena_tables.sql # Database migration scripts
├── logs/
│   └── plaudai_uploader.log # Application logs
├── .env                     # Environment configuration (not in git)
├── .env.example             # Environment template
├── .gitignore               # Git exclusions
├── requirements.txt         # Python dependencies
└── readme.md                # This documentation
```

### Component Details

---

### `backend/main.py`

**Architectural Role:** Application entry point and HTTP request orchestrator

**Position in Data Flow:** Entry point for all HTTP requests

**Critical Design Principles:**
- Lifespan management for database connections
- Middleware chain for CORS, logging, error handling
- Route registration with prefix organization

**Key Functions:**

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifecycle manager.

    Startup:
        - Initialize database connection pool
        - Create tables if not exist
        - Verify connectivity

    Shutdown:
        - Close database connections gracefully
        - Flush pending logs

    Raises:
        SystemExit: If database connection fails
    """

@app.middleware("http")
async def log_requests(request: Request, call_next):
    """
    Request/response logging middleware.

    Parameters:
        request: Incoming HTTP request
        call_next: Next middleware in chain

    Returns:
        Response with timing headers

    Logs:
        - Request ID (UUID)
        - Method and path
        - Response status
        - Processing time (ms)
    """
```

**Security Considerations:**
- CORS configured for development (allows all origins)
- No authentication middleware (TODO for production)
- Request IDs for audit trail correlation

**Maintenance Notes:**
- Add authentication middleware before production
- Consider rate limiting for /ingest endpoints
- Monitor response times in logs

---

### `backend/db.py`

**Architectural Role:** Database abstraction layer

**Position in Data Flow:** Provides session management for all database operations

**Critical Design Principles:**
- Connection pooling for performance
- Session-per-request pattern
- Automatic cleanup with context managers

**Key Functions:**

```python
def get_db() -> Generator[Session, None, None]:
    """
    Dependency injection for database sessions.

    Yields:
        Session: SQLAlchemy session bound to request lifecycle

    Usage:
        @app.get("/patients")
        def get_patients(db: Session = Depends(get_db)):
            return db.query(Patient).all()

    Guarantees:
        - Session closed after request completes
        - Rollback on unhandled exceptions
        - Connection returned to pool
    """

def init_db() -> None:
    """
    Initialize database schema.

    Operations:
        1. Test connection with SELECT 1
        2. Create all tables via SQLAlchemy metadata
        3. Log success or failure

    Raises:
        Exception: Logged and re-raised if connection fails

    Idempotency:
        Safe to call multiple times (uses CREATE IF NOT EXISTS)
    """
```

**Configuration:**
```python
DATABASE_URL = f"postgresql://{user}:{password}@{host}:{port}/{database}"

engine = create_engine(
    DATABASE_URL,
    pool_size=5,           # Concurrent connections
    max_overflow=10,       # Burst capacity
    pool_pre_ping=True,    # Verify connections before use
    echo=False             # SQL logging (True for debug)
)
```

---

### `backend/models.py`

**Architectural Role:** Core domain models for patient data

**Position in Data Flow:** ORM layer between services and PostgreSQL

**Critical Design Principles:**
- Single source of truth for schema
- Relationship definitions for joined queries
- Audit timestamps on all entities

**Models:**

```python
class Patient(Base):
    """
    Patient demographic and identification record.

    Attributes:
        id (int): Primary key, auto-increment
        first_name (str): Patient first name
        last_name (str): Patient surname
        dob (date): Date of birth (required for uniqueness)
        athena_mrn (str): Athena Medical Record Number (unique, indexed)
        birth_sex (str): M/F/Other
        race (str): Demographic classification
        zip_code (str): For geographic analysis
        created_at (datetime): Record creation timestamp
        updated_at (datetime): Last modification timestamp

    Relationships:
        transcripts: List[VoiceTranscript] - One-to-many
        procedures: List[PVIProcedure] - One-to-many
        synopses: List[ClinicalSynopsis] - One-to-many

    Indexes:
        - athena_mrn (unique): Fast lookup for Athena integration

    Constraints:
        - athena_mrn NOT NULL: Every patient must have MRN
        - dob NOT NULL: Required for patient identification
    """

class VoiceTranscript(Base):
    """
    Voice recording transcript with parsed clinical data.

    Attributes:
        id (int): Primary key
        patient_id (int): Foreign key to patients
        raw_transcript (text): Original voice-to-text output
        plaud_note (text): Formatted PlaudAI note
        tags (json): Extracted medical tags
        confidence_score (float): Parsing confidence 0.0-1.0
        record_category (str): operative_note, imaging, etc.
        category_specific_data (json): Category-dependent fields

    Design Notes:
        - raw_transcript preserved for audit/reprocessing
        - tags stored as JSON array for flexible querying
        - category_specific_data allows schema evolution
    """

class PVIProcedure(Base):
    """
    Peripheral Vascular Intervention registry data.

    Follows SVS VQI (Vascular Quality Initiative) standards.

    Key Field Groups:
        - Demographics: smoking, comorbidities
        - History: rutherford_status, prior_interventions
        - Procedure: access_site, arteries_treated, devices
        - Outcomes: complications, mortality
        - Follow-up: 30-day, long-term (9-21 months)

    Clinical Importance:
        - rutherford_status: Claudication severity (0-6)
        - preop_abi: Ankle-brachial index (<0.9 = PAD)
        - tasc_grade: Lesion complexity (A-D)
    """
```

---

### `backend/models_athena.py`

**Architectural Role:** Athena EMR integration data models

**Position in Data Flow:** Storage layer for ingested Athena data

**Critical Design Principles:**
- Append-only event storage
- Idempotency via unique hash keys
- Optional patient linking (may ingest before patient exists)

**Models:**

```python
class ClinicalEvent(Base):
    """
    Raw clinical data captured from Athena EMR.

    Attributes:
        id (str): UUID primary key
        patient_id (int): FK to patients (nullable)
        athena_patient_id (str): MRN from Athena
        event_type (str): medication, problem, vital, lab, etc.
        event_subtype (str): active, historical, etc.
        raw_payload (json): Complete data from Athena
        idempotency_key (str): SHA256 hash for deduplication
        captured_at (datetime): When Athena sent data
        ingested_at (datetime): When we stored it
        confidence (float): Classification confidence

    Indexes:
        - athena_patient_id: Patient timeline queries
        - event_type: Filter by category
        - captured_at: Chronological ordering
        - idempotency_key (unique): Duplicate prevention

    Design Rationale:
        - raw_payload never modified (source of truth)
        - patient_id nullable for orphan events
        - Composite index on (athena_patient_id, captured_at)
    """

class IntegrationAuditLog(Base):
    """
    HIPAA-compliant audit trail for all operations.

    Attributes:
        action (str): INGEST, PARSE, VIEW, EXPORT, ERROR
        resource_type (str): clinical_event, patient, etc.
        resource_id (str): ID of affected resource
        details (json): Action-specific metadata
        error_message (text): Error details if failed
        actor (str): System or user identifier
        ip_address (str): Client IP for access logs
        timestamp (datetime): Action timestamp

    Retention:
        - Minimum 6 years per HIPAA requirements
        - No deletion allowed (append-only)
    """
```

---

### `backend/routes/ingest.py`

**Architectural Role:** Athena data ingestion API endpoints

**Position in Data Flow:** Entry point for external clinical data

**Critical Design Principles:**
- Idempotent POST operations
- Automatic patient linking
- Comprehensive error handling

**Endpoints:**

```python
@router.post("/athena", response_model=IngestResponse)
async def ingest_athena_event(
    payload: AthenaEventPayload,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
) -> IngestResponse:
    """
    Receive and store clinical event from Athena-Scraper.

    Parameters:
        payload: AthenaEventPayload
            - athena_patient_id (str): Patient MRN [required]
            - event_type (str): Event category [required]
            - event_subtype (str): Sub-category [optional]
            - payload (dict): Raw Athena data [required]
            - captured_at (str): ISO timestamp [required]
            - source_endpoint (str): Athena API path [optional]
            - confidence (float): Classification score [optional]

        db: Database session (injected)

    Returns:
        IngestResponse:
            - status: "success" | "duplicate" | "error"
            - event_id: UUID of created/existing event
            - message: Human-readable status

    Processing Steps:
        1. Generate idempotency key from payload
        2. Check for existing event with same key
        3. If duplicate: return existing event_id
        4. Parse timestamp to datetime
        5. Query patients table for MRN match
        6. If found: set patient_id foreign key
        7. Create ClinicalEvent record
        8. Log to IntegrationAuditLog
        9. Commit transaction
        10. Return success response

    Error Handling:
        - Duplicate: 200 with status="duplicate"
        - Validation: 422 with field details
        - Database: 500 with error message
        - All errors logged to audit table

    Performance:
        - Average: 30-50ms
        - Bottleneck: Patient lookup query
        - Optimization: Index on athena_mrn
    """

@router.get("/events/{athena_patient_id}")
async def get_patient_events(
    athena_patient_id: str,
    event_type: Optional[str] = Query(None),
    limit: int = Query(100, le=1000),
    db: Session = Depends(get_db)
) -> dict:
    """
    Retrieve clinical events for a patient.

    Parameters:
        athena_patient_id: Patient MRN
        event_type: Filter by category (optional)
        limit: Maximum results (default 100, max 1000)

    Returns:
        {
            "patient_id": str,
            "count": int,
            "events": [
                {
                    "id": str,
                    "type": str,
                    "subtype": str,
                    "captured_at": str,
                    "confidence": float,
                    "payload_keys": List[str]
                }
            ]
        }

    Use Cases:
        - Debugging ingestion pipeline
        - Building patient timelines
        - Verifying data completeness
    """

@router.get("/stats")
async def get_ingestion_stats(db: Session = Depends(get_db)) -> dict:
    """
    Get aggregate ingestion statistics.

    Returns:
        {
            "total_events": int,
            "unique_patients": int,
            "by_type": {
                "medication": int,
                "problem": int,
                ...
            }
        }

    Use Cases:
        - Monitoring dashboard
        - Capacity planning
        - Integration health checks
    """

@router.get("/health")
async def health_check() -> dict:
    """
    Service health check endpoint.

    Returns:
        {"status": "healthy", "service": "scc-ingest"}

    Use Cases:
        - Load balancer health probes
        - Athena-Scraper connectivity check
        - Monitoring systems
    """
```

---

## Security Model

### Authentication & Authorization

| Layer | Current State | Production Requirement |
|-------|--------------|------------------------|
| API Authentication | None | JWT Bearer tokens |
| User Authorization | None | Role-based access control |
| Service-to-Service | None | API key or mTLS |

### Data Protection

```
┌─────────────────────────────────────────────────────────────────┐
│                      SECURITY LAYERS                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  TRANSPORT          HTTPS/TLS 1.3 (via nginx reverse proxy)    │
│                                                                 │
│  APPLICATION        Input validation (Pydantic schemas)        │
│                     SQL injection prevention (SQLAlchemy ORM)  │
│                     CORS restrictions                          │
│                                                                 │
│  DATA               PostgreSQL role-based access               │
│                     Encrypted connections (sslmode=require)    │
│                     Audit logging (integration_audit_log)      │
│                                                                 │
│  SECRETS            Environment variables (.env)               │
│                     .gitignore exclusion                       │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### HIPAA Compliance Measures

1. **Audit Logging**: All data access logged to `integration_audit_log`
2. **Data Integrity**: Append-only event storage prevents modification
3. **Access Controls**: Database credentials isolated in .env
4. **Encryption**: TLS for transport, PostgreSQL encryption at rest
5. **Minimum Necessary**: API returns only requested fields

### Sensitive Data Handling

```python
# Files excluded from version control (.gitignore)
.env                    # Database credentials, API keys
logs/                   # May contain PHI in error messages
*.log                   # Application logs
__pycache__/            # Compiled Python (may contain secrets)
```

---

## Database Schema

### Entity Relationship Diagram

```
┌─────────────────┐       ┌─────────────────┐       ┌─────────────────┐
│    patients     │       │ voice_transcripts│      │ pvi_procedures  │
├─────────────────┤       ├─────────────────┤       ├─────────────────┤
│ id (PK)         │──┐    │ id (PK)         │       │ id (PK)         │
│ first_name      │  │    │ patient_id (FK) │───┐   │ patient_id (FK) │──┐
│ last_name       │  │    │ raw_transcript  │   │   │ procedure_date  │  │
│ dob             │  │    │ tags            │   │   │ rutherford      │  │
│ athena_mrn (UQ) │  │    │ confidence      │   │   │ arteries        │  │
│ created_at      │  │    │ created_at      │   │   │ complications   │  │
└─────────────────┘  │    └─────────────────┘   │   └─────────────────┘  │
         │           │                          │                        │
         │           └──────────────────────────┼────────────────────────┘
         │                                      │
         ▼                                      ▼
┌─────────────────┐       ┌─────────────────┐       ┌─────────────────┐
│ clinical_events │       │clinical_synopses│       │structured_      │
├─────────────────┤       ├─────────────────┤       │findings         │
│ id (PK)         │       │ id (PK)         │       ├─────────────────┤
│ patient_id (FK) │───────│ patient_id (FK) │       │ id (PK)         │
│ athena_patient_ │       │ synopsis_text   │       │ patient_id (FK) │
│   id            │       │ ai_model        │       │ finding_type    │
│ event_type      │       │ created_at      │       │ value           │
│ raw_payload     │       └─────────────────┘       │ source_event_id │
│ idempotency_key │                                 └─────────────────┘
│   (UQ)          │
│ captured_at     │
└─────────────────┘
         │
         ▼
┌─────────────────┐
│ integration_    │
│ audit_log       │
├─────────────────┤
│ id (PK)         │
│ action          │
│ resource_type   │
│ resource_id     │
│ details         │
│ timestamp       │
└─────────────────┘
```

### Index Strategy

```sql
-- High-cardinality lookups
CREATE INDEX ix_patients_athena_mrn ON patients(athena_mrn);
CREATE INDEX ix_clinical_events_athena_patient ON clinical_events(athena_patient_id);

-- Temporal queries
CREATE INDEX ix_clinical_events_captured_at ON clinical_events(captured_at);
CREATE INDEX ix_audit_log_timestamp ON integration_audit_log(timestamp);

-- Composite for timeline queries
CREATE INDEX ix_ce_patient_time ON clinical_events(athena_patient_id, captured_at);

-- Deduplication
CREATE UNIQUE INDEX ix_ce_idempotency ON clinical_events(idempotency_key);
```

---

## API Reference

### Base URL

```
Development: http://localhost:8001
Production:  http://100.75.237.36:8001
```

### Endpoints Summary

#### Core Endpoints
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Service info and health |
| GET | `/health` | Detailed health check |
| POST | `/upload` | Upload transcript |
| POST | `/batch-upload` | Batch upload |

#### ORCC Integration (Patients & Procedures)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/patients` | List/search patients |
| GET | `/api/patients/{mrn}` | Get patient by MRN |
| POST | `/api/patients` | Create patient |
| GET | `/api/procedures` | List procedures |
| GET | `/api/procedures/{id}` | Get procedure details |
| POST | `/api/procedures` | Create procedure with planning data |
| PATCH | `/api/procedures/{id}` | Update procedure |
| DELETE | `/api/procedures/{id}` | Delete procedure (cleanup duplicates) |
| GET | `/api/planning/{mrn}` | Get planning data for workspace |
| GET | `/api/orcc/status` | ORCC integration status |

#### Tasks API (NEW - 2026)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/tasks` | List tasks (with filters) |
| POST | `/api/tasks` | Create task |
| GET | `/api/tasks/{id}` | Get task by ID |
| PATCH | `/api/tasks/{id}` | Update task |
| DELETE | `/api/tasks/{id}` | Delete task |
| POST | `/api/tasks/{id}/complete` | Mark task complete |
| GET | `/api/tasks/patient/{mrn}` | Tasks by patient |
| GET | `/api/tasks/procedure/{id}` | Tasks by procedure |
| GET | `/api/tasks/stats/summary` | Task statistics |

#### Shadow Coder API (NEW - Migrated from SCC)
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/shadow-coder/status` | Service status |
| POST | `/api/shadow-coder/intake/plaud` | Plaud transcript intake |
| POST | `/api/shadow-coder/intake/zapier` | Zapier webhook |
| GET | `/api/shadow-coder/intake/status/{id}` | Voice note status |
| GET | `/api/shadow-coder/intake/recent` | Recent voice notes |
| GET | `/api/shadow-coder/facts/{case_id}` | Get case facts |
| POST | `/api/shadow-coder/facts/{case_id}` | Add fact to case |
| GET | `/api/shadow-coder/facts/{case_id}/history` | Full fact history |
| GET | `/api/shadow-coder/prompts/{case_id}` | Get active prompts |
| POST | `/api/shadow-coder/prompts/{id}/action` | Execute prompt action |
| POST | `/api/shadow-coder/analyze` | Analyze transcript (AI) |

#### WebSocket (NEW - Real-time)
| Method | Endpoint | Description |
|--------|----------|-------------|
| WS | `/ws?client_id={id}` | Real-time connection |
| GET | `/ws/stats` | Connection statistics |

#### Athena EMR Integration
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/ingest/athena` | Ingest Athena event |
| GET | `/ingest/events/{mrn}` | Get patient events |
| GET | `/ingest/clinical/{mrn}` | Fetch all clinical data |
| GET | `/ingest/stats` | Ingestion statistics |
| GET | `/ingest/health` | Ingestion service health |

#### AI Services
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/parse` | Parse transcript |
| POST | `/api/synopsis` | Generate synopsis |
| POST | `/api/extract` | Extract PVI fields |
| POST | `/clinical/query` | Natural language query |

### Request/Response Examples

See `/docs` endpoint for interactive Swagger documentation.

---

## Integration Patterns

### Athena-Scraper Integration

```python
# Athena-Scraper sends to PlaudAI
POST /ingest/athena
Content-Type: application/json

{
    "athena_patient_id": "18889107",
    "event_type": "medication",
    "event_subtype": "active",
    "payload": {
        "medication_name": "Aspirin",
        "dose": "81mg",
        "frequency": "daily"
    },
    "captured_at": "2025-12-28T10:00:00Z",
    "source_endpoint": "/api/medications/active",
    "confidence": 0.95,
    "indexer_version": "2.0.0"
}
```

### Response Handling

```python
# Success
{"status": "success", "event_id": "uuid...", "message": "Event ingested"}

# Duplicate (idempotent - not an error)
{"status": "duplicate", "event_id": "uuid...", "message": "Already ingested"}

# Validation Error
HTTP 422
{"detail": [{"loc": ["body", "athena_patient_id"], "msg": "required"}]}
```

### Bidirectional Integration (Phase 3 - NEW)

**Purpose:** Enable Athena-Scraper to fetch stored clinical data when a patient is opened.

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                       BIDIRECTIONAL DATA FLOW                                    │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│   1. User opens patient in Athena                                                │
│      │                                                                           │
│      ▼                                                                           │
│   2. GET /ingest/clinical/{mrn} ───────────────► Plaud Backend (8001)            │
│      │                                                                           │
│      ▼                                                                           │
│   3. Receive stored clinical data (instant)                                      │
│      │                                                                           │
│      ▼                                                                           │
│   4. Display in WebUI ◄─────────────────────────────────────────────             │
│      │                                                                           │
│      │  (Meanwhile, scrape new data from Athena...)                              │
│      ▼                                                                           │
│   5. POST /ingest/athena ──────────────────────► Store new events                │
│      │                                                                           │
│      ▼                                                                           │
│   6. Update WebUI with new data                                                  │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

**Fetch Clinical Data:**
```bash
# Request
GET /ingest/clinical/18889107

# Response (200 OK)
{
  "status": "found",
  "athena_mrn": "18889107",
  "patient_id": 31,
  "last_updated": "2026-01-06T04:51:02.218698",
  "clinical_data": {
    "demographics": {
      "first_name": "John N",
      "last_name": "Finnicum",
      "date_of_birth": "1944-02-18",
      "gender": null,
      "race": null,
      "zip_code": "31721"
    },
    "medications": [...],
    "problems": [...],
    "allergies": [...],
    "labs": [...],
    "vitals": {...},
    "encounters": [...],
    "documents": [...],
    "other": [...]
  },
  "event_count": 658,
  "sources": ["athena"]
}
```

**Benefits:**
- **Instant display**: Show stored data immediately while scraping new data
- **Persistent access**: Data available even if Athena session expired
- **Longitudinal view**: See historical data accumulated over multiple visits

**For Athena-Scraper implementation details**, see `ATHENA_SCRAPER_DATABASE_SPEC.md` Section 11.

---

## Maintenance Guide

### Log Analysis

```bash
# View real-time logs
tail -f logs/plaudai_uploader.log

# Find errors
grep ERROR logs/plaudai_uploader.log

# Check ingestion activity
grep "AUTO-LINKED\|NO PATIENT MATCH" logs/plaudai_uploader.log

# Count events by type
grep "Ingested" logs/plaudai_uploader.log | awk '{print $4}' | sort | uniq -c
```

### Database Maintenance

```sql
-- Check table sizes
SELECT relname, pg_size_pretty(pg_total_relation_size(relid))
FROM pg_catalog.pg_statio_user_tables
ORDER BY pg_total_relation_size(relid) DESC;

-- Vacuum and analyze
VACUUM ANALYZE clinical_events;
VACUUM ANALYZE integration_audit_log;

-- Check for orphan events (no patient link)
SELECT COUNT(*) FROM clinical_events WHERE patient_id IS NULL;
```

### Common Issues

| Symptom | Cause | Resolution |
|---------|-------|------------|
| 405 on /ingest | Wrong endpoint | Use /ingest/athena |
| Events not linking | Patient doesn't exist | Create patient first |
| Duplicate warnings | Same data sent twice | Normal - idempotency working |
| Connection refused | Server not running | Start uvicorn |
| API key expired | Google key issue | Update .env, restart |

### Server Management

```bash
# Start server
cd ~/plaudai_uploader
conda activate plaudai
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8001

# Check if running
ps aux | grep uvicorn

# Stop server
pkill -f "uvicorn.*8001"

# Check port usage
lsof -i :8001
```

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 3.2.0 | Jan 2026 | **Full Integration**: DELETE /api/procedures, saveOrUpdateProcedure(), Claude AI extraction, barriers PATCH fix |
| 3.1.0 | Jan 2026 | **Procedures API**: POST /api/procedures, GET /api/planning/{mrn}, vessel_data, ICD-10, CPT codes |
| 3.0.0 | Jan 2026 | **SCC Migration**: Tasks API, Shadow Coder, WebSocket server, ORCC integration |
| 2.1.0 | Jan 2026 | Bidirectional integration: GET /ingest/clinical/{mrn}, plaud-fetch telemetry |
| 2.0.0 | Dec 2025 | Athena integration, auto-linking |
| 1.5.0 | Dec 2025 | Patient search, rebranding |
| 1.0.0 | Nov 2025 | Initial release |

---

## Related Documentation

| Document | Location | Purpose |
|----------|----------|---------|
| SCC Migration Spec | `SCC_MIGRATION_SPEC.md` | Full migration plan from SCC |
| SHARED_WORKSPACE | `.claude-team/SHARED_WORKSPACE.md` | Team coordination |
| API Documentation | `/docs` (live endpoint) | Interactive Swagger docs |

---

**Organization:** Albany Vascular Specialist Center
**Location:** 2300 Dawson Road, Suite 101, Albany, GA 31707
**Contact:** (229) 436-8535
**Server:** 100.75.237.36 (Tailscale) | Port 8001
