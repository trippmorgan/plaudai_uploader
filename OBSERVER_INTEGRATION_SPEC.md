# Medical Mirror Observer Integration Specification
## Albany Vascular AI / Plaud AI Uploader

---

## SYSTEM IDENTIFICATION

| Property | Value |
|----------|-------|
| **Source Name** | `plaud-ai-uploader` |
| **Application** | Albany Vascular AI Clinical Documentation System |
| **Version** | 2.0.0 |
| **Language** | Python 3.11 / FastAPI |

---

## PORT MAPPING & NETWORK TOPOLOGY

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           NETWORK TOPOLOGY                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────┐         ┌─────────────────────┐                   │
│  │   Browser/Frontend  │         │  Athena-Scraper     │                   │
│  │   (User Interface)  │         │  (Chrome Extension) │                   │
│  └──────────┬──────────┘         └──────────┬──────────┘                   │
│             │                               │                               │
│             │ HTTP :8001                    │ HTTP :8001                    │
│             ▼                               ▼                               │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │                    PLAUD AI UPLOADER                                 │  │
│  │                    Port: 8001                                        │  │
│  │                    Host: 0.0.0.0                                     │  │
│  │                                                                      │  │
│  │  Endpoints:                                                          │  │
│  │    POST /upload           - Transcript submission                   │  │
│  │    GET  /patients         - Patient search/list                     │  │
│  │    POST /clinical/query   - AI clinical queries                     │  │
│  │    POST /ingest/athena    - Athena EMR ingestion                    │  │
│  │    POST /synopsis/generate/{id} - AI synopsis generation            │  │
│  │    GET  /stats            - System statistics                       │  │
│  └──────────────────────────────┬───────────────────────────────────────┘  │
│                                 │                                           │
│           Telemetry ────────────┤                                           │
│           POST /api/events      │                                           │
│                                 ▼                                           │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │                  MEDICAL MIRROR OBSERVER                             │  │
│  │                  Port: 54112                                         │  │
│  │                  Host: localhost                                     │  │
│  │                                                                      │  │
│  │  Receives:                                                           │  │
│  │    - Transcript upload events (success/failure/quality)             │  │
│  │    - Patient query events                                           │  │
│  │    - Clinical AI query events                                       │  │
│  │    - Athena ingestion events                                        │  │
│  │    - Data quality assessments                                       │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                 │                                           │
│                                 │ SQL :5432                                 │
│                                 ▼                                           │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │                     POSTGRESQL DATABASE                              │  │
│  │                     Port: 5432                                       │  │
│  │                     Host: server1-70TR000LUX                         │  │
│  │                     Database: surgical_command_center                │  │
│  │                                                                      │  │
│  │  Tables:                                                             │  │
│  │    - patients              - voice_transcripts                      │  │
│  │    - pvi_procedures        - clinical_synopses                      │  │
│  │    - clinical_events       - integration_audit_log                  │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
│  ┌─────────────────────┐                                                   │
│  │   Google Gemini AI  │◄──── AI Processing (gemini-2.0-flash-exp)         │
│  │   (External API)    │                                                   │
│  └─────────────────────┘                                                   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Port Summary

| Service | Port | Protocol | Purpose |
|---------|------|----------|---------|
| Plaud AI Uploader | 8001 | HTTP | Main API server |
| Medical Mirror Observer | 54112 | HTTP | Telemetry collection |
| PostgreSQL | 5432 | TCP | Database |
| Gemini AI | 443 | HTTPS | External AI API |

### Environment Variables

```bash
# Plaud AI Configuration
API_HOST=0.0.0.0
API_PORT=8001
DEBUG=True

# Database
DB_HOST=server1-70TR000LUX
DB_PORT=5432
DB_NAME=surgical_command_center
DB_USER=scc_user

# Observer Telemetry
OBSERVER_URL=http://localhost:54112

# AI
GOOGLE_API_KEY=<redacted>
GEMINI_MODEL=gemini-2.0-flash-exp
```

---

## TELEMETRY EVENT SCHEMA

### Base Event Structure

All events sent to `POST http://localhost:54112/api/events` follow this schema:

```json
{
  "type": "OBSERVER_TELEMETRY",
  "source": "plaud-ai-uploader",
  "event": {
    "stage": "<stage-name>",
    "action": "<ACTION_NAME>",
    "success": true|false,
    "timestamp": "2025-01-05T10:30:00.000Z",
    "correlationId": "plaud_1735689000000",
    "data": {
      // Event-specific payload
    }
  }
}
```

### Telemetry Stages

| Stage | Description | Endpoints |
|-------|-------------|-----------|
| `upload` | Transcript/record submission | POST /upload |
| `query` | Patient lookup operations | GET /patients |
| `ai-query` | Clinical AI question answering | POST /clinical/query |
| `ingest` | Athena EMR data ingestion | POST /ingest/athena |
| `synopsis` | AI synopsis generation | POST /synopsis/generate |
| `plaud-fetch` | **NEW** Clinical data fetch (bidirectional) | GET /ingest/clinical/{mrn} |

---

## COMPLETE EVENT CATALOG

### Stage: `upload`

#### 1. TRANSCRIPT_RECEIVED
**Trigger:** Beginning of upload processing
```json
{
  "source": "plaud-ai-uploader",
  "stage": "upload",
  "action": "TRANSCRIPT_RECEIVED",
  "success": true,
  "timestamp": "2025-01-05T10:30:00.000Z",
  "correlationId": "plaud_1735689000000",
  "data": {
    "hasPatientInfo": true,
    "recordType": "operative_note",
    "hasMrn": true
  }
}
```

#### 2. TRANSCRIPT_PROCESSED
**Trigger:** Successful completion of upload
```json
{
  "source": "plaud-ai-uploader",
  "stage": "upload",
  "action": "TRANSCRIPT_PROCESSED",
  "success": true,
  "timestamp": "2025-01-05T10:30:05.000Z",
  "correlationId": "plaud_1735689000000",
  "data": {
    "correlationId": "plaud_1735689000000",
    "patientId": 42,
    "transcriptId": 156,
    "confidence": 0.95,
    "category": "operative_note",
    "tagsCount": 8
  }
}
```

#### 3. DATA_QUALITY_ASSESSMENT
**Trigger:** After successful upload (data completeness tracking)
```json
{
  "source": "plaud-ai-uploader",
  "stage": "upload",
  "action": "DATA_QUALITY_ASSESSMENT",
  "success": true,
  "timestamp": "2025-01-05T10:30:05.100Z",
  "correlationId": "plaud_1735689000000",
  "data": {
    "correlationId": "plaud_1735689000000",
    "fieldsPresent": {
      "firstName": true,
      "lastName": true,
      "dob": true,
      "mrn": true,
      "birthSex": false,
      "race": false,
      "zipCode": false,
      "rawTranscript": true,
      "plaudNote": true,
      "recordingDate": true,
      "visitType": false
    },
    "hasStructuredData": true,
    "hasPviFields": true
  }
}
```

#### 4. TRANSCRIPT_FAILED
**Trigger:** Upload processing error
```json
{
  "source": "plaud-ai-uploader",
  "stage": "upload",
  "action": "TRANSCRIPT_FAILED",
  "success": false,
  "timestamp": "2025-01-05T10:30:02.000Z",
  "correlationId": "plaud_1735689000000",
  "data": {
    "correlationId": "plaud_1735689000000",
    "error": "Database connection timeout"
  }
}
```

---

### Stage: `query`

#### 1. PATIENTS_QUERIED
**Trigger:** Patient list/search completed
```json
{
  "source": "plaud-ai-uploader",
  "stage": "query",
  "action": "PATIENTS_QUERIED",
  "success": true,
  "timestamp": "2025-01-05T10:31:00.000Z",
  "correlationId": "plaud_1735689060000",
  "data": {
    "resultCount": 15,
    "queryType": "search"
  }
}
```

**queryType values:** `"search"` | `"list"`

#### 2. PATIENTS_QUERY_FAILED
**Trigger:** Patient query error
```json
{
  "source": "plaud-ai-uploader",
  "stage": "query",
  "action": "PATIENTS_QUERY_FAILED",
  "success": false,
  "timestamp": "2025-01-05T10:31:01.000Z",
  "correlationId": "plaud_1735689061000",
  "data": {
    "error": "Database query timeout"
  }
}
```

---

### Stage: `ai-query`

#### 1. QUERY_SUBMITTED
**Trigger:** Clinical AI query received
```json
{
  "source": "plaud-ai-uploader",
  "stage": "ai-query",
  "action": "QUERY_SUBMITTED",
  "success": true,
  "timestamp": "2025-01-05T10:32:00.000Z",
  "correlationId": "plaud_1735689120000",
  "data": {
    "queryLength": 45,
    "patientFound": false
  }
}
```

#### 2. RESPONSE_GENERATED
**Trigger:** AI response successfully generated
```json
{
  "source": "plaud-ai-uploader",
  "stage": "ai-query",
  "action": "RESPONSE_GENERATED",
  "success": true,
  "timestamp": "2025-01-05T10:32:05.000Z",
  "correlationId": "plaud_1735689120000",
  "data": {
    "correlationId": "plaud_1735689120000",
    "responseLength": 1250,
    "dataSources": {
      "transcripts": 5,
      "procedures": 3
    }
  }
}
```

#### 3. QUERY_FAILED
**Trigger:** AI query processing error
```json
{
  "source": "plaud-ai-uploader",
  "stage": "ai-query",
  "action": "QUERY_FAILED",
  "success": false,
  "timestamp": "2025-01-05T10:32:02.000Z",
  "correlationId": "plaud_1735689120000",
  "data": {
    "correlationId": "plaud_1735689120000",
    "error": "Could not identify patient from your query"
  }
}
```

---

### Stage: `ingest`

#### 1. ATHENA_EVENT_RECEIVED
**Trigger:** Athena-Scraper sends EMR data
```json
{
  "source": "plaud-ai-uploader",
  "stage": "ingest",
  "action": "ATHENA_EVENT_RECEIVED",
  "success": true,
  "timestamp": "2025-01-05T10:33:00.000Z",
  "correlationId": "plaud_1735689180000",
  "data": {
    "eventType": "medication",
    "hasPatientLink": false
  }
}
```

**eventType values:** `"medication"` | `"problem"` | `"vital"` | `"lab"` | `"encounter"` | `"allergy"`

#### 2. ATHENA_EVENT_PROCESSED
**Trigger:** Athena data successfully stored
```json
{
  "source": "plaud-ai-uploader",
  "stage": "ingest",
  "action": "ATHENA_EVENT_PROCESSED",
  "success": true,
  "timestamp": "2025-01-05T10:33:01.000Z",
  "correlationId": "plaud_1735689180000",
  "data": {
    "correlationId": "plaud_1735689180000",
    "eventType": "medication",
    "status": "success"
  }
}
```

**status values:** `"success"` | `"duplicate"`

#### 3. PATIENT_LINK_STATUS
**Trigger:** After ingestion, reports patient auto-linking result
```json
{
  "source": "plaud-ai-uploader",
  "stage": "ingest",
  "action": "PATIENT_LINK_STATUS",
  "success": true,
  "timestamp": "2025-01-05T10:33:01.100Z",
  "correlationId": "plaud_1735689180000",
  "data": {
    "correlationId": "plaud_1735689180000",
    "linkedToPatient": true,
    "patientId": 42
  }
}
```

#### 4. ATHENA_EVENT_FAILED
**Trigger:** Athena ingestion error
```json
{
  "source": "plaud-ai-uploader",
  "stage": "ingest",
  "action": "ATHENA_EVENT_FAILED",
  "success": false,
  "timestamp": "2025-01-05T10:33:02.000Z",
  "correlationId": "plaud_1735689180000",
  "data": {
    "correlationId": "plaud_1735689180000",
    "eventType": "medication",
    "error": "Invalid payload structure"
  }
}
```

---

### Stage: `plaud-fetch` (NEW - Phase 3 Bidirectional Integration)

These events track clinical data fetch operations when Athena-Scraper requests stored patient data.

#### 1. FETCH_PATIENT
**Trigger:** Clinical data fetch requested
```json
{
  "source": "plaud-ai-uploader",
  "stage": "plaud-fetch",
  "action": "FETCH_PATIENT",
  "success": true,
  "timestamp": "2026-01-06T10:00:00.000Z",
  "correlationId": "plaud_1736157600000",
  "data": {
    "athena_mrn": "18889107"
  }
}
```

#### 2. FETCH_SUCCESS
**Trigger:** Clinical data successfully returned
```json
{
  "source": "plaud-ai-uploader",
  "stage": "plaud-fetch",
  "action": "FETCH_SUCCESS",
  "success": true,
  "timestamp": "2026-01-06T10:00:00.050Z",
  "correlationId": "plaud_1736157600000",
  "data": {
    "correlationId": "plaud_1736157600000",
    "patientId": 31,
    "eventCount": 658,
    "durationMs": 45
  }
}
```

#### 3. FETCH_NOT_FOUND
**Trigger:** Patient MRN not in database
```json
{
  "source": "plaud-ai-uploader",
  "stage": "plaud-fetch",
  "action": "FETCH_NOT_FOUND",
  "success": false,
  "timestamp": "2026-01-06T10:00:00.020Z",
  "correlationId": "plaud_1736157600000",
  "data": {
    "correlationId": "plaud_1736157600000",
    "athena_mrn": "UNKNOWN123"
  }
}
```

#### 4. FETCH_FAILED
**Trigger:** Clinical data fetch error
```json
{
  "source": "plaud-ai-uploader",
  "stage": "plaud-fetch",
  "action": "FETCH_FAILED",
  "success": false,
  "timestamp": "2026-01-06T10:00:00.100Z",
  "correlationId": "plaud_1736157600000",
  "data": {
    "correlationId": "plaud_1736157600000",
    "athena_mrn": "18889107",
    "error": "Database connection timeout",
    "duration_ms": 5000
  }
}
```

---

## DATA FLOW PIPELINES

### Pipeline 1: Transcript Upload

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        TRANSCRIPT UPLOAD PIPELINE                           │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  1. POST /upload                                                            │
│     │                                                                       │
│     ├──► emit: upload/TRANSCRIPT_RECEIVED                                  │
│     │    {hasPatientInfo, recordType, hasMrn}                              │
│     │                                                                       │
│     ├──► Get or Create Patient                                             │
│     │                                                                       │
│     ├──► Gemini AI: Category-specific parsing                              │
│     │    (operative_note, imaging, lab_result, office_visit)               │
│     │                                                                       │
│     ├──► Generate medical tags                                             │
│     │                                                                       │
│     ├──► Extract PVI fields (if operative_note)                            │
│     │                                                                       │
│     ├──► Save VoiceTranscript record                                       │
│     │                                                                       │
│     ├──► Create PVIProcedure (if applicable)                               │
│     │                                                                       │
│     ├──► emit: upload/TRANSCRIPT_PROCESSED                                 │
│     │    {patientId, transcriptId, confidence, category, tagsCount}        │
│     │                                                                       │
│     └──► emit: upload/DATA_QUALITY_ASSESSMENT                              │
│          {fieldsPresent: {...}, hasStructuredData, hasPviFields}           │
│                                                                             │
│  On Error:                                                                  │
│     └──► emit: upload/TRANSCRIPT_FAILED                                    │
│          {error: "..."}                                                     │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Pipeline 2: Clinical AI Query

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       CLINICAL AI QUERY PIPELINE                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  1. POST /clinical/query                                                    │
│     │   Body: {"query": "What medications is Mr. Jones on?"}               │
│     │                                                                       │
│     ├──► emit: ai-query/QUERY_SUBMITTED                                    │
│     │    {queryLength, patientFound: false}                                │
│     │                                                                       │
│     ├──► Extract patient from query                                        │
│     │    Strategy 1: MRN pattern matching                                  │
│     │    Strategy 2: Full name extraction                                  │
│     │    Strategy 3: Last name with title                                  │
│     │                                                                       │
│     ├──► Gather patient data (transcripts, procedures)                     │
│     │                                                                       │
│     ├──► Build context-aware Gemini prompt                                 │
│     │                                                                       │
│     ├──► Gemini AI: Generate clinical response                             │
│     │                                                                       │
│     └──► emit: ai-query/RESPONSE_GENERATED                                 │
│          {responseLength, dataSources: {transcripts: N, procedures: N}}    │
│                                                                             │
│  On Error:                                                                  │
│     └──► emit: ai-query/QUERY_FAILED                                       │
│          {error: "Could not identify patient..."}                          │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Pipeline 3: Athena EMR Ingestion

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       ATHENA EMR INGESTION PIPELINE                         │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  1. POST /ingest/athena                                                     │
│     │   From: Athena-Scraper Chrome Extension                              │
│     │                                                                       │
│     ├──► emit: ingest/ATHENA_EVENT_RECEIVED                                │
│     │    {eventType: "medication", hasPatientLink: false}                  │
│     │                                                                       │
│     ├──► Generate idempotency key (SHA256)                                 │
│     │                                                                       │
│     ├──► Check for duplicate                                               │
│     │    │                                                                  │
│     │    └──► If duplicate:                                                │
│     │         emit: ingest/ATHENA_EVENT_PROCESSED {status: "duplicate"}    │
│     │         return early                                                 │
│     │                                                                       │
│     ├──► Auto-link to existing patient (by MRN)                            │
│     │                                                                       │
│     ├──► Create ClinicalEvent record                                       │
│     │                                                                       │
│     ├──► Log to IntegrationAuditLog (HIPAA)                                │
│     │                                                                       │
│     ├──► emit: ingest/ATHENA_EVENT_PROCESSED                               │
│     │    {eventType, status: "success"}                                    │
│     │                                                                       │
│     └──► emit: ingest/PATIENT_LINK_STATUS                                  │
│          {linkedToPatient: true/false, patientId: N}                       │
│                                                                             │
│  On Error:                                                                  │
│     └──► emit: ingest/ATHENA_EVENT_FAILED                                  │
│          {eventType, error: "..."}                                         │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Pipeline 4: Bidirectional Clinical Fetch (NEW)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                   BIDIRECTIONAL CLINICAL FETCH PIPELINE                      │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  1. GET /ingest/clinical/{athena_mrn}                                       │
│     │   From: Athena-Scraper (on patient context change)                    │
│     │                                                                       │
│     ├──► emit: plaud-fetch/FETCH_PATIENT                                    │
│     │    {athena_mrn: "18889107"}                                           │
│     │                                                                       │
│     ├──► Query: SELECT * FROM patients WHERE athena_mrn = ?                 │
│     │    │                                                                  │
│     │    └──► If not found:                                                 │
│     │         emit: plaud-fetch/FETCH_NOT_FOUND                             │
│     │         return {status: "not_found"}                                  │
│     │                                                                       │
│     ├──► Query: SELECT * FROM clinical_events WHERE athena_patient_id = ?   │
│     │                                                                       │
│     ├──► Organize events by type:                                           │
│     │    - demographics (from patients table)                               │
│     │    - medications, problems, allergies, labs                           │
│     │    - vitals (most recent only)                                        │
│     │    - encounters, documents                                            │
│     │                                                                       │
│     ├──► emit: plaud-fetch/FETCH_SUCCESS                                    │
│     │    {patientId, eventCount, durationMs}                                │
│     │                                                                       │
│     └──► Return structured clinical_data                                    │
│                                                                             │
│  On Error:                                                                  │
│     └──► emit: plaud-fetch/FETCH_FAILED                                     │
│          {athena_mrn, error, duration_ms}                                   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## DASHBOARD SUGGESTIONS FOR OBSERVER

### Plaud Sync Metrics (NEW)

Consider adding these metrics to the Observer dashboard:

| Metric | Description | Query |
|--------|-------------|-------|
| **Fetch Success Rate** | % of clinical fetches that return data | `FETCH_SUCCESS / (FETCH_SUCCESS + FETCH_NOT_FOUND + FETCH_FAILED)` |
| **Avg Fetch Time** | Mean response time for clinical fetches | `AVG(durationMs) WHERE action = "FETCH_SUCCESS"` |
| **Data Freshness** | Time since last sync per patient | `NOW() - MAX(timestamp) GROUP BY patientId` |
| **Export Success Rate** | % of Athena events successfully stored | `ATHENA_EVENT_PROCESSED / ATHENA_EVENT_RECEIVED` |
| **Patients with Data** | Count of unique patients with stored data | `COUNT(DISTINCT patientId) WHERE eventCount > 0` |

### Recommended Dashboard Panels

1. **Sync Status Overview**
   - Real-time fetch/export success rates
   - Active patient count
   - Events ingested today

2. **Performance Monitoring**
   - P50/P95/P99 fetch latencies
   - Failed operations alert threshold
   - Database query times

3. **Data Quality**
   - Patient link rate (% of events linked to patients)
   - Duplicate detection rate
   - Event type distribution

---

## TELEMETRY CODE IMPLEMENTATION

### Core Telemetry Module

```python
# backend/services/telemetry.py

import asyncio
import httpx
from datetime import datetime

OBSERVER_URL = "http://localhost:54112"
SOURCE_NAME = "plaud-ai-uploader"
TIMEOUT_SECONDS = 2.0

async def emit(
    stage: str,
    action: str,
    data: dict = None,
    success: bool = True,
    correlation_id: str = None
) -> str:
    """Fire-and-forget telemetry emission."""

    if correlation_id is None:
        correlation_id = f"plaud_{int(time.time() * 1000)}"

    # Observer's expected envelope format
    payload = {
        "type": "OBSERVER_TELEMETRY",
        "source": SOURCE_NAME,
        "event": {
            "stage": stage,
            "action": action,
            "success": success,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "correlationId": correlation_id,
            "data": data or {}
        }
    }

    # Non-blocking send
    asyncio.create_task(_send_event(payload))
    return correlation_id

async def _send_event(payload: dict) -> None:
    """Send event to Observer - handles all errors gracefully."""
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS) as client:
            await client.post(
                f"{OBSERVER_URL}/api/events",
                json=payload,
                headers={"Content-Type": "application/json"}
            )
    except Exception:
        pass  # Graceful degradation
```

### Endpoint Integration Example

```python
# backend/main.py - Upload Endpoint

@app.post("/upload", response_model=UploadResponse)
async def upload_note(data: TranscriptUpload, db: Session = Depends(get_db)):

    # 1. Emit received event
    correlation_id = await emit_upload_received(
        has_patient_info=bool(data.first_name and data.athena_mrn),
        record_type=data.record_category or "office_visit",
        mrn=data.athena_mrn
    )

    try:
        # ... processing logic ...

        # 2. Emit success event
        await emit_upload_processed(
            correlation_id=correlation_id,
            patient_id=patient.id,
            transcript_id=transcript.id,
            confidence=confidence,
            category=category,
            tags_count=len(tags)
        )

        # 3. Emit data quality assessment
        await emit('upload', 'DATA_QUALITY_ASSESSMENT', {
            'correlationId': correlation_id,
            'fieldsPresent': {
                'firstName': bool(data.first_name),
                'lastName': bool(data.last_name),
                # ... etc
            },
            'hasStructuredData': bool(category_data),
            'hasPviFields': bool(pvi_fields)
        })

        return UploadResponse(...)

    except Exception as e:
        # 4. Emit failure event
        await emit_upload_failed(correlation_id=correlation_id, error=str(e))
        raise HTTPException(status_code=500, detail=str(e))
```

---

## OBSERVER ANALYSIS RECOMMENDATIONS

The Observer should analyze the following patterns:

### 1. Upload Quality Metrics
- **Confidence Score Distribution:** Track `TRANSCRIPT_PROCESSED.confidence` over time
- **Category Distribution:** Count by `recordType` (operative_note, imaging, etc.)
- **Data Completeness:** Analyze `DATA_QUALITY_ASSESSMENT.fieldsPresent` to identify commonly missing fields
- **PVI Extraction Rate:** Track `hasPviFields` for operative notes

### 2. Query Patterns
- **Search vs List Ratio:** From `PATIENTS_QUERIED.queryType`
- **Result Set Sizes:** Track `resultCount` distributions
- **AI Query Lengths:** Analyze `QUERY_SUBMITTED.queryLength`
- **AI Response Sizes:** Track `RESPONSE_GENERATED.responseLength`
- **Data Source Coverage:** Monitor `dataSources.transcripts` and `dataSources.procedures`

### 3. Athena Integration Health
- **Event Type Distribution:** Count by `ATHENA_EVENT_RECEIVED.eventType`
- **Duplicate Rate:** Ratio of `status: "duplicate"` vs `status: "success"`
- **Patient Linking Success:** Track `PATIENT_LINK_STATUS.linkedToPatient` rate
- **Orphaned Events:** Events where `linkedToPatient: false`

### 4. Error Patterns
- **Failure Rate by Stage:** Track `success: false` events per stage
- **Error Categories:** Classify errors from `TRANSCRIPT_FAILED.error`
- **Correlation Tracking:** Follow correlation IDs to identify partial failures

---

## TESTING THE INTEGRATION

### 1. Verify Telemetry is Flowing

```bash
# Check Observer stats
curl http://localhost:54112/api/events/stats

# Expected response includes:
{
  "sources": {
    "plaud-ai-uploader": {
      "total": 150,
      "last24h": 45,
      "byStage": {
        "upload": 50,
        "query": 40,
        "ai-query": 30,
        "ingest": 30
      }
    }
  }
}
```

### 2. Test Upload Telemetry

```bash
curl -X POST http://localhost:8001/upload \
  -H "Content-Type: application/json" \
  -d '{
    "first_name": "John",
    "last_name": "Doe",
    "dob": "1958-03-15",
    "athena_mrn": "12345678",
    "raw_transcript": "Patient presents with claudication...",
    "record_category": "office_visit"
  }'

# Check Observer received events
curl http://localhost:54112/api/events?source=plaud-ai-uploader&limit=5
```

### 3. Test Clinical Query Telemetry

```bash
curl -X POST http://localhost:8001/clinical/query \
  -H "Content-Type: application/json" \
  -d '{"query": "What medications is Mr. Doe on?"}'

# Verify ai-query events in Observer
curl http://localhost:54112/api/events?source=plaud-ai-uploader&stage=ai-query
```

---

## SECURITY NOTES

- **No PHI in Telemetry:** Patient names, MRNs, and clinical content are NEVER sent
- **Only Metadata:** Counts, types, IDs, lengths, and boolean flags
- **Fire-and-Forget:** Telemetry failures never impact application flow
- **Short Timeouts:** 2-second max to avoid blocking
- **Graceful Degradation:** If Observer is down, application continues normally

---

## DEPENDENCIES

```
# requirements.txt
httpx==0.28.1  # Async HTTP client for telemetry
```

---

## CONTACT

| Role | System |
|------|--------|
| Source Application | Plaud AI Uploader (port 8001) |
| Telemetry Target | Medical Mirror Observer (port 54112) |
| Database | PostgreSQL surgical_command_center (port 5432) |
