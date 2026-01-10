# Athena-Scraper Database Integration Specification
## Connecting to Albany Vascular AI / Plaud AI Shared Database

---

## QUICK REFERENCE

| Property | Value |
|----------|-------|
| **API URL** | `http://100.75.237.36:8001/ingest/athena` |
| **Method** | `POST` |
| **Tailscale IP** | `100.75.237.36` |
| **Hostname** | `server1-70tr000lux` |
| **Patient Key** | `athena_patient_id` (matches `patients.athena_mrn`) |
| **Database** | PostgreSQL `surgical_command_center` |

---

## 1. NETWORK TOPOLOGY

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           NETWORK ARCHITECTURE                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                    TAILSCALE MESH NETWORK                            │   │
│  │                    Network: pretoriafieldscollective                  │   │
│  │                                                                       │   │
│  │  ┌─────────────────┐     ┌─────────────────┐     ┌───────────────┐   │   │
│  │  │ Athena-Scraper  │     │  Plaud Backend  │     │  PostgreSQL   │   │   │
│  │  │ (Your Machine)  │────►│  FastAPI :8001  │────►│  :5432        │   │   │
│  │  │                 │     │ 100.75.237.36   │     │ localhost     │   │   │
│  │  └─────────────────┘     └─────────────────┘     └───────────────┘   │   │
│  │                                                                       │   │
│  │  Tailscale Devices:                                                   │   │
│  │  • server1-70tr000lux   100.75.237.36  ← DATABASE SERVER             │   │
│  │  • joevoldemort-romed8  100.101.184.20                                │   │
│  │  • tripp-precision-t36  100.104.39.64                                 │   │
│  │  • tripp-super-server   100.80.111.84                                 │   │
│  │  • tripps-macbook-pro   100.113.243.36                                │   │
│  │                                                                       │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. TAILSCALE SETUP GUIDE

### Step 1: Install Tailscale

```bash
# Linux (Ubuntu/Debian)
curl -fsSL https://tailscale.com/install.sh | sh

# macOS
brew install tailscale

# Windows
# Download from https://tailscale.com/download/windows
```

### Step 2: Authenticate & Join Network

```bash
sudo tailscale up

# A URL will appear - open it in your browser
# Log in with the pretoriafieldscollective account credentials
# Once authenticated, you're on the mesh network
```

### Step 3: Verify Connection

```bash
# Check Tailscale status
tailscale status
# Should show: server1-70tr000lux   100.75.237.36   ...

# Ping the database server
ping 100.75.237.36
# Should respond with ~1-5ms latency
```

### Step 4: Test API Connectivity

```bash
# Health check - main API
curl http://100.75.237.36:8001/health
# Expected: {"status": "healthy", "database": "healthy", ...}

# Health check - ingestion endpoint
curl http://100.75.237.36:8001/ingest/health
# Expected: {"status": "healthy", "service": "scc-ingest"}

# Get current stats
curl http://100.75.237.36:8001/ingest/stats
# Returns event counts by type
```

---

## 3. RECOMMENDED: API INTEGRATION

### Why Use the API (Not Direct PostgreSQL)

| Benefit | Description |
|---------|-------------|
| **Auto Patient Linking** | API automatically matches `athena_patient_id` to existing patients |
| **Deduplication** | SHA256 idempotency keys prevent duplicate events |
| **HIPAA Audit Trail** | All ingestions logged to `integration_audit_log` |
| **Telemetry** | Events sent to Medical Mirror Observer for AI analysis |
| **Validation** | Pydantic schemas validate input structure |
| **Security** | No database credentials needed on Athena-Scraper |

### API Endpoint

```
POST http://100.75.237.36:8001/ingest/athena
Content-Type: application/json
```

### Request Schema

```json
{
  "athena_patient_id": "string (required) - Patient MRN from Athena",
  "event_type": "string (required) - medication|problem|vital|lab|allergy|encounter",
  "event_subtype": "string (optional) - active|historical|search|etc",
  "payload": "object (required) - Complete raw Athena API response",
  "captured_at": "string (required) - ISO timestamp (2025-01-05T10:30:00Z)",
  "source_endpoint": "string (optional) - The intercepted Athena API endpoint",
  "confidence": "float (optional, 0.0-1.0) - Classification confidence",
  "indexer_version": "string (optional, default='2.0.0')"
}
```

### Response Schema

```json
{
  "status": "success | duplicate | error",
  "event_id": "UUID string",
  "message": "Human-readable status message"
}
```

### JavaScript/TypeScript Implementation (Chrome Extension)

```javascript
// Configuration
const PLAUD_API = 'http://100.75.237.36:8001';

/**
 * Send intercepted Athena data to Plaud AI backend
 */
async function sendToPlaudBackend(eventData) {
  try {
    const response = await fetch(`${PLAUD_API}/ingest/athena`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        athena_patient_id: eventData.patientMrn,
        event_type: eventData.type,        // medication, problem, vital, etc.
        event_subtype: eventData.subtype,  // active, historical, etc.
        payload: eventData.rawPayload,     // Complete Athena response
        captured_at: new Date().toISOString(),
        source_endpoint: eventData.interceptedUrl,
        confidence: eventData.confidence || 0.9,
        indexer_version: '2.0.0'
      })
    });

    const result = await response.json();

    if (result.status === 'success') {
      console.log(`✅ Event stored: ${result.event_id}`);
    } else if (result.status === 'duplicate') {
      console.log(`⏭️ Duplicate skipped: ${result.event_id}`);
    } else {
      console.error(`❌ Error: ${result.message}`);
    }

    return result;
  } catch (error) {
    console.error('Failed to send to Plaud backend:', error);
    return { status: 'error', message: error.message };
  }
}

// Example usage in content script
chrome.webRequest.onCompleted.addListener(
  async (details) => {
    if (details.url.includes('/api/') && details.url.includes('athena')) {
      // Parse the response and classify it
      const eventData = await parseAthenaResponse(details);
      if (eventData) {
        await sendToPlaudBackend(eventData);
      }
    }
  },
  { urls: ['*://*.athenahealth.com/*'] }
);
```

---

## 4. PATIENT LINKING STRATEGY

### The Universal Key: `athena_mrn`

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         PATIENT LINKING FLOW                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ATHENA-SCRAPER captures:                                                    │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │ POST /ingest/athena                                                    │  │
│  │ {                                                                      │  │
│  │   "athena_patient_id": "12345678",  ◄── MRN from Athena               │  │
│  │   "event_type": "medication",                                          │  │
│  │   "payload": { ... }                                                   │  │
│  │ }                                                                      │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                    │                                         │
│                                    ▼                                         │
│  PLAUD BACKEND processes:                                                    │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │ 1. Store in clinical_events.athena_patient_id = "12345678"             │  │
│  │                                                                        │  │
│  │ 2. Query: SELECT id FROM patients WHERE athena_mrn = "12345678"       │  │
│  │                                                                        │  │
│  │ 3. If found: Set clinical_events.patient_id = patients.id             │  │
│  │    If not: patient_id = NULL (event still stored, linkable later)     │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                    │                                         │
│                                    ▼                                         │
│  RESULT: Unified patient record                                              │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │ Patient ID: 42                                                         │  │
│  │ MRN: 12345678                                                          │  │
│  │                                                                        │  │
│  │ ├── voice_transcripts (from PlaudAI)                                   │  │
│  │ │   └── Operative note, Office visit, etc.                             │  │
│  │ │                                                                      │  │
│  │ ├── clinical_events (from Athena-Scraper)                              │  │
│  │ │   └── Medications, Problems, Vitals, Labs                            │  │
│  │ │                                                                      │  │
│  │ └── pvi_procedures (extracted from operative notes)                    │  │
│  │     └── SVS Registry data                                              │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Query All Patient Data

```sql
-- Get everything for a patient by MRN
SELECT
  p.id, p.first_name, p.last_name, p.athena_mrn,
  COUNT(DISTINCT vt.id) as transcript_count,
  COUNT(DISTINCT ce.id) as athena_event_count,
  COUNT(DISTINCT pvi.id) as procedure_count
FROM patients p
LEFT JOIN voice_transcripts vt ON vt.patient_id = p.id
LEFT JOIN clinical_events ce ON ce.patient_id = p.id
LEFT JOIN pvi_procedures pvi ON pvi.patient_id = p.id
WHERE p.athena_mrn = '12345678'
GROUP BY p.id;
```

---

## 5. COMPLETE DATABASE SCHEMA

### Table: `patients` (Core Entity)

| Column | Type | Constraints | Purpose |
|--------|------|-------------|---------|
| id | Integer | PRIMARY KEY | Unique patient ID |
| first_name | String(100) | | First name |
| last_name | String(100) | | Last name |
| dob | Date | | Date of birth |
| **athena_mrn** | String(20) | UNIQUE, NOT NULL, INDEX | **External Athena MRN** |
| birth_sex | String(10) | | M/F/Other |
| race | String(50) | | Ethnicity |
| zip_code | String(10) | | ZIP code |
| created_at | DateTime | server_default=now() | Created timestamp |
| updated_at | DateTime | auto-update | Modified timestamp |

### Table: `clinical_events` (Athena Data - Append-Only)

| Column | Type | Constraints | Purpose |
|--------|------|-------------|---------|
| id | String(36) | PRIMARY KEY (UUID) | Event ID |
| patient_id | Integer | FK→patients.id, INDEX, nullable | Auto-linked patient |
| **athena_patient_id** | String(50) | INDEX | **MRN from Athena** |
| event_type | String(50) | INDEX | medication, problem, vital, lab, etc. |
| event_subtype | String(50) | nullable | active, historical, etc. |
| **raw_payload** | JSON | NOT NULL | **Complete unmodified Athena response** |
| source_endpoint | Text | nullable | Intercepted API endpoint |
| **idempotency_key** | String(128) | UNIQUE, INDEX | **SHA256 hash for deduplication** |
| captured_at | DateTime | INDEX | When captured from Athena |
| ingested_at | DateTime | default=now() | When stored in PostgreSQL |
| confidence | Float | default=0.0 | Classification confidence |
| indexer_version | String(20) | | Indexer version |

### Table: `voice_transcripts` (PlaudAI Data)

| Column | Type | Constraints | Purpose |
|--------|------|-------------|---------|
| id | Integer | PRIMARY KEY | Transcript ID |
| patient_id | Integer | FK→patients.id, INDEX | Patient reference |
| record_category | String(50) | INDEX | operative_note, imaging, lab_result, office_visit |
| raw_transcript | Text | NOT NULL | Raw voice-to-text |
| plaud_note | Text | | Formatted PlaudAI note |
| category_specific_data | JSON | | Parsed structured data |
| tags | JSON | | Auto-generated medical tags |
| confidence_score | Float | | AI parsing confidence |
| recording_date | DateTime | | When recorded |
| created_at | DateTime | | Created timestamp |

### Table: `pvi_procedures` (SVS Registry)

| Column | Type | Purpose |
|--------|------|---------|
| id | Integer | Procedure ID |
| patient_id | Integer | FK→patients.id |
| procedure_date | Date | Intervention date |
| surgeon_name | String(100) | Primary surgeon |
| indication | String(100) | Clinical indication |
| arteries_treated | JSON | List of vessels |
| treatment_success | Boolean | Technical success |
| complications | JSON | List of complications |
| ... | ... | 50+ registry fields |

### Table: `integration_audit_log` (HIPAA Compliance)

| Column | Type | Purpose |
|--------|------|---------|
| id | Integer | Log entry ID |
| action | String(50) | INGEST, PARSE, VIEW, EXPORT, ERROR |
| resource_type | String(50) | clinical_event, finding, etc. |
| resource_id | String(100) | ID of affected resource |
| details | JSON | Additional context |
| error_message | Text | Error details if applicable |
| timestamp | DateTime | Action timestamp |

---

## 6. EVENT TYPES

| event_type | Description | Example payload keys |
|------------|-------------|---------------------|
| `medication` | Active/historical medications | medication_name, dose, frequency, start_date |
| `problem` | Diagnoses and conditions | diagnosis, icd_code, onset_date, status |
| `vital` | Vital signs measurements | blood_pressure, heart_rate, temperature |
| `lab` | Laboratory results | test_name, value, unit, reference_range |
| `allergy` | Allergies and reactions | allergen, reaction_type, severity |
| `encounter` | Office visits/appointments | date, provider, reason, notes |

---

## 7. SSH ACCESS (For Debugging)

```bash
# Connect via Tailscale
ssh server1@100.75.237.36

# Or using Tailscale hostname
ssh server1@server1-70tr000lux

# SSH tunnel for direct database access (debugging only)
ssh -L 5433:localhost:5432 server1@100.75.237.36
# Then connect to localhost:5433 with PostgreSQL client
```

### Database Connection (If Direct Access Needed)

```bash
# Connection parameters (credentials from .env)
Host: localhost (via SSH tunnel) or 100.75.237.36
Port: 5432
Database: surgical_command_center
User: scc_user
Password: <from DB_PASSWORD environment variable>
```

---

## 8. DATA FLOW ARCHITECTURE

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         UNIFIED DATA ARCHITECTURE                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  DATA SOURCE 1: Athena EMR                                                   │
│  ┌─────────────────┐      ┌─────────────────┐      ┌───────────────────┐    │
│  │  Athena Browser │ ───► │ Athena-Scraper  │ ───► │ clinical_events   │    │
│  │  (AthenaHealth) │      │ (Chrome Ext)    │      │ (append-only)     │    │
│  └─────────────────┘      └─────────────────┘      └─────────┬─────────┘    │
│                                                              │              │
│                                                              ▼              │
│  DATA SOURCE 2: PlaudAI                          ┌───────────────────┐      │
│  ┌─────────────────┐      ┌─────────────────┐    │                   │      │
│  │  PlaudAI App    │ ───► │  /upload        │───►│     patients      │      │
│  │  (Voice Notes)  │      │  FastAPI        │    │   (athena_mrn)    │      │
│  └─────────────────┘      └─────────────────┘    │                   │      │
│                                                   └───────────────────┘      │
│                                                              │              │
│                                                              ▼              │
│  UNIFIED PATIENT VIEW:                           ┌───────────────────┐      │
│  ┌───────────────────────────────────────────────┤  PostgreSQL DB    │      │
│  │                                               │  surgical_command │      │
│  │  GET /patients/{id}/emr-chart                 │  _center          │      │
│  │  GET /clinical/patient-summary/{mrn}          │                   │      │
│  │  POST /clinical/query                         └───────────────────┘      │
│  │                                                                          │
│  │  Returns: Transcripts + Athena Events + Procedures + AI Synopsis         │
│  │                                                                          │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
│  TELEMETRY:                                                                  │
│  ┌─────────────────────────────────────────────────────────────────────────┐│
│  │  All operations ──► Medical Mirror Observer (localhost:54112)           ││
│  │  AI-powered analysis and recommendations                                ││
│  └─────────────────────────────────────────────────────────────────────────┘│
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 9. DEDUPLICATION & IDEMPOTENCY

### How It Works

```javascript
// When Athena-Scraper sends the same data twice:

// Request 1:
POST /ingest/athena
{ athena_patient_id: "123", event_type: "medication", payload: {...} }
// Response: { status: "success", event_id: "abc-123" }

// Request 2 (identical):
POST /ingest/athena
{ athena_patient_id: "123", event_type: "medication", payload: {...} }
// Response: { status: "duplicate", event_id: "abc-123", message: "Event already ingested" }
```

### Algorithm

```python
# Server-side deduplication
idempotency_key = SHA256(
    f"{athena_patient_id}:{event_type}:{json.dumps(payload, sort_keys=True)}"
)[:64]

# If this key exists → return "duplicate"
# If new → store event
```

---

## 10. SECURITY CONSIDERATIONS

| Aspect | Implementation |
|--------|----------------|
| **Network** | Tailscale mesh provides end-to-end encryption |
| **Credentials** | Database password in `.env` file, never in code |
| **Audit Trail** | All ingestions logged to `integration_audit_log` |
| **Data Integrity** | Append-only pattern - events never modified/deleted |
| **PHI Protection** | No PHI in telemetry, only operational metadata |
| **Deduplication** | SHA256 hashes prevent duplicate storage |

---

## 11. BIDIRECTIONAL INTEGRATION (Phase 3)

### NEW: Fetch Stored Clinical Data

When a user opens a patient in Athena, the scraper can now **fetch stored data** from Plaud before scraping new data. This provides:
- **Instant display**: Show stored data immediately while scraping new data
- **Persistent access**: Data available even if Athena session expired
- **Longitudinal view**: See historical data accumulated over multiple visits

### Endpoint: GET /ingest/clinical/{athena_mrn}

```bash
# Fetch all stored clinical data for a patient
curl http://100.75.237.36:8001/ingest/clinical/12345678
```

### Response Schema

```json
{
  "status": "found",
  "athena_mrn": "12345678",
  "patient_id": 42,
  "last_updated": "2026-01-05T12:30:00Z",
  "clinical_data": {
    "demographics": {
      "first_name": "John",
      "last_name": "Doe",
      "date_of_birth": "1955-03-15",
      "gender": "male",
      "race": "white",
      "zip_code": "31721"
    },
    "medications": [
      {
        "event_id": "uuid-here",
        "name": "Aspirin 81mg",
        "sig": "Take 1 tablet daily",
        "start_date": "2024-01-15",
        "source": "athena",
        "captured_at": "2026-01-05T12:00:00Z",
        "status": "active"
      }
    ],
    "problems": [
      {
        "event_id": "uuid-here",
        "name": "Peripheral Vascular Disease",
        "icd10": "I73.9",
        "status": "active",
        "onset_date": "2023-06-01",
        "source": "athena",
        "captured_at": "2026-01-05T12:00:00Z"
      }
    ],
    "allergies": [
      {
        "event_id": "uuid-here",
        "allergen": "Penicillin",
        "reaction_type": "Rash",
        "severity": "Moderate",
        "source": "athena",
        "captured_at": "2026-01-05T12:00:00Z"
      }
    ],
    "labs": [
      {
        "event_id": "uuid-here",
        "name": "Creatinine",
        "value": "1.2",
        "unit": "mg/dL",
        "reference_range": "0.7-1.3",
        "flag": "normal",
        "date": "2026-01-03",
        "source": "athena",
        "captured_at": "2026-01-03T12:00:00Z"
      }
    ],
    "vitals": {
      "event_id": "uuid-here",
      "blood_pressure": "128/78",
      "heart_rate": 72,
      "temperature": null,
      "respiratory_rate": null,
      "oxygen_saturation": null,
      "weight": null,
      "height": null,
      "bmi": null,
      "recorded_at": "2026-01-05T10:00:00Z",
      "source": "athena"
    },
    "encounters": [...],
    "documents": [...],
    "other": [...]
  },
  "event_count": 47,
  "sources": ["athena", "plaud_transcript"]
}
```

### Not Found Response

```json
{
  "status": "not_found",
  "athena_mrn": "12345678",
  "patient_id": null,
  "message": "No patient found with MRN 12345678"
}
```

### JavaScript Implementation

```javascript
// backend/plaud_client.js (or equivalent)

const PLAUD_API = 'http://100.75.237.36:8001';

/**
 * Fetch stored clinical data when patient context changes.
 * Call this when user opens a patient chart in Athena.
 */
async function fetchStoredPatientData(patientMrn) {
  try {
    const startTime = Date.now();

    const response = await fetch(`${PLAUD_API}/ingest/clinical/${patientMrn}`);
    const data = await response.json();

    const duration = Date.now() - startTime;

    if (data.status === 'found') {
      console.log(`✅ Loaded ${data.event_count} stored events for ${patientMrn} in ${duration}ms`);

      // Emit telemetry to Observer
      await emitTelemetry('plaud-fetch', 'fetch-patient', true, {
        patientId: patientMrn,
        eventCount: data.event_count,
        lastUpdated: data.last_updated,
        httpStatus: 200,
        duration_ms: duration
      });

      return data;
    } else {
      console.log(`ℹ️ No stored data for ${patientMrn}`);

      await emitTelemetry('plaud-fetch', 'fetch-not-found', false, {
        patientId: patientMrn,
        httpStatus: 200,
        duration_ms: duration
      });

      return null;
    }
  } catch (error) {
    console.error(`❌ Failed to fetch stored data: ${error.message}`);

    await emitTelemetry('plaud-fetch', 'fetch-failed', false, {
      patientId: patientMrn,
      error: error.message
    });

    return null;
  }
}

/**
 * Integration flow when patient context changes.
 */
async function onPatientContextChange(patientMrn) {
  // 1. Immediately fetch stored data from Plaud
  const storedData = await fetchStoredPatientData(patientMrn);

  if (storedData) {
    // 2. Display stored data in WebUI immediately
    updateWebUI(storedData.clinical_data);
  }

  // 3. Continue scraping new data from Athena (existing flow)
  // New data will be exported to Plaud via POST /ingest/athena
}
```

### Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           BIDIRECTIONAL DATA FLOW                                │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│   USER OPENS PATIENT IN ATHENA                                                   │
│   ─────────────────────────────                                                  │
│                                                                                  │
│   1. Patient context changes (MRN detected)                                      │
│      │                                                                           │
│      ▼                                                                           │
│   2. GET /ingest/clinical/{mrn} ──────────────────────────────────────┐          │
│      │                                           Plaud Backend         │          │
│      │                                           (ThinkServer:8001)    │          │
│      ▼                                                                 │          │
│   3. Receive stored clinical data                                      │          │
│      │                                                                 │          │
│      ▼                                                                 │          │
│   4. Display in WebUI IMMEDIATELY ◄────────────────────────────────────┘          │
│      │                                                                           │
│      │  (Meanwhile, continue scraping new data from Athena...)                   │
│      ▼                                                                           │
│   5. Intercept new Athena API responses                                          │
│      │                                                                           │
│      ▼                                                                           │
│   6. POST /ingest/athena ─────────────────────────────────────────────┐          │
│      │                                           Plaud Backend         │          │
│      ▼                                                                 │          │
│   7. Update WebUI with new data ◄──────────────────────────────────────┘          │
│                                                                                  │
│   RESULT: User sees stored data instantly, new data streams in                   │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## 12. TESTING CHECKLIST

```bash
# 1. Verify Tailscale connection
tailscale status | grep server1

# 2. Test API health
curl http://100.75.237.36:8001/health

# 3. Test ingestion endpoint health
curl http://100.75.237.36:8001/ingest/health

# 4. Test clinical fetch endpoint (NEW - Phase 3)
curl http://100.75.237.36:8001/ingest/clinical/18889107

# 5. Send test event
curl -X POST http://100.75.237.36:8001/ingest/athena \
  -H "Content-Type: application/json" \
  -d '{
    "athena_patient_id": "TEST123",
    "event_type": "medication",
    "payload": {"test": true, "medication": "Aspirin 81mg"},
    "captured_at": "2026-01-06T12:00:00Z"
  }'

# 6. Verify event stored
curl http://100.75.237.36:8001/ingest/events/TEST123

# 7. Check stats
curl http://100.75.237.36:8001/ingest/stats
```

---

## 13. TROUBLESHOOTING

| Issue | Solution |
|-------|----------|
| Can't reach `100.75.237.36` | Run `tailscale status` - ensure connected to network |
| `Connection refused` on :8001 | Server may be down - SSH and check: `sudo systemctl status plaud-api` |
| `duplicate` status always | Expected for same data - change payload to test new events |
| `patient_id: null` in events | Patient doesn't exist yet - create via `/upload` first or wait for auto-link |
| Slow responses | Normal for first request (cold start) - subsequent requests faster |

---

## 14. CONTACT & SUPPORT

| Resource | Location |
|----------|----------|
| Database Server | `server1@100.75.237.36` |
| API Docs | `http://100.75.237.36:8001/docs` |
| API ReDoc | `http://100.75.237.36:8001/redoc` |
| Telemetry Spec | `OBSERVER_INTEGRATION_SPEC.md` |
| Database Schema | `backend/models.py`, `backend/models_athena.py` |
