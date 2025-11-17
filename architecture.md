# PlaudAI Uploader - Architecture Review

## 🏗️ System Overview

```
┌─────────────────────────────────────────────────────────────┐
│                     User Interface Layer                     │
├─────────────────────────────────────────────────────────────┤
│  Web Browser                                                 │
│  └─ frontend/index.html (HTML/JS)                           │
│     └─ Simple form for manual transcript entry              │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼ HTTP/REST API
┌─────────────────────────────────────────────────────────────┐
│                   Application Layer                          │
├─────────────────────────────────────────────────────────────┤
│  FastAPI Backend (backend/main.py)                          │
│  ├─ Upload Endpoints (/upload, /batch-upload)               │
│  ├─ Query Endpoints (/patients, /transcripts)               │
│  └─ Health & Stats (/health, /stats)                        │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                    Business Logic Layer                      │
├─────────────────────────────────────────────────────────────┤
│  services/parser.py                                          │
│  ├─ Markdown section parsing                                │
│  ├─ Medical keyword tagging                                 │
│  ├─ PVI field extraction                                    │
│  └─ Confidence scoring                                      │
│                                                              │
│  services/uploader.py                                        │
│  ├─ Patient management (get/create)                         │
│  ├─ Transcript storage                                      │
│  └─ PVI procedure record creation                           │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                    Data Access Layer                         │
├─────────────────────────────────────────────────────────────┤
│  SQLAlchemy ORM (models.py)                                 │
│  ├─ Patient                                                  │
│  ├─ VoiceTranscript                                         │
│  └─ PVIProcedure                                            │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                    Database Layer                            │
├─────────────────────────────────────────────────────────────┤
│  PostgreSQL (server1-70TR000LUX)                            │
│  Database: surgical_command_center                           │
│  ├─ patients                                                 │
│  ├─ voice_transcripts                                       │
│  └─ pvi_procedures                                          │
└─────────────────────────────────────────────────────────────┘
```

---

## 🔗 Integration with Surgical Command Center

### Current SCC Architecture

Your existing Surgical Command Center has:

1. **Backend Server** (Node.js Express)
   - Port: 3000
   - Database: `surgical_command_center`
   - WebSocket support for real-time updates

2. **Dragon Dictation Integration** (Python)
   - GPU-accelerated Whisper transcription
   - Gemini AI template generation
   - Port: 5005

3. **Database Tables**
   - `procedures`
   - `transcriptions`
   - `template_usage`

### PlaudAI Uploader Position

PlaudAI Uploader is a **standalone mini-app** that:
- Runs independently on port 8000
- Connects to the same PostgreSQL database
- Adds new tables without disrupting existing ones
- Can be accessed separately or integrated into SCC UI

### Integration Paths

```
┌──────────────────────┐
│  Dragon Dictation    │  ← Real-time voice during surgery
│  (Port 5005)         │
└──────────────────────┘
           │
           ▼
┌──────────────────────┐
│  SCC Backend         │  ← Main application logic
│  (Port 3000)         │
└──────────────────────┘
           │
           ▼
┌──────────────────────┐
│  PostgreSQL          │  ← Shared database
│  surgical_command_   │
│  center              │
└──────────────────────┘
           ▲
           │
┌──────────────────────┐
│  PlaudAI Uploader    │  ← Async voice note import
│  (Port 8000)         │
└──────────────────────┘
```

---

## 📊 Database Schema

### New Tables Added by PlaudAI

#### 1. **patients** (Enhanced)
```sql
CREATE TABLE patients (
    id SERIAL PRIMARY KEY,
    first_name TEXT,
    last_name TEXT,
    dob DATE,
    athena_mrn VARCHAR(20) UNIQUE NOT NULL,
    birth_sex VARCHAR(10),
    race VARCHAR(50),
    zip_code VARCHAR(10),
    center_site_location VARCHAR(100),
    insurance_type VARCHAR(50),
    created_at TIMESTAMP DEFAULT now(),
    updated_at TIMESTAMP DEFAULT now()
);
```

#### 2. **voice_transcripts**
```sql
CREATE TABLE voice_transcripts (
    id SERIAL PRIMARY KEY,
    patient_id INTEGER REFERENCES patients(id),
    visit_date TIMESTAMP DEFAULT now(),
    transcript_title TEXT,
    transcript_text TEXT NOT NULL,
    summary TEXT,
    tags JSONB,
    confidence_score FLOAT,
    is_processed BOOLEAN DEFAULT FALSE,
    processing_notes TEXT,
    created_at TIMESTAMP DEFAULT now(),
    updated_at TIMESTAMP DEFAULT now()
);
```

#### 3. **pvi_procedures** (SVS VQI Registry Fields)
```sql
CREATE TABLE pvi_procedures (
    id SERIAL PRIMARY KEY,
    patient_id INTEGER REFERENCES patients(id),
    transcript_id INTEGER REFERENCES voice_transcripts(id),
    
    -- Basic info
    procedure_date DATE NOT NULL,
    surgeon_name VARCHAR(100),
    
    -- Demographics
    smoking_history VARCHAR(50),
    comorbidities JSONB,
    living_status VARCHAR(50),
    creatinine FLOAT,
    
    -- History
    indication VARCHAR(100),
    rutherford_status VARCHAR(50),
    prior_amputation BOOLEAN,
    preop_abi FLOAT,
    preop_tbi FLOAT,
    
    -- Procedure details
    access_site VARCHAR(100),
    radiation_exposure FLOAT,
    contrast_volume FLOAT,
    arteries_treated JSONB,
    tasc_grade VARCHAR(10),
    device_details JSONB,
    treatment_success BOOLEAN,
    
    -- Post-procedure
    complications JSONB,
    disposition_status VARCHAR(50),
    discharge_medications JSONB,
    
    -- 30-day follow-up
    followup_30day_captured BOOLEAN,
    readmission_30day BOOLEAN,
    reintervention_30day BOOLEAN,
    
    -- Long-term follow-up (9-21 months)
    ltfu_captured BOOLEAN,
    ltfu_mortality BOOLEAN,
    ltfu_patency_documentation TEXT,
    ltfu_amputation_since_discharge BOOLEAN,
    
    created_at TIMESTAMP DEFAULT now(),
    updated_at TIMESTAMP DEFAULT now()
);
```

### Relationship to Existing SCC Tables

The PlaudAI tables **complement** but don't replace existing SCC tables:

- **SCC `procedures`** → Real-time surgical documentation
- **PlaudAI `voice_transcripts`** → Post-op voice notes and summaries
- **PlaudAI `pvi_procedures`** → Registry-compliant structured data

They can be linked via:
```sql
-- Add foreign key to SCC procedures if needed
ALTER TABLE voice_transcripts 
ADD COLUMN scc_procedure_id INTEGER REFERENCES procedures(id);
```

---

## 🔄 Data Flow

### Upload Workflow

```
1. User pastes PlaudAI transcript
   └─► Frontend validates form data

2. POST /upload with patient info + transcript
   └─► FastAPI receives request

3. Patient lookup/creation
   └─► Check Athena MRN
   └─► Create new patient OR update existing

4. Text processing
   ├─► Parse markdown sections
   ├─► Extract medical tags (pad, stenosis, etc.)
   ├─► Identify PVI registry fields
   └─► Calculate confidence score

5. Database insertion
   ├─► Insert voice_transcript record
   └─► Insert pvi_procedures record (if enough data)

6. Return response
   └─► Patient ID, Transcript ID, Tags, Confidence
```

### Integration with Existing Workflows

**Scenario 1: Post-Operative Documentation**
```
Surgery Day:
1. Dragon Dictation → Real-time note → SCC procedures table
2. Later: Review PlaudAI recording → PlaudAI Uploader → voice_transcripts

Query to link:
SELECT 
    p.athena_mrn,
    pr.procedure_name,
    vt.transcript_text
FROM procedures pr
JOIN patients p ON pr.patient_id = p.id
LEFT JOIN voice_transcripts vt ON vt.patient_id = p.id
WHERE pr.created_at::date = vt.visit_date::date;
```

**Scenario 2: Clinic Follow-up**
```
1. PlaudAI records clinic visit
2. Upload to PlaudAI Uploader
3. Auto-extract 30-day follow-up fields
4. Update pvi_procedures.followup_30day_* fields
```

---

## 🎯 Key Features

### 1. Intelligent Text Parsing

The `services/parser.py` module provides:

**Markdown Section Recognition**
```python
## Chief Complaint
Leg pain...

## Assessment
Bilateral PAD...
```
→ Parsed into structured sections

**Medical Tagging**
- Vascular terms: PAD, CLI, aneurysm
- Anatomical: femoral, popliteal, tibial
- Procedures: angioplasty, stent, atherectomy
- Findings: occlusion, stenosis, calcification

**PVI Field Extraction**
- Rutherford classification (regex: `rutherford 4`)
- Numeric values (ABI, TBI, creatinine, contrast volume)
- Arteries treated (right/left femoral, SFA, etc.)
- Access site identification
- TASC grade (A/B/C/D)
- Complications

### 2. Confidence Scoring

Algorithm considers:
- Text length (word count)
- Number of extracted fields
- Presence of critical fields (Rutherford, ABI, arteries)

Score: 0.0 - 1.0 (displayed as percentage)

### 3. Patient Deduplication

Smart patient matching:
- Primary key: Athena MRN
- Auto-update demographics on subsequent uploads
- Prevents duplicate patient records

### 4. Batch Processing

Upload multiple transcripts at once:
```bash
POST /batch-upload
{
  "items": [
    {patient_data, transcript_text},
    {patient_data, transcript_text},
    ...
  ]
}
```

---

## 🔮 Future Enhancements

### Phase 1: Enhanced AI (Optional)

Add Gemini AI integration for:
- Contextual tagging beyond keywords
- Sentiment analysis
- Clinical decision support suggestions

```python
# In services/parser.py
import google.generativeai as genai

def enhanced_tagging_with_gemini(text):
    model = genai.GenerativeModel('gemini-2.0-flash-exp')
    response = model.generate_content(
        f"Extract medical conditions from: {text}"
    )
    return parse_gemini_response(response.text)
```

### Phase 2: SCC UI Integration

Embed PlaudAI Uploader into main SCC interface:

```javascript
// In SCC frontend
<button onclick="showPlaudAIUploader()">
  📱 Import PlaudAI Note
</button>

function showPlaudAIUploader() {
  // Load PlaudAI Uploader in modal
  fetch('http://localhost:8000/upload')
    .then(...)
}
```

### Phase 3: Automated Import

Schedule cron job to auto-import from PlaudAI API:

```bash
# /etc/cron.d/plaudai-sync
*/15 * * * * /opt/plaudai_uploader/venv/bin/python \
  /opt/plaudai_uploader/scripts/sync_plaudai.py
```

### Phase 4: LTFU Automation

Automated long-term follow-up reminders:

```python
# Check patients needing 9-21 month follow-up
SELECT patient_id, procedure_date
FROM pvi_procedures
WHERE procedure_date BETWEEN 
  (CURRENT_DATE - INTERVAL '21 months') AND
  (CURRENT_DATE - INTERVAL '9 months')
AND ltfu_captured = FALSE;
```

---

## 🛡️ Security Considerations

### Current Status (Development)
- ⚠️ No authentication
- ⚠️ CORS allows all origins
- ⚠️ Database password in .env
- ⚠️ No encryption

### Production Requirements
- ✅ JWT authentication for API
- ✅ SSL/TLS encryption
- ✅ HIPAA-compliant logging
- ✅ Data encryption at rest
- ✅ Audit trails
- ✅ Role-based access control

---

## 📈 Performance Considerations

### Current Capacity
- Single-threaded: ~100 requests/minute
- Database connection pool: 5 connections
- Suitable for: Small to medium clinics (< 1000 procedures/month)

### Scaling Options

**Horizontal Scaling**
```bash
# Run multiple workers
uvicorn backend.main:app --workers 4 --host 0.0.0.0 --port 8000
```

**Load Balancing**
```nginx
upstream plaudai_backend {
    server 127.0.0.1:8000;
    server 127.0.0.1:8001;
    server 127.0.0.1:8002;
}
```

**Database Optimization**
- Add indexes on frequently queried fields
- Implement caching (Redis)
- Archive old transcripts

---

## 🧪 Testing Strategy

### Unit Tests
```python
def test_segment_summary():
    text = "## Chief Complaint\nPain\n## Assessment\nPAD"
    sections = segment_summary(text)
    assert "Chief Complaint" in sections
    assert "Assessment" in sections

def test_generate_tags():
    text = "femoral artery stenosis with claudication"
    tags = generate_tags(text)
    assert "femoral" in tags
    assert "stenosis" in tags
    assert "claudication" in tags
```

### Integration Tests
```python
def test_upload_transcript(test_db):
    result = upload_transcript(
        test_db,
        patient_data={"first_name": "Test", ...},
        summary_text="Test transcript"
    )
    assert result["patient_id"] > 0
    assert result["transcript_id"] > 0
```

---

## 📞 Support & Maintenance

### Monitoring

```bash
# Check service status
systemctl status plaudai-uploader

# View logs
tail -f /opt/plaudai_uploader/logs/plaudai_uploader.log

# Database queries
psql -U postgres -d surgical_command_center
```

### Backup Strategy

```bash
# Daily backup
0 2 * * * pg_dump -U postgres surgical_command_center > \
  /backup/scc_$(date +\%Y\%m\%d).sql

# Backup voice transcripts
0 3 * * * pg_dump -U postgres -t voice_transcripts \
  -t pvi_procedures surgical_command_center > \
  /backup/plaudai_$(date +\%Y\%m\%d).sql
```

---

## ✅ Deployment Checklist

- [ ] PostgreSQL accessible from server1-70TR000LUX
- [ ] Python 3.8+ installed
- [ ] Virtual environment created
- [ ] Dependencies installed
- [ ] .env configured with correct credentials
- [ ] Database tables created
- [ ] API health check passes
- [ ] Frontend loads correctly
- [ ] Test upload succeeds
- [ ] systemd service configured (production)
- [ ] Nginx reverse proxy setup (optional)
- [ ] Firewall rules configured
- [ ] SSL certificate installed (production)
- [ ] Backup strategy implemented
- [ ] Monitoring configured

---

## 🎓 Summary

PlaudAI Uploader is designed as a **modular, standalone component** that:

1. ✅ Runs independently without disrupting existing SCC
2. ✅ Shares the same database for seamless integration
3. ✅ Provides PVI registry-compliant data structure
4. ✅ Auto-processes transcripts with intelligent parsing
5. ✅ Can be integrated into SCC UI in future phases
6. ✅ Scales from development to production

**Next Action**: Deploy to server1-70TR000LUX and test with real PlaudAI transcripts!