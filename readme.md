# 🏥 PlaudAI Uploader

**Voice Transcript Import System for Surgical Command Center**

A standalone mini-application that imports PlaudAI voice transcripts, automatically parses medical content, extracts PVI (Peripheral Vascular Intervention) registry fields, and stores structured data in your PostgreSQL database.

---

## 📋 Table of Contents

1. [Features](#features)
2. [Quick Start](#quick-start)
3. [Project Structure](#project-structure)
4. [Installation](#installation)
5. [Configuration](#configuration)
6. [Usage](#usage)
7. [API Documentation](#api-documentation)
8. [PVI Registry Integration](#pvi-registry-integration)
9. [Deployment](#deployment)
10. [Architecture](#architecture)
11. [Contributing](#contributing)

---

## ✨ Features

### Core Functionality
- 📝 **Smart Text Parsing** - Automatically segments markdown-formatted transcripts
- 🏷️ **Medical Tagging** - Identifies vascular procedures, anatomical locations, findings
- 📊 **PVI Registry Compliance** - Extracts SVS VQI peripheral vascular intervention fields
- 🎯 **Confidence Scoring** - Rates extraction quality (0-100%)
- 👥 **Patient Management** - Auto-creates/updates patient records by Athena MRN
- 🔄 **Batch Upload** - Process multiple transcripts at once
- 🔍 **Search & Query** - Find patients, transcripts, procedures

### Technical Features
- ⚡ **FastAPI Backend** - Modern, async Python web framework
- 🗄️ **PostgreSQL Integration** - Connects to existing SCC database
- 🎨 **Simple Web UI** - Clean HTML/JS interface for manual uploads
- 🔌 **REST API** - Full programmatic access
- 📈 **Scalable** - Multi-worker support for production
- 🛡️ **Production Ready** - systemd service, nginx integration

---

## 🚀 Quick Start

### Prerequisites
- Python 3.8+
- PostgreSQL 12+ (already running on server1-70TR000LUX)
- Access to `surgical_command_center` database

### 1. Clone/Create Project

```bash
mkdir -p /opt/plaudai_uploader
cd /opt/plaudai_uploader
```

### 2. Install Dependencies

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Configure Environment

```bash
cp .env.example .env
nano .env  # Update DB_PASSWORD and other settings
```

### 4. Start Server

```bash
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

### 5. Access UI

Open browser: `http://localhost:8000/docs` (API docs)
Or: Open `frontend/index.html` in browser

---

## 📁 Project Structure

```
plaudai_uploader/
│
├── backend/                      # FastAPI application
│   ├── __init__.py
│   ├── config.py                 # Environment configuration
│   ├── db.py                     # Database connection
│   ├── models.py                 # SQLAlchemy ORM models
│   ├── schemas.py                # Pydantic validation schemas
│   ├── main.py                   # FastAPI app & routes
│   └── services/
│       ├── __init__.py
│       ├── parser.py             # Text parsing & tagging
│       └── uploader.py           # Upload business logic
│
├── frontend/
│   └── index.html                # Web UI for uploads
│
├── logs/                         # Application logs
│   └── plaudai_uploader.log
│
├── requirements.txt              # Python dependencies
├── .env.example                  # Environment template
├── .env                          # Your actual config (not in git)
├── README.md                     # This file
├── DEPLOYMENT.md                 # Deployment guide
└── ARCHITECTURE.md               # Architecture documentation
```

---

## 🔧 Installation

### Development Environment

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Copy environment template
cp .env.example .env

# Edit configuration
nano .env
```

### Production Environment (server1-70TR000LUX)

See [DEPLOYMENT.md](DEPLOYMENT.md) for detailed instructions including:
- systemd service setup
- Nginx reverse proxy
- SSL/TLS configuration
- Firewall rules

---

## ⚙️ Configuration

### Environment Variables (.env)

```bash
# Database
DB_HOST=server1-70TR000LUX    # PostgreSQL server
DB_PORT=5432
DB_NAME=surgical_command_center
DB_USER=postgres
DB_PASSWORD=your_secure_password

# API Server
API_HOST=0.0.0.0
API_PORT=8000
DEBUG=True                     # False in production

# Optional: Gemini AI
GOOGLE_API_KEY=your_api_key    # For enhanced tagging

# Features
PVI_ENABLED=True               # Enable PVI registry fields

# Logging
LOG_LEVEL=INFO
LOG_FILE=logs/plaudai_uploader.log
```

### Database Connection

The app connects to your existing `surgical_command_center` database and creates these tables:
- `patients` (enhanced with PVI demographics)
- `voice_transcripts`
- `pvi_procedures`

**Important**: These tables are additive and don't conflict with existing SCC tables.

---

## 💡 Usage

### Web Interface

1. Open `frontend/index.html` in a browser
2. Fill in patient information:
   - First Name, Last Name
   - Date of Birth
   - Athena MRN (required - used for deduplication)
3. Paste PlaudAI transcript
4. Click "Upload Transcript"
5. Review results: tags, confidence score, warnings

### API Usage (Python)

```python
import requests

# Upload transcript
response = requests.post('http://localhost:8000/upload', json={
    "first_name": "John",
    "last_name": "Doe",
    "dob": "1960-05-15",
    "athena_mrn": "MRN123456",
    "transcript_text": """
## Chief Complaint
Patient presents with right leg claudication

## Physical Exam
Diminished right femoral pulse

## Assessment
Peripheral arterial disease, likely right SFA stenosis
Rutherford category 3

## Plan
Proceed with right lower extremity angiogram
Consider angioplasty vs stenting
    """
})

result = response.json()
print(f"Patient ID: {result['patient_id']}")
print(f"Tags: {result['tags']}")
print(f"Confidence: {result['confidence_score']:.1%}")
```

### API Usage (cURL)

```bash
# Upload transcript
curl -X POST http://localhost:8000/upload \
  -H "Content-Type: application/json" \
  -d '{
    "first_name": "Jane",
    "last_name": "Smith",
    "dob": "1975-08-20",
    "athena_mrn": "MRN789012",
    "transcript_text": "Bilateral femoral artery stenosis..."
  }'

# Get patient info
curl http://localhost:8000/patients/1

# Get patient's transcripts
curl http://localhost:8000/patients/1/transcripts

# Get statistics
curl http://localhost:8000/stats
```

---

## 📚 API Documentation

### Endpoints

#### Health & Info

**GET /** - Health check
```json
{
  "service": "PlaudAI Uploader",
  "version": "1.0.0",
  "status": "healthy",
  "database": "connected"
}
```

**GET /health** - Detailed health
```json
{
  "status": "healthy",
  "database": "healthy",
  "timestamp": "2025-11-11T10:30:00"
}
```

#### Upload

**POST /upload** - Upload single transcript
```json
Request:
{
  "first_name": "John",
  "last_name": "Doe",
  "dob": "1960-05-15",
  "athena_mrn": "MRN123456",
  "transcript_text": "...",
  "transcript_title": "Clinic Visit",
  "birth_sex": "M",
  "race": "White"
}

Response:
{
  "status": "success",
  "patient_id": 1,
  "transcript_id": 5,
  "tags": ["pad", "femoral", "stenosis"],
  "confidence_score": 0.85,
  "warnings": []
}
```

**POST /batch-upload** - Upload multiple transcripts
```json
Request:
{
  "items": [
    {"patient_data": {...}, "transcript_text": "..."},
    {"patient_data": {...}, "transcript_text": "..."}
  ]
}

Response:
{
  "status": "completed",
  "total": 2,
  "successful": 2,
  "failed": 0,
  "results": [...]
}
```

#### Query

**GET /patients** - List patients
- Query params: `search` (name or MRN), `limit` (default 50)

**GET /patients/{id}** - Get specific patient

**GET /patients/{id}/transcripts** - Get patient's transcripts

**GET /patients/{id}/procedures** - Get patient's PVI procedures

**GET /transcripts/{id}** - Get specific transcript

**GET /stats** - Database statistics

### Interactive API Docs

Visit `http://localhost:8000/docs` for interactive Swagger UI documentation.

---

## 🩺 PVI Registry Integration

### Supported Fields

PlaudAI Uploader automatically extracts PVI (Peripheral Vascular Intervention) registry fields from free text, following **SVS VQI (Society for Vascular Surgery Vascular Quality Initiative)** standards.

#### Basic Information
- Procedure date, surgeon name
- Patient demographics (smoking, living status)

#### Clinical History
- **Rutherford Classification** (0-6)
- Indication (acute vs chronic)
- Prior interventions
- Pre-op ABI/TBI
- Comorbidities

#### Procedure Details
- Access site (femoral, radial, brachial)
- Sheath size, closure method
- Radiation exposure, contrast volume
- Arteries treated (with laterality)
- **TASC Grade** (A/B/C/D)
- Treatment lengths

#### Devices & Techniques
- Angioplasty, stenting, atherectomy
- Device details (brand, size)
- Thrombectomy
- Treatment success/failure

#### Outcomes
- Complications (dissection, perforation, etc.)
- Disposition status
- Discharge medications

#### Follow-up
- 30-day readmissions/reinterventions
- Long-term follow-up (9-21 months)
- Mortality tracking
- Limb salvage data

### Extraction Examples

**Input Text:**
```
Patient underwent right common femoral to below-knee popliteal 
bypass. Pre-op ABI was 0.45. Patient is a current smoker with 
diabetes. Rutherford category 4. Used 6Fr sheath with Perclose 
closure. No complications.
```

**Extracted Fields:**
```python
{
  "arteries_treated": ["right common femoral", "popliteal"],
  "preop_abi": 0.45,
  "smoking_history": "Current",
  "rutherford_status": "Rutherford 4",
  "access_site": "Common Femoral Artery",
  "complications": []
}
```

### Confidence Scoring

The system calculates a confidence score (0-1.0) based on:
- Text length and detail
- Number of extracted fields
- Presence of critical fields (Rutherford, ABI, arteries)

**High Confidence (≥0.75)**: Detailed transcript with many structured fields
**Medium Confidence (0.50-0.74)**: Some fields extracted, manual review recommended
**Low Confidence (<0.50)**: Few fields extracted, significant manual review needed

---

## 🚀 Deployment

### Development Mode

```bash
cd /opt/plaudai_uploader
source venv/bin/activate
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

### Production Mode (systemd)

See [DEPLOYMENT.md](DEPLOYMENT.md) for complete instructions.

Quick summary:
```bash
# Create service
sudo nano /etc/systemd/system/plaudai-uploader.service

# Enable and start
sudo systemctl enable plaudai-uploader
sudo systemctl start plaudai-uploader

# Check status
sudo systemctl status plaudai-uploader
```

### Docker (Optional)

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY backend ./backend
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

```bash
docker build -t plaudai-uploader .
docker run -p 8000:8000 --env-file .env plaudai-uploader
```

---

## 🏗️ Architecture

### System Design

```
User → Frontend (HTML/JS)
         ↓ HTTP
       FastAPI (Python)
         ↓
     Parser → Tagger → Extractor
         ↓
     SQLAlchemy ORM
         ↓
     PostgreSQL (surgical_command_center)
```

### Integration with SCC

PlaudAI Uploader is designed as a **modular component** that:
- Runs independently on separate port (8000)
- Shares the same PostgreSQL database
- Doesn't conflict with existing SCC tables
- Can be embedded in SCC UI later

See [ARCHITECTURE.md](ARCHITECTURE.md) for detailed diagrams and integration patterns.

---

## 🧪 Testing

### Manual Testing

```bash
# Test health
curl http://localhost:8000/health

# Test upload
curl -X POST http://localhost:8000/upload \
  -H "Content-Type: application/json" \
  -d @test_data/sample_transcript.json

# Verify database
psql -U postgres -d surgical_command_center \
  -c "SELECT * FROM voice_transcripts ORDER BY created_at DESC LIMIT 1;"
```

### Unit Tests (Future)

```bash
pytest tests/
```

---

## 🔒 Security

### Current Status (Development)
- ⚠️ No authentication required
- ⚠️ CORS allows all origins
- ⚠️ Credentials in .env file

### Production Requirements
- ✅ JWT authentication
- ✅ SSL/TLS encryption
- ✅ HIPAA-compliant logging
- ✅ Audit trails
- ✅ Data encryption at rest
- ✅ Role-based access control

---

## 🐛 Troubleshooting

### Database Connection Failed

```bash
# Check PostgreSQL is running
sudo systemctl status postgresql

# Test connection
psql -h localhost -U postgres -d surgical_command_center

# Check pg_hba.conf
sudo nano /etc/postgresql/*/main/pg_hba.conf
```

### Port Already in Use

```bash
# Find process
sudo lsof -i :8000

# Kill process
sudo kill -9 <PID>
```

### Import Errors

```bash
# Ensure correct directory
cd /opt/plaudai_uploader

# Activate venv
source venv/bin/activate

# Test import
python -c "from backend import main"
```

### Low Confidence Scores

- Add more detail to transcripts
- Use structured format with markdown headers
- Include specific medical terms and values
- Review `services/parser.py` keyword mappings

---

## 📊 Performance

### Current Capacity
- Single worker: ~100 requests/minute
- Database pool: 5 connections
- Suitable for: <1000 procedures/month

### Scaling
```bash
# Multi-worker mode
uvicorn backend.main:app --workers 4 --host 0.0.0.0 --port 8000

# Load balancing with nginx
upstream plaudai { server 127.0.0.1:8000; server 127.0.0.1:8001; }
```

---

## 🗺️ Roadmap

### Phase 1 (Current)
- ✅ Basic upload and parsing
- ✅ PVI field extraction
- ✅ Web UI
- ✅ REST API

### Phase 2 (Next)
- [ ] Gemini AI enhanced tagging
- [ ] File upload support (PDF, DOCX)
- [ ] Authentication & authorization
- [ ] Advanced search filters

### Phase 3 (Future)
- [ ] SCC UI integration
- [ ] Automated PlaudAI API sync
- [ ] LTFU reminder system
- [ ] Quality metrics dashboard

---

## 🤝 Contributing

### Development Setup

```bash
git clone <repo>
cd plaudai_uploader
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install -r requirements-dev.txt  # Testing tools
```

### Code Style

- Follow PEP 8
- Use type hints
- Document functions with docstrings
- Add unit tests for new features

---

## 📄 License

Proprietary - Internal use only for Surgical Command Center

---

## 📞 Support

### Documentation
- [DEPLOYMENT.md](DEPLOYMENT.md) - Server deployment
- [ARCHITECTURE.md](ARCHITECTURE.md) - System design
- API Docs: `http://localhost:8000/docs`

### Logs
```bash
# Application logs
tail -f logs/plaudai_uploader.log

# Service logs (if using systemd)
sudo journalctl -u plaudai-uploader -f
```

### Database Queries
```sql
-- Check recent uploads
SELECT patient_id, transcript_title, confidence_score, created_at
FROM voice_transcripts
ORDER BY created_at DESC LIMIT 10;

-- View PVI procedures
SELECT patient_id, procedure_date, rutherford_status, arteries_treated
FROM pvi_procedures
ORDER BY procedure_date DESC LIMIT 10;

-- Statistics
SELECT 
  COUNT(*) as total_transcripts,
  AVG(confidence_score) as avg_confidence,
  COUNT(DISTINCT patient_id) as unique_patients
FROM voice_transcripts;
```

---

## 🎉 Acknowledgments

- FastAPI framework
- SQLAlchemy ORM
- PlaudAI for voice recording technology
- SVS VQI for registry standards

---

**Version**: 1.0.0  
**Last Updated**: November 2025  
**Maintainer**: Surgical Command Center Team