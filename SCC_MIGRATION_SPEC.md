# SCC → PlaudAI Migration Specification

**Date**: 2026-01-21
**Status**: ✅ CORE MIGRATION COMPLETE
**Owner**: PlaudAI (Server1)
**Last Updated**: 2026-01-21 15:55 EST

## Implementation Progress

| Component | Status | Completed |
|-----------|--------|-----------|
| POST /api/patients fix | ✅ DONE | 2026-01-21 |
| Tasks API | ✅ DONE | 2026-01-21 |
| Shadow Coder API | ✅ DONE | 2026-01-21 |
| WebSocket Server | ✅ DONE | 2026-01-21 |
| ORCC Integration | ✅ DONE | 2026-01-21 |
| Case Planning API | ⬜ TODO | - |

---

## Executive Summary

The Surgical Command Center (SCC) Node.js backend on port 3001 is being retired. All functionality will migrate to PlaudAI on port 8001. ORCC will be the new frontend, replacing the React Dashboard.

---

## Current State

```
┌─────────────────────────────────────────────────────────────┐
│  SCC Node (3001) - BROKEN                                   │
│  ├── Shadow Coder (AI charge coding)                        │
│  ├── WebSocket Server (real-time updates)                   │
│  ├── React Dashboard (RETIRING)                             │
│  ├── /api/patients, /api/procedures                         │
│  └── PostgreSQL connection (AUTH FAILING)                   │
│      DB_PASSWORD=YourSecurePassword (WRONG)                 │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│  PlaudAI (8001) - WORKING                                   │
│  ├── /api/patients (ORCC router)                            │
│  ├── /api/procedures (ORCC router)                          │
│  ├── /api/parse, /api/synopsis, /api/extract (AI)           │
│  └── PostgreSQL connection (WORKING)                        │
│      DB_PASSWORD=scc_password (CORRECT)                     │
└─────────────────────────────────────────────────────────────┘
```

---

## Target Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  PlaudAI Backend (8001) - UNIFIED                           │
│  ├── EXISTING:                                              │
│  │   ├── /api/patients                                      │
│  │   ├── /api/procedures                                    │
│  │   ├── /api/parse                                         │
│  │   ├── /api/synopsis                                      │
│  │   ├── /api/extract                                       │
│  │   └── /api/orcc/status                                   │
│  │                                                          │
│  ├── MIGRATE FROM SCC:                                      │
│  │   ├── /api/shadow-coder/analyze                          │
│  │   ├── /api/shadow-coder/intake                           │
│  │   └── WebSocket /ws (real-time updates)                  │
│  │                                                          │
│  └── NEW FOR ORCC:                                          │
│      ├── /api/tasks (CRUD for task management)              │
│      ├── /api/planning (surgical planning workflows)        │
│      └── /api/workspaces (PAD, Carotid, Aortic, Venous)    │
└─────────────────────────────────────────────────────────────┘
         ↑
         │ HTTP + WebSocket
         │
┌─────────────────────────────────────────────────────────────┐
│  ORCC Frontend (Static HTML → React)                        │
│  ├── Patient Lists & Search                                 │
│  ├── Procedure Workspaces                                   │
│  │   ├── PAD (Peripheral Arterial Disease)                  │
│  │   ├── Carotid                                            │
│  │   ├── Aortic                                             │
│  │   └── Venous                                             │
│  ├── Task Manager                                           │
│  ├── Shadow Coder Integration                               │
│  └── Real-time Updates (WebSocket)                          │
└─────────────────────────────────────────────────────────────┘
```

---

## Migration Phases

### Phase 1: Shadow Coder Migration (Priority: HIGH)

**Source**: `/home/server1/surgical-command-center/backend/`
- `routes/intake.js` - Shadow Coder API routes
- `services/shadowChargeCoder.js` - Claude AI integration
- `prompts/` - Charge coding prompts

**Target**: `/home/server1/plaudai_uploader/backend/routes/shadow_coder.py`

**New Endpoints**:
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/shadow-coder/analyze` | POST | Analyze transcript for charge codes |
| `/api/shadow-coder/intake` | POST | Process Plaud intake for billing |
| `/api/shadow-coder/prompts` | GET | List available prompt templates |

**Dependencies**:
- ANTHROPIC_API_KEY for Claude API
- Prompt templates (migrate from SCC)

### Phase 2: WebSocket Server (Priority: MEDIUM)

**Source**: `/home/server1/surgical-command-center/backend/websocket/`
- `server.js` - WebSocket initialization
- Message handlers for real-time updates

**Target**: `/home/server1/plaudai_uploader/backend/websocket/`

**Implementation**:
```python
# Using FastAPI WebSocket
from fastapi import WebSocket, WebSocketDisconnect

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_json()
            # Handle: patient_update, procedure_update, task_update
            await manager.broadcast(data)
    except WebSocketDisconnect:
        manager.disconnect(websocket)
```

**Message Types**:
| Type | Payload | Description |
|------|---------|-------------|
| `patient_selected` | `{mrn, name}` | Patient context changed |
| `procedure_update` | `{id, status}` | Procedure status changed |
| `task_update` | `{id, status}` | Task completed/added |
| `sync_request` | `{type}` | Request full state sync |

### Phase 3: Tasks API (Priority: HIGH)

**New Endpoints**:
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/tasks` | GET | List tasks (filter by patient, status) |
| `/api/tasks` | POST | Create new task |
| `/api/tasks/{id}` | GET | Get task details |
| `/api/tasks/{id}` | PATCH | Update task |
| `/api/tasks/{id}` | DELETE | Delete task |

**Database Table**: `tasks` (NEW)
```sql
CREATE TABLE tasks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_mrn VARCHAR(50) REFERENCES scc_patients(mrn),
    procedure_id UUID REFERENCES procedures(id),
    title VARCHAR(255) NOT NULL,
    description TEXT,
    task_type VARCHAR(50), -- 'workup', 'clearance', 'scheduling', 'follow_up'
    status VARCHAR(20) DEFAULT 'pending', -- 'pending', 'in_progress', 'completed', 'blocked'
    priority VARCHAR(10) DEFAULT 'normal', -- 'low', 'normal', 'high', 'urgent'
    due_date TIMESTAMP,
    assigned_to VARCHAR(100),
    created_by VARCHAR(100),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    completed_at TIMESTAMP,
    notes TEXT
);
```

### Phase 4: Planning API (Priority: MEDIUM)

**New Endpoints**:
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/planning/workups` | GET | List surgical workups |
| `/api/planning/workups/{mrn}` | GET | Get patient workup status |
| `/api/planning/clearances` | GET | List pending clearances |
| `/api/planning/schedule` | GET | Get surgical schedule |

---

## Database Schema Updates

### New Tables Required

```sql
-- Tasks table (Phase 3)
CREATE TABLE tasks (...);

-- Planning/Workup tracking (Phase 4)
CREATE TABLE surgical_workups (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_mrn VARCHAR(50) REFERENCES scc_patients(mrn),
    procedure_id UUID REFERENCES procedures(id),
    workup_type VARCHAR(50), -- 'cardiac', 'pulmonary', 'renal', 'general'
    status VARCHAR(20) DEFAULT 'pending',
    ordered_date TIMESTAMP,
    completed_date TIMESTAMP,
    result TEXT,
    notes TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);
```

---

## ORCC Integration Points

ORCC frontend should update `api-client.js` to use:

```javascript
const API_BASE = 'http://100.75.237.36:8001';

// Existing endpoints (already working)
GET  ${API_BASE}/api/patients
GET  ${API_BASE}/api/patients/{mrn}
GET  ${API_BASE}/api/procedures
PATCH ${API_BASE}/api/procedures/{id}

// New endpoints (after migration)
POST ${API_BASE}/api/shadow-coder/analyze
GET  ${API_BASE}/api/tasks
POST ${API_BASE}/api/tasks
WS   ${API_BASE}/ws
```

---

## SCC Retirement Checklist

After all migrations complete:

- [ ] Verify all endpoints work on PlaudAI:8001
- [ ] Update ORCC to point to PlaudAI exclusively
- [ ] Stop SCC service: `sudo systemctl stop scc`
- [ ] Disable SCC service: `sudo systemctl disable scc`
- [ ] Archive SCC code (don't delete yet)
- [ ] Update documentation
- [ ] Monitor for 1 week
- [ ] Remove SCC systemd service file

---

## Environment Variables

### PlaudAI .env (Current - Working)
```bash
DB_HOST=localhost
DB_PORT=5432
DB_NAME=surgical_command_center
DB_USER=scc_user
DB_PASSWORD=scc_password
GOOGLE_API_KEY=xxx  # Gemini AI
```

### PlaudAI .env (After Migration - Add)
```bash
# Existing...
ANTHROPIC_API_KEY=xxx  # For Shadow Coder (Claude)
WEBSOCKET_ENABLED=true
```

---

## Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| Shadow Coder prompt incompatibility | Medium | Test with real transcripts before cutover |
| WebSocket connection drops | Low | Implement reconnection logic in ORCC |
| Missing functionality discovered | Medium | Keep SCC code archived, quick rollback |
| Database migration issues | Low | No schema changes to existing tables |

---

## Timeline

| Phase | Task | Duration | Dependencies |
|-------|------|----------|--------------|
| 1 | Shadow Coder Migration | 2-3 hours | ANTHROPIC_API_KEY |
| 2 | WebSocket Server | 1-2 hours | None |
| 3 | Tasks API | 2-3 hours | Database migration |
| 4 | Planning API | 2-3 hours | Tasks API |
| 5 | ORCC Updates | 1-2 hours | Phases 1-4 |
| 6 | SCC Retirement | 30 mins | All phases complete |

**Total Estimated Time**: 8-14 hours

---

## Contact

- **PlaudAI Claude**: Server1 (100.75.237.36)
- **ORCC Claude**: Workstation (100.104.39.64)
- **Hub**: ws://100.104.39.64:4847

---

*Document Version: 1.0*
*Last Updated: 2026-01-21*
