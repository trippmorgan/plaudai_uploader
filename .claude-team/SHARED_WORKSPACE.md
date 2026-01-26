# PlaudAI SHARED_WORKSPACE

**Instance**: PlaudAI Claude (Server1)
**Location**: 100.75.237.36:8001
**Last Updated**: 2026-01-25 23:15 EST
**Version**: 1.0.0 - FULLY INTEGRATED

---

## Current Status: ORCC Integration COMPLETE

PlaudAI is the **unified backend** for the Albany Vascular surgical platform.
ORCC frontend is fully integrated with bidirectional data flow.

### Integration Status

| Component | Status | Notes |
|-----------|--------|-------|
| Patients API | ✅ DONE | Full CRUD |
| Procedures API | ✅ DONE | Full CRUD + DELETE endpoint |
| Planning API | ✅ DONE | GET /api/planning/{mrn} |
| Tasks API | ✅ DONE | Full CRUD at /api/tasks |
| Shadow Coder API | ✅ DONE | Claude AI extraction working |
| WebSocket Server | ✅ DONE | /ws with subscriptions |
| ORCC Frontend | ✅ INTEGRATED | saveOrUpdateProcedure() working |
| Barriers PATCH | ✅ FIXED | JSONB array updates |
| DELETE endpoint | ✅ NEW | Clean up duplicates |

---

## Working API Endpoints

### Patients & Procedures (ORCC)
```
GET    /health                      - Health check
GET    /api/patients                - List patients
GET    /api/patients/{mrn}          - Get patient by MRN
POST   /api/patients                - Create patient
GET    /api/procedures              - List procedures (38 total)
GET    /api/procedures/{id}         - Get procedure
POST   /api/procedures              - Create procedure with planning data
PATCH  /api/procedures/{id}         - Update procedure
DELETE /api/procedures/{id}         - Delete procedure (NEW)
GET    /api/planning/{mrn}          - Get planning data for workspace
GET    /api/orcc/status             - ORCC integration status
```

### Tasks API
```
GET    /api/tasks                   - List tasks (with filters)
POST   /api/tasks                   - Create task
GET    /api/tasks/{id}              - Get task by ID
PATCH  /api/tasks/{id}              - Update task
DELETE /api/tasks/{id}              - Delete task
POST   /api/tasks/{id}/complete     - Mark complete
GET    /api/tasks/patient/{mrn}     - Tasks by patient
GET    /api/tasks/procedure/{id}    - Tasks by procedure
GET    /api/tasks/stats/summary     - Task statistics
```

### Shadow Coder API (Claude AI)
```
POST   /api/shadow-coder/analyze          - Analyze transcript (WORKING)
POST   /api/shadow-coder/intake/plaud     - Plaud transcript intake
POST   /api/shadow-coder/intake/zapier    - Zapier webhook
GET    /api/shadow-coder/intake/status/{id} - Voice note status
GET    /api/shadow-coder/intake/recent    - Recent voice notes (6 notes)
GET    /api/shadow-coder/facts/{case_id}  - Get case facts
POST   /api/shadow-coder/facts/{case_id}  - Add fact
GET    /api/shadow-coder/prompts/{case_id} - Get prompts
POST   /api/shadow-coder/prompts/{id}/action - Execute prompt
```

### WebSocket
```
WS     /ws?client_id={id}           - Real-time connection
GET    /ws/stats                    - Connection statistics
```

### AI Processing (Gemini)
```
POST   /api/parse                   - Parse transcript
POST   /api/synopsis                - Generate synopsis
POST   /api/extract                 - Extract PVI fields
```

---

## Database

```
Host: localhost:5432
Database: surgical_command_center
User: scc_user
```

### Current Record Counts
| Table | Records | Purpose |
|-------|---------|---------|
| scc_patients | 17 | Patient profiles |
| procedures | 38 | Surgical procedures |
| tasks | 2+ | Task management |
| scc_voice_notes | 6 | Shadow coder transcripts |

### Surgical Status Breakdown
| Status | Count |
|--------|-------|
| Workup | 24 |
| Near Ready | 5 |
| Ready | 3 |
| Hold | 2 |
| Scheduled | 2 |

---

## AI Services

| Service | Provider | Status |
|---------|----------|--------|
| Synopsis Generation | Google Gemini | ✅ Working |
| Fact Extraction | Anthropic Claude | ✅ Working |
| Transcript Parsing | Local (regex) | ✅ Working |

---

## ORCC Frontend Integration (2026-01-25)

The ORCC frontend now has full bidirectional integration:

### Frontend Changes (ORCommandCenter repo)
- `js/api-client.js` - Added `saveOrUpdateProcedure()` and `getLatestProcedureByMRN()`
- `planning-endovascular.html` - Pre-populates modal with existing data
- `surgical-command-center-workspace.html` - Added LEFT-side SVG vessel paths

### Data Flow
```
ORCC Frontend ──────────────────► PlaudAI API
     │                                 │
     │  GET /api/planning/{mrn}        │
     │  POST/PATCH /api/procedures     │
     │  DELETE /api/procedures/{id}    │
     │                                 │
     ◄────────────────────────────────┘
           JSON responses
```

---

## Known Issues Resolved

| Issue | Resolution | Date |
|-------|------------|------|
| Duplicate procedures | DELETE endpoint added | 2026-01-25 |
| .env not loading | Added explicit dotenv in main.py | 2026-01-25 |
| Pydantic model_used warning | Added protected_namespaces config | 2026-01-25 |
| PATCH barriers 500 | Was working - frontend testing issue | 2026-01-25 |
| Shadow Coder analyze | ANTHROPIC_API_KEY now configured | 2026-01-25 |

---

## Remaining Duplicates (For Cleanup)

| Patient | MRN | Count |
|---------|-----|-------|
| Charles Daniels | 18890211 | 12 |
| William Thompson | 123456789 | 8 |
| Janice Pringle | 35072287 | 5 |
| Test User | TESTXYZ999 | 3 |
| James Brown | 444555666 | 2 |
| Patricia Davis | 111222333 | 2 |

Use `DELETE /api/procedures/{id}` to clean up.

---

## Recent Changes (2026-01-25)

- Added DELETE /api/procedures/{id} endpoint
- Fixed .env loading in main.py (explicit dotenv path)
- Fixed Pydantic protected_namespaces warning
- Verified Claude AI fact extraction working
- Verified all PATCH operations working
- Team hub communication working

## Recent Changes (2026-01-22)

- Fixed barriers SQL bug (text[] → jsonb conversion)
- POST /api/procedures saves full planning data
- GET /api/planning/{mrn} returns planning data
- Charles Daniels (MRN: 18890211) has verified planning data

## Recent Changes (2026-01-21)

- Fixed SQL parameter binding (`CAST(:param AS type)`)
- Created Tasks API with full CRUD
- Migrated Shadow Coder from SCC Node.js
- Added WebSocket server with subscriptions

---

## For Other Claude Instances

**API Base URL**: `http://100.75.237.36:8001`
**Team Hub**: `ws://100.104.39.64:4847`

```bash
# Health check
curl http://100.75.237.36:8001/health

# Create patient
curl -X POST http://100.75.237.36:8001/api/patients \
  -H "Content-Type: application/json" \
  -d '{"mrn": "12345", "first_name": "John", "last_name": "Doe", "date_of_birth": "1960-01-01", "gender": "male"}'

# Delete duplicate procedure
curl -X DELETE http://100.75.237.36:8001/api/procedures/{uuid}
```

---

*This workspace is shared via claude-team hub*
