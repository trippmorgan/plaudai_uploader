# PlaudAI SHARED_WORKSPACE

**Instance**: PlaudAI Claude (Server1)
**Location**: 100.75.237.36:8001
**Last Updated**: 2026-01-21 15:55 EST

---

## Current Status: SCC Migration COMPLETE (Core Features)

PlaudAI is now the **unified backend** for the Albany Vascular surgical platform.

### Migration Status

| Component | Status | Notes |
|-----------|--------|-------|
| POST /api/patients | ✅ FIXED | SQL CAST syntax fix |
| Tasks API | ✅ DONE | Full CRUD at /api/tasks |
| Shadow Coder API | ✅ DONE | All endpoints at /api/shadow-coder |
| WebSocket Server | ✅ DONE | /ws with subscriptions |
| ORCC Integration | ✅ DONE | All endpoints working |
| Case Planning API | ⬜ TODO | /api/planning/{caseId} |

---

## Working API Endpoints

### Patients & Procedures (ORCC)
```
GET  /health                      - Health check
GET  /api/patients                - List patients
GET  /api/patients/{mrn}          - Get patient by MRN
POST /api/patients                - Create patient ✅ FIXED
GET  /api/procedures              - List procedures
GET  /api/procedures/{id}         - Get procedure
PATCH /api/procedures/{id}        - Update procedure
GET  /api/orcc/status             - ORCC integration status
```

### Tasks API (NEW)
```
GET  /api/tasks                   - List tasks (with filters)
POST /api/tasks                   - Create task
GET  /api/tasks/{id}              - Get task by ID
PATCH /api/tasks/{id}             - Update task
DELETE /api/tasks/{id}            - Delete task
POST /api/tasks/{id}/complete     - Mark complete
GET  /api/tasks/patient/{mrn}     - Tasks by patient
GET  /api/tasks/procedure/{id}    - Tasks by procedure
GET  /api/tasks/stats/summary     - Task statistics
```

### Shadow Coder API (NEW - Migrated from SCC)
```
GET  /api/shadow-coder/status           - Service status
POST /api/shadow-coder/intake/plaud     - Plaud transcript intake
POST /api/shadow-coder/intake/zapier    - Zapier webhook
GET  /api/shadow-coder/intake/status/{id} - Voice note status
GET  /api/shadow-coder/intake/recent    - Recent voice notes
GET  /api/shadow-coder/facts/{case_id}  - Get case facts
POST /api/shadow-coder/facts/{case_id}  - Add fact
GET  /api/shadow-coder/facts/{case_id}/history - Fact history
GET  /api/shadow-coder/prompts/{case_id} - Get prompts
POST /api/shadow-coder/prompts/{id}/action - Execute prompt
POST /api/shadow-coder/analyze          - Analyze transcript (needs API key)
```

### WebSocket (NEW)
```
WS   /ws?client_id={id}           - Real-time connection
GET  /ws/stats                    - Connection statistics
```

### AI Processing (Existing)
```
POST /api/parse                   - Parse transcript (Gemini)
POST /api/synopsis                - Generate synopsis (Gemini)
POST /api/extract                 - Extract PVI fields
```

---

## Database

```
Host: localhost:5432
Database: surgical_command_center
User: scc_user
```

### Key Tables
| Table | Records | Purpose |
|-------|---------|---------|
| scc_patients | 38 | Patient profiles |
| procedures | 24+ | Surgical procedures |
| tasks | 1+ | Task management (NEW) |
| scc_voice_notes | 6 | Shadow coder transcripts |
| scc_case_facts | - | Clinical truth map |
| scc_prompt_instances | - | Compliance prompts |

---

## Test Patients Created

| Name | MRN | Created |
|------|-----|---------|
| Larry Taylor | 32016089 | 2026-01-21 |
| Test Migration | TEST999 | 2026-01-21 |

---

## What's Next

1. ~~**Case Planning API** - Create table and /api/planning endpoints~~ ✅ DONE
2. **User Testing** - Validate full workflow with real patients
3. **ORCC Integration** - Connect ORCC frontend to new endpoints
4. **SCC Retirement** - Stop SCC services on port 3001

---

## Procedures API (NEW - 2026-01-21)

### POST /api/procedures
Create a new procedure with full endovascular planning data.

```bash
curl -X POST http://100.75.237.36:8001/api/procedures \
  -H "Content-Type: application/json" \
  -d '{
    "mrn": "18890211",
    "procedure_type": "LEA with Angioplasty",
    "procedure_name": "Left Lower Extremity Arteriogram with Atherectomy",
    "procedure_side": "left",
    "procedure_date": "2026-01-21",
    "scheduled_location": "ASC",
    "status": "draft",
    "surgical_status": "workup",
    "indication": {
      "primary_icd10": "I70.222",
      "primary_icd10_text": "Atherosclerosis with rest pain, left leg",
      "rutherford": "r4"
    },
    "access": {"site": "r_cfa", "sheath_size": "6", "anesthesia": "mac_local"},
    "inflow": {"aortoiliac": "normal", "cfa": "normal"},
    "outflow": {"at": "patent", "pt": "patent", "peroneal": "patent"},
    "vessel_data": {"l_sfa": {"status": "stenosis_severe", "length": "10-20cm"}},
    "interventions": [{"vessel": "L SFA", "vessel_id": "l_sfa", "intervention": "ath_pta"}],
    "cpt_codes": ["75710", "36246", "37225"]
  }'
```

### GET /api/planning/{mrn}
Get planning data for workspace to load.

```bash
curl http://100.75.237.36:8001/api/planning/18890211
```

Returns: patient info, procedure details, indication, vessel_data, interventions, cpt_codes

---

## For Other Claude Instances

**API Base URL**: `http://100.75.237.36:8001`

**Example calls**:
```bash
# Health check
curl http://100.75.237.36:8001/health

# Create patient
curl -X POST http://100.75.237.36:8001/api/patients \
  -H "Content-Type: application/json" \
  -d '{"mrn": "12345", "first_name": "John", "last_name": "Doe", "date_of_birth": "1960-01-01", "gender": "male"}'

# Create task
curl -X POST http://100.75.237.36:8001/api/tasks \
  -H "Content-Type: application/json" \
  -d '{"title": "Pre-op workup", "patient_mrn": "12345", "task_type": "workup", "priority": "high"}'

# WebSocket test
wscat -c "ws://100.75.237.36:8001/ws?client_id=test"
```

**Team Hub**: `ws://100.104.39.64:4847`

---

## Recent Changes (2026-01-21)

- Fixed SQL parameter binding (`:param::type` → `CAST(:param AS type)`)
- Created Tasks API with full CRUD
- Migrated Shadow Coder from SCC Node.js
- Added WebSocket server with subscriptions
- VS Code Claude Team extension configured

---

*This workspace is shared via claude-team hub*
