# PlaudAI Uploader - Quick Reference Card

## 🚀 Essential Commands

### Start Server
```bash
# Development
cd /opt/plaudai_uploader
source venv/bin/activate
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000

# Production (systemd)
sudo systemctl start plaudai-uploader
sudo systemctl status plaudai-uploader
```

### Stop Server
```bash
# Development: Ctrl+C

# Production
sudo systemctl stop plaudai-uploader
```

### View Logs
```bash
# Application logs
tail -f /opt/plaudai_uploader/logs/plaudai_uploader.log

# Service logs (systemd)
sudo journalctl -u plaudai-uploader -f
```

### Restart Service
```bash
sudo systemctl restart plaudai-uploader
```

---

## 🌐 URLs

| Resource | URL |
|----------|-----|
| API Root | http://server1-70TR000LUX:8000/ |
| API Docs | http://server1-70TR000LUX:8000/docs |
| Health Check | http://server1-70TR000LUX:8000/health |
| Statistics | http://server1-70TR000LUX:8000/stats |
| Upload | http://server1-70TR000LUX:8000/upload |

---

## 📊 Database Quick Queries

```sql
-- Connect
psql -U postgres -d surgical_command_center

-- View recent transcripts
SELECT 
    id, patient_id, transcript_title, 
    confidence_score, created_at 
FROM voice_transcripts 
ORDER BY created_at DESC 
LIMIT 10;

-- Count by patient
SELECT 
    patient_id, 
    COUNT(*) as transcript_count
FROM voice_transcripts 
GROUP BY patient_id 
ORDER BY transcript_count DESC;

-- Average confidence
SELECT 
    ROUND(AVG(confidence_score) * 100, 1) as avg_confidence
FROM voice_transcripts;

-- PVI procedures today
SELECT 
    procedure_date, patient_id, 
    surgeon_name, arteries_treated
FROM pvi_procedures 
WHERE procedure_date = CURRENT_DATE;
```

---

## 🔧 Troubleshooting

### Database Connection Failed
```bash
# Test connection
psql -h localhost -U postgres -d surgical_command_center

# Check PostgreSQL status
sudo systemctl status postgresql

# Restart PostgreSQL
sudo systemctl restart postgresql
```

### Port Already in Use
```bash
# Find process on port 8000
sudo lsof -i :8000

# Kill process
sudo kill -9 <PID>
```

### Service Won't Start
```bash
# Check service status
sudo systemctl status plaudai-uploader

# View recent errors
sudo journalctl -u plaudai-uploader -n 50

# Check configuration
cat /opt/plaudai_uploader/.env

# Test manually
cd /opt/plaudai_uploader
source venv/bin/activate
python -c "from backend.db import check_connection; check_connection()"
```

---

## 📝 API Examples

### Upload Transcript (cURL)
```bash
curl -X POST http://localhost:8000/upload \
  -H "Content-Type: application/json" \
  -d '{
    "first_name": "John",
    "last_name": "Doe",
    "dob": "1960-05-15",
    "athena_mrn": "MRN123456",
    "transcript_text": "Patient with right leg claudication..."
  }'
```

### Upload Transcript (Python)
```python
import requests

response = requests.post('http://localhost:8000/upload', json={
    "first_name": "Jane",
    "last_name": "Smith",
    "dob": "1975-08-20",
    "athena_mrn": "MRN789012",
    "transcript_text": "Femoral artery stenosis..."
})

print(response.json())
```

### Get Patient Info
```bash
curl http://localhost:8000/patients/1
```

### Search Patients
```bash
curl "http://localhost:8000/patients?search=smith&limit=10"
```

### Get Statistics
```bash
curl http://localhost:8000/stats
```

---

## 🏥 Medical Tags Reference

### Vascular Conditions
- `pad` - Peripheral arterial disease
- `cli` - Critical limb ischemia
- `claudication` - Intermittent claudication
- `aneurysm` - Aneurysmal disease

### Anatomical Locations
- `infrarenal`, `femoral`, `popliteal`, `tibial`, `profunda`

### Procedures
- `angioplasty`, `stent`, `atherectomy`, `thrombectomy`, `bypass`

### Findings
- `occlusion`, `stenosis`, `dissection`, `thrombus`, `calcification`

### Complications
- `perforation`, `hemorrhage`, `ischemia`

---

## 📋 PVI Field Extraction

### What Gets Extracted Automatically

| Field | Example Text | Extracted Value |
|-------|-------------|-----------------|
| Smoking Status | "current smoker" | smoking_history: "Current" |
| Rutherford | "rutherford 4" | rutherford_status: "Rutherford 4" |
| ABI | "ABI 0.45" | preop_abi: 0.45 |
| TBI | "TBI 0.3" | preop_tbi: 0.3 |
| Creatinine | "creatinine 1.2" | creatinine: 1.2 |
| Contrast | "contrast 150 ml" | contrast_volume: 150.0 |
| Access | "femoral access" | access_site: "Common Femoral Artery" |
| TASC Grade | "TASC C" | tasc_grade: "TASC C" |
| Arteries | "right SFA" | arteries_treated: ["right sfa"] |

---

## 🔐 Security Checklist

- [ ] Changed default PostgreSQL password
- [ ] .env file has correct permissions (600)
- [ ] Firewall configured (port 8000)
- [ ] Running as non-root user
- [ ] Logs directory writable
- [ ] Database backups configured
- [ ] SSL/TLS enabled (production)
- [ ] Authentication added (production)

---

## 📞 Common Issues & Solutions

| Issue | Solution |
|-------|----------|
| "Module not found" | `cd /opt/plaudai_uploader && source venv/bin/activate` |
| "Database connection refused" | Check PostgreSQL: `sudo systemctl status postgresql` |
| "Port 8000 in use" | Find and kill: `sudo lsof -i :8000` then `kill -9 <PID>` |
| "Permission denied" | Check ownership: `ls -la /opt/plaudai_uploader` |
| Low confidence scores | Add more detail to transcripts, use structured format |
| Service won't start | Check logs: `sudo journalctl -u plaudai-uploader -n 50` |

---

## 🗂️ File Locations

```
/opt/plaudai_uploader/
├── .env                      ← Configuration
├── backend/
│   ├── main.py              ← API routes
│   ├── models.py            ← Database schema
│   └── services/
│       ├── parser.py        ← Text parsing
│       └── uploader.py      ← Upload logic
├── frontend/
│   └── index.html           ← Web UI
├── logs/
│   └── plaudai_uploader.log ← Application logs
└── venv/                     ← Python environment
```

---

## 🎯 Performance Tuning

### Increase Workers
```bash
# Edit systemd service
sudo nano /etc/systemd/system/plaudai-uploader.service

# Change to:
ExecStart=.../uvicorn ... --workers 4

# Reload and restart
sudo systemctl daemon-reload
sudo systemctl restart plaudai-uploader
```

### Database Connection Pool
```python
# In backend/db.py
engine = create_engine(
    DATABASE_URL,
    pool_size=10,        # Increase from 5
    max_overflow=20,     # Increase from 10
)
```

---

## 💡 Pro Tips

1. **Use structured transcript format** with markdown headers (##) for better parsing
2. **Include numeric values** (ABI, contrast, etc.) for automatic extraction
3. **Specify laterality** (right/left) for arteries to improve accuracy
4. **Review low confidence uploads** manually
5. **Check logs regularly** for parsing issues
6. **Backup database** before major updates
7. **Use batch upload** for multiple transcripts
8. **Test uploads** with sample data first

---

## 🔄 Update Procedure

```bash
# Stop service
sudo systemctl stop plaudai-uploader

# Backup
cp -r /opt/plaudai_uploader /opt/plaudai_uploader.backup

# Update code
cd /opt/plaudai_uploader
# (upload new files)

# Update dependencies
source venv/bin/activate
pip install -r requirements.txt

# Restart
sudo systemctl start plaudai-uploader
sudo systemctl status plaudai-uploader
```

---

## 📞 Quick Help

```bash
# Test database connection
python3 -c "from backend.db import check_connection; print(check_connection())"

# Test API endpoint
curl http://localhost:8000/health

# Check Python packages
pip list

# View environment
cat .env

# Check service status
sudo systemctl status plaudai-uploader

# Restart everything
sudo systemctl restart postgresql
sudo systemctl restart plaudai-uploader
```

---

**Quick Access**: Keep this file open for daily operations!
**Full Docs**: See README.md, DEPLOYMENT.md, and ARCHITECTURE.md