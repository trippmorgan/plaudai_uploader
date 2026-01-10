# Port Mapping - Albany Vascular System Ecosystem

## Current Active Configuration

| Port | Host | Service | Description | Status |
|------|------|---------|-------------|--------|
| **8001** | 100.75.237.36 (server1) | PlaudAI Uploader (VAI) | FastAPI backend + frontend | **ACTIVE** |
| **3001** | localhost | Surgical Command Center | Node.js/Express backend | **ACTIVE** |
| **3000** | 100.113.243.36 (MacBook) | Medical Mirror Observer | Telemetry & AI analysis | **ACTIVE** |
| **5432** | localhost | PostgreSQL | Database server | ACTIVE |
| **8384** | localhost | Syncthing | File sync service | SYSTEM |

---

## Why Port 8001?

The PlaudAI Uploader uses a **single-server architecture** where FastAPI serves BOTH:
1. **Static files** (the frontend at `/index.html`)
2. **REST API endpoints** (all backend functionality)

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    FastAPI Server @ Port 8001                            │
│                                                                          │
│  STATIC FILES (Frontend)              REST API (Backend)                │
│  ─────────────────────────            ──────────────────                │
│  GET /index.html → WebUI              POST /upload → Transcripts        │
│  GET /static/*   → Assets             GET  /patients → Patient list     │
│                                        POST /ingest/athena → EMR data   │
│                                        POST /clinical/query → AI chat   │
│                                        GET  /health → Health check      │
└─────────────────────────────────────────────────────────────────────────┘
```

**Key Point:** The frontend's JavaScript (`frontend/index.html:861`) has:
```javascript
const API_BASE = 'http://100.75.237.36:8001';
```

This means the browser loads the page from port 8001, then makes API calls back to the SAME port 8001.

---

## Application Port Assignments

### PlaudAI Uploader (This Project)
```
Port 8001 (Active)
├── GET  /index.html      ← Browser loads WebUI here
├── POST /ingest/athena   ← Athena-Scraper sends data here
├── GET  /ingest/stats    ← Monitoring dashboard
├── POST /upload          ← PlaudAI voice transcripts
├── GET  /patients        ← Patient lookup
├── GET  /health          ← Health check
└── Static files          ← CSS/JS assets
```

### Athena-Scraper (Chrome Extension)
```
Connects TO:
├── Port 8001 → PlaudAI Uploader /ingest/athena endpoint
└── Athena EMR (external cloud service)
```

### Surgical Command Center (SCC)
```
Port 3001 (localhost)
├── GET  /                 ← Main SCC dashboard
├── GET  /api/patients     ← Patient list
├── GET  /api/procedures   ← Procedure list
├── WebSocket /ws          ← Real-time updates
└── Embeds VAI iframes     ← VAI integration
```

### Medical Mirror Observer
```
Port 3000 (100.113.243.36 - MacBook Pro)
├── POST /api/events       ← Telemetry ingestion
├── GET  /api/events/stats ← Event statistics
├── GET  /api/recommendations ← AI recommendations
└── WebSocket              ← Real-time dashboard
```

### Inter-Service Communication
```
┌─────────────────────────────────────────────────────────────────────────┐
│                        SERVICE MESH                                      │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  SCC (localhost:3001)                                                    │
│    │                                                                     │
│    ├─────► VAI iframe (100.75.237.36:8001)                              │
│    │         └─ postMessage: PATIENT_CONTEXT_LOADED, PATIENT_SELECTED   │
│    │                                                                     │
│    └─────► Observer (100.113.243.36:3000)                               │
│              └─ POST /api/events: telemetry                             │
│                                                                          │
│  VAI (100.75.237.36:8001)                                               │
│    │                                                                     │
│    ├─────► PostgreSQL (localhost:5432)                                  │
│    │         └─ Database queries                                        │
│    │                                                                     │
│    ├─────► Gemini AI (external)                                         │
│    │         └─ Synopsis generation, clinical queries                   │
│    │                                                                     │
│    └─────► Observer (100.113.243.36:3000)                               │
│              └─ POST /api/events: telemetry                             │
│                                                                          │
│  Athena-Scraper (Chrome Extension)                                       │
│    │                                                                     │
│    └─────► VAI (100.75.237.36:8001)                                     │
│              └─ POST /ingest/athena: clinical events                    │
│              └─ GET  /ingest/clinical/{mrn}: fetch stored data          │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### Future Services (Reserved)
| Port | Reserved For | Notes |
|------|--------------|-------|
| 8000 | Available | Can use if 8001 is occupied |
| 8002 | PDF Generator Service | If split from main app |
| 8003 | AI Synopsis Worker | Background processing |
| 8080 | Nginx Reverse Proxy | Production deployment |

---

## Startup Commands

```bash
# PlaudAI Uploader (Current Configuration)
cd ~/plaudai_uploader
conda activate plaudai
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8001

# Access WebUI
# Browser: http://100.75.237.36:8001/index.html

# Check what's using a port
lsof -i :8001

# Kill process on a port
kill $(lsof -t -i:8001)
```

---

## If You Need to Change Ports

**IMPORTANT:** If you change the backend port, you must update TWO places:

1. **Startup command** - Change `--port 8001` to new port
2. **Frontend API_BASE** - Edit `frontend/index.html:861`:
   ```javascript
   const API_BASE = 'http://100.75.237.36:NEW_PORT';
   ```

3. **Athena-Scraper config** (if using):
   - Extension settings → Server URL → `http://100.75.237.36:NEW_PORT`

---

## Network Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        BROWSER                                   │
│  ┌─────────────────┐     ┌──────────────────────────────────┐   │
│  │ Athena EMR Tab  │     │     PlaudAI Frontend Tab         │   │
│  │                 │     │  http://100.75.237.36:8001/index.html│
│  └────────┬────────┘     └──────────────┬───────────────────┘   │
│           │                             │                        │
│  ┌────────▼────────┐                    │                        │
│  │ Athena-Scraper  │                    │ fetch(API_BASE + ...)  │
│  │ Chrome Extension│                    │                        │
│  └────────┬────────┘                    │                        │
└───────────┼─────────────────────────────┼────────────────────────┘
            │                             │
            │ POST /ingest/athena         │ All API calls
            │                             │
            ▼                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                 100.75.237.36:8001                               │
│                  PlaudAI Uploader                                │
│                    (FastAPI)                                     │
│                                                                  │
│   Serves: index.html + All API endpoints                        │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             │ psycopg2
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                    localhost:5432                                │
│                     PostgreSQL                                   │
│              surgical_command_center                             │
└─────────────────────────────────────────────────────────────────┘
```

---

## Environment Variables

Ensure `.env` has correct configuration:
```env
API_HOST=0.0.0.0
API_PORT=8001
DATABASE_URL=postgresql://user:pass@localhost:5432/surgical_command_center
```

---

## Troubleshooting

| Issue | Cause | Solution |
|-------|-------|----------|
| "Connection refused" in browser | Server not running | Start uvicorn on port 8001 |
| API calls fail but page loads | API_BASE mismatch | Check `frontend/index.html:861` matches server port |
| "Address already in use" | Port 8001 occupied | `kill $(lsof -t -i:8001)` or use different port |
| Athena data not arriving | Wrong port in extension | Update Athena-Scraper settings to port 8001 |

---

## Related Documentation

- [VAI-SCC-INTEGRATION.md](VAI-SCC-INTEGRATION.md) - postMessage protocol for SCC ↔ VAI sync
- [OBSERVER_INTEGRATION_SPEC.md](OBSERVER_INTEGRATION_SPEC.md) - Telemetry event schema
- [ATHENA_SCRAPER_DATABASE_SPEC.md](ATHENA_SCRAPER_DATABASE_SPEC.md) - Athena ingestion API

---
Last Updated: 2026-01-09
