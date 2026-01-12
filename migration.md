# SCC + PlaudAI/VAI Integration Migration Plan

## Goal
1. **Remove Dragon dictation** from SCC (replaced by Plaud)
2. **Integrate PlaudAI/VAI** tabs into SCC legacy frontend as unified UI

---

## Architecture Overview

### Current State (TWO separate apps):
```
┌─────────────────────────────────────────────────────────────────────────┐
│  BROWSER TAB 1: SCC                    BROWSER TAB 2: VAI              │
│  http://localhost:3001                 http://100.75.237.36:8001       │
│  ┌─────────────────────────┐           ┌─────────────────────────┐     │
│  │ • Patient Selection     │           │ • Upload                │     │
│  │ • Procedure Docs        │           │ • Patients              │     │
│  │ • Vessel Cards          │           │ • EMR Chart             │     │
│  │ • Shadow Coder Prompts  │           │ • Clinical Query        │     │
│  │ • UltraLinq Images      │           │ • Synopsis              │     │
│  └─────────────────────────┘           └─────────────────────────┘     │
└─────────────────────────────────────────────────────────────────────────┘
        ↑ Switch between tabs manually - TWO different URLs
```

### After Integration (ONE unified app):
```
┌─────────────────────────────────────────────────────────────────────────┐
│  BROWSER: Single URL - http://localhost:3001                            │
│  ┌─────────────────────────────────────────────────────────────────────┐│
│  │  [ Procedures ] [ Upload ] [ EMR Chart ] [ Query ] [ Synopsis ]     ││
│  │  ─────────────────────────────────────────────────────────────────  ││
│  │                                                                      ││
│  │  ┌─────────────────────────────────────────────────────────────┐   ││
│  │  │                                                              │   ││
│  │  │   Content changes based on which tab is selected            │   ││
│  │  │   • Procedures tab → SCC procedure documentation            │   ││
│  │  │   • Upload tab → VAI voice transcript upload                │   ││
│  │  │   • EMR Chart tab → VAI patient records                     │   ││
│  │  │   • Query tab → VAI clinical query (AI)                     │   ││
│  │  │   • Synopsis tab → VAI AI summaries                         │   ││
│  │  │                                                              │   ││
│  │  └─────────────────────────────────────────────────────────────┘   ││
│  └─────────────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────────────┘
        ↑ ONE URL, tabs switch content - unified experience
```

---

## Data Flow

### Step-by-step when user clicks "EMR Chart" tab:

```
STEP 1: User clicks "EMR Chart" tab
        ↓
STEP 2: Browser JavaScript shows EMR Chart panel
        ↓
STEP 3: JavaScript calls SCC backend
        Browser sends: GET http://localhost:3001/api/vai/patients/12345/records
        ↓
STEP 4: SCC backend receives request
        Node.js sees /api/vai/* route
        ↓
STEP 5: SCC proxies to VAI
        SCC sends: GET http://100.75.237.36:8001/patients/12345/records
        ↓
STEP 6: VAI backend receives request
        FastAPI processes it
        Queries PostgreSQL database
        ↓
STEP 7: VAI returns data to SCC
        VAI sends JSON: { records: [...] }
        ↓
STEP 8: SCC forwards response to browser
        SCC passes through the JSON unchanged
        ↓
STEP 9: Browser receives data
        JavaScript renders the EMR chart
```

### Visual Data Flow:
```
┌──────────┐    GET /api/vai/patients    ┌──────────┐    GET /patients    ┌──────────┐
│          │ ─────────────────────────►  │          │ ─────────────────► │          │
│  BROWSER │                             │   SCC    │                     │   VAI    │
│          │ ◄─────────────────────────  │ Backend  │ ◄───────────────── │ Backend  │
└──────────┘    { patients: [...] }      └──────────┘   { patients: [...]}└──────────┘
     │                                        │                                │
     │                                        │                                │
     └────────────────────────────────────────┴────────────────────────────────┘
                                              │
                                              ▼
                                    ┌──────────────────┐
                                    │   PostgreSQL     │
                                    │   Database       │
                                    │                  │
                                    │  Both SCC & VAI  │
                                    │  read/write here │
                                    └──────────────────┘
```

---

## Server Utilization

### Current Machine Roles:

| Machine | IP Address | What Runs | Port |
|---------|------------|-----------|------|
| **Your Mac** (development) | localhost | SCC Backend (Node.js) | 3001 |
| **Voldemort** (Tailscale - HOME) | 100.101.184.20 | PostgreSQL Database | 5432 |
| **Server1** (Tailscale - WORK) | 100.75.237.36 | VAI Backend (Python) | 8001 |

### Server Architecture:
```
┌─────────────────────────────────────────────────────────────────────────┐
│  YOUR MAC (localhost)                                                    │
│  ┌─────────────────────────────────────────────────────────────────────┐│
│  │  SCC Backend (Node.js/Express) - Port 3001                          ││
│  │  • Serves the web UI (HTML/CSS/JS)                                  ││
│  │  • Handles /api/procedures, /api/patients                           ││
│  │  • Handles /api/vai/* (proxies to VAI)                              ││
│  │  • Runs Shadow Charge Coder                                         ││
│  │  • WebSocket for real-time updates                                  ││
│  └─────────────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                    ┌───────────────┴───────────────┐
                    │ Tailscale VPN Network         │
                    │ (secure tunnel)               │
                    └───────────────┬───────────────┘
                                    │
        ┌───────────────────────────┴───────────────────────────────────┐
        │                                                                │
        ▼                                                                ▼
┌───────────────────────────────┐          ┌───────────────────────────────┐
│  VOLDEMORT (100.101.184.20)   │          │  SERVER1 (100.75.237.36)      │
│  Location: HOME               │          │  Location: WORK               │
│  ┌─────────────────────────┐  │          │  ┌─────────────────────────┐  │
│  │  PostgreSQL - Port 5432 │  │          │  │  VAI Backend - Port 8001│  │
│  │  • patients table       │  │          │  │  • /upload endpoint     │  │
│  │  • procedures table     │  │          │  │  • /patients endpoint   │  │
│  │  • voice_transcripts    │  │          │  │  • /synopsis endpoint   │  │
│  │  • clinical_events      │  │          │  │  • /clinical/query      │  │
│  │  • scc_* tables         │  │          │  │  • Gemini AI calls      │  │
│  └─────────────────────────┘  │          │  └─────────────────────────┘  │
└───────────────────────────────┘          └───────────────────────────────┘
```

---

## Port Mapping

### Port Summary:

| Port | Location | Service | Protocol | Purpose |
|------|----------|---------|----------|---------|
| **3001** | localhost | SCC Backend | HTTP/WS | Main entry point for everything |
| **5432** | 100.101.184.20 | PostgreSQL | TCP | Database (both apps use this) |
| **8001** | 100.75.237.36 | VAI Backend | HTTP | Voice transcript processing |

### URL Mapping:
```
BROWSER CALLS                         ACTUALLY GOES TO
─────────────────────────────────────────────────────────────────────────

http://localhost:3001/                → SCC serves index.html
http://localhost:3001/api/patients    → SCC handles directly (Node.js)
http://localhost:3001/api/procedures  → SCC handles directly (Node.js)
http://localhost:3001/api/intake/plaud → SCC handles directly (Shadow Coder)

http://localhost:3001/api/vai/upload  → PROXY → http://100.75.237.36:8001/upload
http://localhost:3001/api/vai/patients → PROXY → http://100.75.237.36:8001/patients
http://localhost:3001/api/vai/synopsis → PROXY → http://100.75.237.36:8001/synopsis
http://localhost:3001/api/vai/clinical/query → PROXY → http://100.75.237.36:8001/clinical/query
```

---

## Phase 1: Remove Dragon Dictation

### Files to DELETE
| File | Reason |
|------|--------|
| `backend/routes/dragon.js` | Dragon API routes |
| `frontend_legacy/js/dragon-connection.js` | Dragon manager class |
| `dragon-integration/` (entire directory) | Python Dragon integration |

### Files to EDIT

#### `backend/server.js`
- Remove line: `const dragonRoutes = require("./routes/dragon");`
- Remove line: `app.use("/api/dragon", dragonRoutes);`
- Remove Dragon from health check response
- Remove Dragon from API discovery endpoint

#### `backend/services/dockerServicesClient.js`
- Remove `checkDragonHealth()` method
- Remove `processNoteWithDragon()` method
- Remove `transcribeAudioWithDragon()` method
- Remove Dragon URL config

#### `frontend_legacy/index.html`
- Remove Dragon icon CSS
- Remove Dragon UI elements in source selection panel
- Remove Dragon connection manager script tag
- Remove Dragon JavaScript initialization
- Remove Dragon status handlers
- Keep Plaud/Shadow Coder integration

#### `frontend_legacy/js/connection-config.js`
- Remove Dragon configuration section
- Remove `buildDragonUrl()` method

#### `frontend_legacy/js/websocket-client.js`
- Remove Dragon message handlers
- Remove `dragonManager` references

#### `frontend_legacy/patient-lookup.html`
- Remove Dragon AI references
- Remove Dragon health checks

#### `backend/websocket/server.js`
- Remove Dragon client type handling
- Remove Dragon message handlers

#### `backend/.env` and `.env.example`
- Remove `DRAGON_URL` variable
- Keep `GOOGLE_API_KEY` (may be used by other services)

---

## Phase 2: Integrate VAI into SCC

### 2.1 Add VAI Proxy Routes (backend)

Create new file: `backend/routes/vai.js`
```javascript
// Proxy routes to PlaudAI/VAI backend at 100.75.237.36:8001
// /api/vai/upload → VAI /upload
// /api/vai/patients → VAI /patients
// /api/vai/synopsis → VAI /synopsis
// /api/vai/clinical/query → VAI /clinical/query
// etc.
```

Mount in `server.js`:
```javascript
const vaiRoutes = require("./routes/vai");
app.use("/api/vai", vaiRoutes);
```

### 2.2 Add VAI Tabs to Frontend

Modify `frontend_legacy/index.html`:
- Add tab navigation: Procedures | Upload | EMR Chart | Clinical Query | Synopsis
- Create tab content containers
- Add JavaScript for tab switching
- Embed VAI UI components via iframes

### 2.3 Environment Configuration

Add to `backend/.env`:
```
VAI_URL=http://100.75.237.36:8001
```

---

## Phase 3: Update Documentation

- Update `backend/README.md` - remove Dragon, add VAI
- Update `docs/SURGICAL-COMMAND-CENTER-DATA-FLOW-SPEC.md` - update architecture

---

## Files Summary

### DELETE (3 items)
- `backend/routes/dragon.js`
- `frontend_legacy/js/dragon-connection.js`
- `dragon-integration/` (entire directory)

### EDIT (10 items)
- `backend/server.js`
- `backend/services/dockerServicesClient.js`
- `backend/websocket/server.js`
- `backend/.env`
- `frontend_legacy/index.html`
- `frontend_legacy/js/connection-config.js`
- `frontend_legacy/js/websocket-client.js`
- `frontend_legacy/patient-lookup.html`
- `backend/README.md`
- `docs/SURGICAL-COMMAND-CENTER-DATA-FLOW-SPEC.md`

### CREATE (1 item)
- `backend/routes/vai.js` - VAI proxy routes

---

## Verification

### After Dragon Removal
```bash
# Start server
cd backend && npm run dev

# Verify no Dragon routes
curl http://localhost:3001/api/dragon/health  # Should 404

# Verify health endpoint works without Dragon
curl http://localhost:3001/health
```

### After VAI Integration
```bash
# Test VAI proxy
curl http://localhost:3001/api/vai/patients

# Open browser
open http://localhost:3001

# Verify:
# - Tab navigation works
# - Upload tab shows VAI upload UI
# - EMR Chart tab shows patient records
# - Clinical Query works
# - Synopsis generation works
```

---

## Risks & Considerations

| Consideration | Impact | Mitigation |
|---------------|--------|------------|
| VAI must be running | Medium | VAI is always-on server; add health check in SCC |
| CORS | None | Using proxy approach avoids CORS entirely |
| Auth | None (future) | Design proxy to forward auth headers when needed |
| Shared DB | Positive | Already unified, no work needed |

---

## Future: Database Migration to Server1

### Current Setup
- PostgreSQL runs on **Voldemort** (100.101.184.20) at HOME
- VAI runs on **Server1** (100.75.237.36) at WORK

### Why Move DB to Server1?
- Server1 is at work = always on, reliable power/network
- Reduces latency for VAI (same machine as DB)
- Single point of infrastructure at work

### Migration Steps (Future Task)

1. **Install PostgreSQL on Server1**
   ```bash
   ssh server1
   sudo apt install postgresql postgresql-contrib
   ```

2. **Dump database from Voldemort**
   ```bash
   pg_dump -h 100.101.184.20 -U surgical_user -d surgical_command_center > scc_backup.sql
   ```

3. **Create database on Server1**
   ```bash
   sudo -u postgres createdb surgical_command_center
   sudo -u postgres createuser surgical_user
   ```

4. **Restore on Server1**
   ```bash
   psql -h localhost -U surgical_user -d surgical_command_center < scc_backup.sql
   ```

5. **Update connection strings**
   - SCC `.env`: `DB_HOST=100.75.237.36`
   - VAI config: `DB_HOST=localhost` (same machine)

6. **Test both apps**

7. **Decommission Voldemort PostgreSQL** (optional, keep as backup)

### Effort Estimate
- **Easy** - 1-2 hours
- PostgreSQL dump/restore is straightforward
- Just updating IP addresses in configs
- No schema changes needed

---

# Part 2: PlaudAI Stateless Refactor Analysis

## Executive Summary

The proposed migration from full-stack to stateless requires **significant refactoring**.
The current PlaudAI has deep database integration throughout its services.

| Component | Database Dependent | Migration Effort |
|-----------|-------------------|------------------|
| `parser.py` | **NO** | Ready as-is |
| `category_parser.py` | **NO** | Ready as-is |
| `gemini_synopsis.py` | **YES** | Major refactor |
| `uploader.py` | **YES** | Remove entirely |
| `clinical_query.py` | **YES** | Remove entirely |
| `pdf_generator.py` | Partial | Minor refactor |
| `telemetry.py` | **NO** | Keep or remove |
| `main.py` | **YES** | Replace entirely |

---

## DIFF: Current main.py vs Proposed Stateless

### Lines to REMOVE (Current main.py)

```python
# ===== DATABASE IMPORTS (REMOVE) =====
from .db import Base, engine, get_db, check_connection, init_db
from .models import Patient, VoiceTranscript, PVIProcedure

# ===== SCHEMA IMPORTS (REMOVE) =====
from .schemas import (
    PatientCreate, PatientResponse,
    TranscriptUpload, TranscriptResponse,
    PVIProcedureResponse,
    UploadResponse,
    BatchUploadRequest, BatchUploadResponse
)

# ===== DATABASE-DEPENDENT SERVICES (REMOVE) =====
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
from .services.clinical_query import process_clinical_query

# ===== ATHENA ROUTER (REMOVE) =====
from .routes.ingest import router as ingest_router
app.include_router(ingest_router)

# ===== STARTUP DB INIT (REMOVE) =====
@app.on_event("startup")
async def startup_event():
    if not check_connection():
        raise RuntimeError("Cannot connect to database")
    init_db()
```

### Endpoints to REMOVE (~25 endpoints becoming 4)

```
REMOVE:
├── GET  /patients                    # List/search patients
├── GET  /patients/{id}               # Get patient by ID
├── GET  /patients/{id}/transcripts   # Get patient transcripts
├── GET  /patients/{id}/procedures    # Get patient procedures
├── GET  /patients/{id}/records-by-category
├── GET  /patients/{id}/emr-chart
├── GET  /transcripts/{id}            # Get specific transcript
├── POST /upload                      # Main upload endpoint
├── POST /upload-medical-record       # Medical record upload
├── POST /upload-file                 # File upload
├── POST /synopsis/generate/{id}      # Generate AI synopsis
├── GET  /synopsis/patient/{id}       # Get patient synopses
├── GET  /synopsis/{id}               # Get specific synopsis
├── GET  /clinical/patient-summary/{mrn}
├── POST /clinical/query              # Natural language query
├── POST /generate-pdf/{id}           # Generate PDF for record
├── POST /generate-synopsis-pdf/{id}  # Generate synopsis PDF
├── GET  /stats                       # Database statistics
├── Static Files mounts               # Frontend & PDFs
└── /ingest/* routes                  # Athena integration

KEEP (New Stateless):
├── GET  /health                      # Health check (no DB)
├── POST /api/parse                   # Parse transcript → sections, tags, PVI
├── POST /api/synopsis                # Generate AI synopsis (Gemini only)
└── POST /api/extract                 # Extract SVS VQI registry fields
```

---

## Service Analysis

### 1. `services/parser.py` - READY FOR STATELESS

**Status: No changes needed**

```python
# Current imports (lines 159-162)
import re
from typing import Dict, List, Tuple
import logging

# NO database imports - pure functions!
```

**Functions available for stateless use:**
- `segment_summary(text)` → Dict of sections
- `generate_tags(text)` → List of tags
- `extract_pvi_fields(text)` → Dict of PVI registry fields
- `calculate_confidence_score(text, fields)` → float
- `process_transcript(text)` → (sections, tags, pvi_fields, confidence)

### 2. `services/category_parser.py` - READY FOR STATELESS

**Status: No changes needed**

Uses only:
- `google.generativeai` (Gemini API)
- Standard library (json, re, logging)

**Functions available:**
- `parse_by_category(text, category)` → Dict
- `generate_category_summary(data, category)` → str

### 3. `services/gemini_synopsis.py` - REQUIRES MAJOR REFACTOR

**Status: Database-dependent - needs rewrite**

**Current imports that must be REMOVED:**
```python
from sqlalchemy.orm import Session              # REMOVE
from ..models import Patient, VoiceTranscript,  # REMOVE
                     PVIProcedure, ClinicalSynopsis
```

**Functions requiring changes:**

| Function | Current Behavior | Stateless Version |
|----------|-----------------|-------------------|
| `gather_patient_data(db, patient_id)` | Queries DB | REMOVE - SCC sends data |
| `generate_clinical_synopsis(db, ...)` | Reads/writes DB, caches | Accept text, return synopsis |
| `get_latest_synopsis(db, ...)` | Queries DB | REMOVE - SCC handles caching |
| `get_all_synopses(db, ...)` | Queries DB | REMOVE |
| `get_patient_summary(db, mrn)` | Queries DB | REMOVE |
| `build_synopsis_prompt()` | No changes | KEEP |
| `parse_synopsis_sections()` | No changes | KEEP |
| `calculate_age()` | No changes | KEEP |

**Proposed stateless signature:**
```python
async def generate_synopsis_stateless(
    transcript_text: str,
    patient_context: Optional[Dict] = None,  # {name, age, mrn}
    style: str = "comprehensive"
) -> Dict:
    """
    Stateless synopsis generation - no database access.

    Args:
        transcript_text: Raw transcript or PlaudAI note
        patient_context: Optional patient demographics from SCC
        style: "comprehensive" | "visit_summary" | "problem_list"

    Returns:
        {
            "synopsis": str,
            "sections": Dict[str, str],  # Parsed sections
            "model_used": str,
            "tokens_used": int
        }
    """
```

### 4. `services/uploader.py` - REMOVE ENTIRELY

All functions are database-dependent. SCC will own:
- `upload_transcript()` → SCC handles storage
- `batch_upload_transcripts()` → SCC handles batch
- `get_patient_transcripts()` → SCC queries
- `get_patient_procedures()` → SCC queries
- `search_patients()` → SCC queries
- `get_or_create_patient()` → SCC handles
- `create_pvi_procedure()` → SCC handles

### 5. `services/clinical_query.py` - REMOVE ENTIRELY

Natural language queries require patient data from database.
SCC will reimplement this using its own data access.

---

## Environment Variables

### KEEP (Required for Stateless)
```bash
GOOGLE_API_KEY=xxx              # For Gemini AI
GEMINI_MODEL=gemini-2.0-flash-exp
API_PORT=8001                   # Service port
LOG_LEVEL=INFO
```

### REMOVE (No Longer Needed)
```bash
DB_HOST=xxx
DB_PORT=xxx
DB_NAME=xxx
DB_USER=xxx
DB_PASSWORD=xxx
DATABASE_URL=xxx
OBSERVER_URL=xxx                # Optional - telemetry
```

---

## Files to DELETE

```
backend/
├── db.py                   # Database connection
├── models.py               # SQLAlchemy models
├── schemas.py              # Pydantic schemas for DB
├── routes/
│   └── ingest.py           # Athena integration
└── services/
    ├── uploader.py         # All DB operations
    └── clinical_query.py   # DB-dependent queries

frontend/
└── index.html              # SCC will serve UI
```

## Files to KEEP (with modifications)

```
backend/
├── main.py                 # REPLACE with stateless version
├── config.py               # SIMPLIFY (remove DB config)
├── logging_config.py       # KEEP as-is
└── services/
    ├── parser.py           # KEEP as-is (already stateless)
    ├── category_parser.py  # KEEP as-is (already stateless)
    ├── gemini_synopsis.py  # REFACTOR (remove DB calls)
    └── pdf_generator.py    # OPTIONAL (or move to SCC)
```

---

## New Stateless main.py Template

```python
"""
PlaudAI Processor - Stateless AI Processing Service
Version 2.0.0 - Refactored for SCC Integration
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict
from datetime import datetime
import os

# Keep these - already stateless
from services.parser import (
    segment_summary,
    generate_tags,
    extract_pvi_fields,
    calculate_confidence_score,
    process_transcript
)
from services.category_parser import parse_by_category, generate_category_summary

app = FastAPI(
    title="PlaudAI Processor",
    description="Stateless AI processing service for SCC",
    version="2.0.0"
)

# Restricted CORS - only SCC
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3001",
        "http://100.75.237.36:3001"
    ],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# ===== REQUEST/RESPONSE MODELS =====

class ParseRequest(BaseModel):
    transcript_text: str
    include_pvi_fields: bool = True

class ParseResponse(BaseModel):
    sections: Dict[str, str]
    tags: List[str]
    pvi_fields: Optional[Dict] = None
    confidence_score: float
    processing_time_ms: int

class SynopsisRequest(BaseModel):
    transcript_text: str
    patient_context: Optional[Dict] = None
    style: str = "comprehensive"

class SynopsisResponse(BaseModel):
    synopsis: str
    sections: Dict[str, str]
    model_used: str
    tokens_used: int

# ===== ENDPOINTS =====

@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "service": "plaudai-processor",
        "version": "2.0.0",
        "gemini_configured": bool(os.getenv("GOOGLE_API_KEY"))
    }

@app.post("/api/parse", response_model=ParseResponse)
async def parse_transcript(request: ParseRequest):
    start = datetime.utcnow()
    sections, tags, pvi_fields, confidence = process_transcript(request.transcript_text)
    elapsed = int((datetime.utcnow() - start).total_seconds() * 1000)

    return ParseResponse(
        sections=sections,
        tags=tags,
        pvi_fields=pvi_fields if request.include_pvi_fields else None,
        confidence_score=confidence,
        processing_time_ms=elapsed
    )

@app.post("/api/synopsis", response_model=SynopsisResponse)
async def generate_synopsis(request: SynopsisRequest):
    from services.gemini_synopsis_stateless import generate_synopsis_stateless

    result = await generate_synopsis_stateless(
        transcript_text=request.transcript_text,
        patient_context=request.patient_context,
        style=request.style
    )
    return result

@app.post("/api/extract")
async def extract_pvi(request: ParseRequest):
    pvi_fields = extract_pvi_fields(request.transcript_text)
    return {"pvi_fields": pvi_fields}
```

---

## Migration Steps

### Step 1: Create Stateless gemini_synopsis.py
```bash
# Copy and refactor
cp backend/services/gemini_synopsis.py backend/services/gemini_synopsis_stateless.py
# Edit to remove all SQLAlchemy/DB code
```

### Step 2: Create New main.py
```bash
# Backup current
mv backend/main.py backend/main_legacy.py
# Create new stateless version
```

### Step 3: Update config.py
Remove DB config, keep only Gemini settings.

### Step 4: Delete Unused Files
```bash
rm backend/db.py
rm backend/models.py
rm backend/schemas.py
rm -rf backend/routes/
rm backend/services/uploader.py
rm backend/services/clinical_query.py
rm -rf frontend/
```

### Step 5: Update requirements.txt
```diff
- sqlalchemy
- psycopg2-binary
- alembic
+ fastapi
+ uvicorn
+ pydantic
+ google-generativeai
+ python-dotenv
```

---

## Questions for SCC Team

1. **Synopsis Caching**: Will SCC implement 24-hour synopsis caching? (Currently in PlaudAI DB)
2. **Patient Context**: What patient data will SCC send for synopsis generation?
3. **Error Handling**: Should PlaudAI return errors or empty results on failure?
4. **PDF Generation**: Move to SCC or keep in PlaudAI?
5. **Telemetry**: Should PlaudAI continue sending events to Observer?

---

## Testing Checklist

After migration, verify:

- [ ] `GET /health` returns healthy status
- [ ] `POST /api/parse` returns sections, tags, PVI fields
- [ ] `POST /api/synopsis` generates AI synopsis without DB
- [ ] `POST /api/extract` extracts VQI registry fields
- [ ] No database connections attempted on startup
- [ ] CORS blocks non-SCC origins
- [ ] Gemini API key works for synopsis generation
- [ ] Server starts without PostgreSQL running
