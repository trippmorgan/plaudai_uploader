# PlaudAI EMR Integration Guide

## 🏥 Overview

This system transforms **PlaudAI voice recordings** into a **structured Electronic Medical Record (EMR)** with AI-powered clinical synopsis generation for point-of-care use.

### The Complete Flow

```
📱 PlaudAI Recording
    ↓ (voice captured)
Raw Transcript + Formatted Note
    ↓ (upload to system)
PostgreSQL Database
    ├─ Tagged by Name, MRN, DOB
    ├─ Linked to all patient data
    └─ Searchable & retrievable
    ↓ (AI processing)
Gemini AI Analysis
    ↓ (generates)
Clinical Synopsis
    └─ Ready for clinical use
```

---

## 📊 Database Architecture

### Patient-Centric Design

All data is **anchored to the patient** using three identifiers:

1. **Name** (`first_name` + `last_name`)
2. **Medical Record Number** (`athena_mrn`) - Primary key for deduplication
3. **Date of Birth** (`dob`)

### Data Tables

```
patients
├─ Demographics (name, MRN, DOB, sex, race)
├─ Contact info (zip code, location)
└─ Timestamps (created, updated)

voice_transcripts
├─ raw_transcript (raw voice-to-text)
├─ plaud_note (PlaudAI's formatted note)
├─ recording metadata (duration, date, ID)
├─ visit info (type, date)
├─ tags (auto-generated medical tags)
└─ Links to: patient, procedures, synopsis

pvi_procedures
├─ Structured vascular procedure data
├─ All SVS VQI registry fields
└─ Links to: patient, transcript

clinical_synopses
├─ AI-generated comprehensive summaries
├─ Structured sections (HPI, assessment, plan)
├─ Data source tracking
└─ Links to: patient, transcript
```

---

## 🎯 Clinical Use Cases

### Use Case 1: **Office Visit Documentation**

**Scenario**: Patient comes for follow-up visit

```python
# 1. Record visit with PlaudAI
# 2. Upload to system
POST /upload
{
  "first_name": "John",
  "last_name": "Doe", 
  "dob": "1960-05-15",
  "athena_mrn": "MRN123456",
  "raw_transcript": "Patient returns for follow-up...",
  "plaud_note": "## Follow-up Visit\nPatient doing well...",
  "visit_type": "Office Visit",
  "recording_date": "2025-11-11T14:30:00"
}

# 3. System automatically:
#    - Links to existing patient (or creates new)
#    - Extracts medical tags
#    - Identifies PVI fields
#    - Stores both raw and formatted notes
```

### Use Case 2: **Pre-Procedure Review**

**Scenario**: Need to review patient before vascular procedure

```python
# Quick lookup by MRN
GET /clinical/patient-summary/MRN123456

Response:
{
  "patient": {
    "name": "John Doe",
    "mrn": "MRN123456",
    "dob": "1960-05-15",
    "age": 65
  },
  "synopsis": "65yo M with hx PAD, s/p right SFA angioplasty...",
  "synopsis_date": "2025-11-10T08:00:00",
  "has_recent_synopsis": true
}
```

### Use Case 3: **Comprehensive Clinical Summary**

**Scenario**: Need full patient summary from all available data

```python
# Generate AI synopsis from last year of data
POST /synopsis/generate/42
{
  "synopsis_type": "comprehensive",
  "days_back": 365
}

Response:
{
  "synopsis_text": "
    CHIEF COMPLAINT: Bilateral leg claudication
    
    HISTORY OF PRESENT ILLNESS:
    65-year-old male with long-standing peripheral arterial 
    disease presents for continued management. Patient reports
    worsening right leg claudication at 2 blocks...
    
    PAST MEDICAL HISTORY:
    - Peripheral arterial disease
    - Hypertension
    - Hyperlipidemia
    - Type 2 Diabetes Mellitus
    - Former smoker (quit 2020)
    
    PROCEDURES:
    - 2025-06-15: Right SFA angioplasty with drug-eluting stent
      Technical success, no complications
    - 2024-11-20: Diagnostic bilateral lower extremity angiogram
    
    MEDICATIONS:
    - Aspirin 81mg daily
    - Clopidogrel 75mg daily
    - Atorvastatin 80mg daily
    - Metformin 1000mg BID
    
    ASSESSMENT AND PLAN:
    1. PAD - Rutherford 3, s/p right SFA intervention
       - Continue dual antiplatelet therapy
       - Check ABIs today
       - Consider left leg intervention if symptoms worsen
    2. Diabetes - well controlled
    3. Follow up in 3 months
  "
}
```

---

## 🔍 Retrieving Patient Data

### Method 1: By MRN (Fastest for Clinical Use)

```bash
# Get comprehensive patient summary
curl http://server1:8000/clinical/patient-summary/MRN123456

# Returns:
# - Demographics
# - Latest clinical synopsis
# - Synopsis freshness indicator
```

### Method 2: By Patient ID

```bash
# Get all transcripts
GET /patients/42/transcripts

# Get all procedures  
GET /patients/42/procedures

# Get all synopses
GET /synopsis/patient/42
```

### Method 3: Search by Name

```bash
# Search patients
GET /patients?search=john+doe&limit=10

# Returns list of matching patients with IDs
```

---

## 🤖 AI Clinical Synopsis Generation

### How It Works

1. **Data Gathering**: System collects all patient data
   - All voice transcripts (raw + formatted notes)
   - All procedures with outcomes
   - Demographics and history
   - Configurable time range (default: 1 year)

2. **AI Processing**: Gemini AI analyzes and synthesizes
   - Reads PlaudAI raw transcripts for context
   - Uses PlaudAI formatted notes for structure
   - Incorporates procedure data
   - Applies clinical documentation standards

3. **Structured Output**: Generates organized synopsis
   - Standard medical sections (HPI, PMH, etc.)
   - Problem-oriented assessment
   - Clear follow-up plan
   - Stored in database for retrieval

### Synopsis Types

| Type | Description | Use Case |
|------|-------------|----------|
| `comprehensive` | Full clinical summary with all sections | New patient, pre-op clearance |
| `visit_summary` | Summary of latest encounter only | Quick review, handoff |
| `problem_list` | Active problems with status | Problem-oriented charting |
| `procedure_summary` | Recent procedures and outcomes | Pre-procedure planning |

### Generation Example

```python
import requests

# Generate comprehensive synopsis
response = requests.post(
    'http://server1:8000/synopsis/generate/42',
    json={
        "synopsis_type": "comprehensive",
        "days_back": 365,
        "force_regenerate": False  # Use cached if < 24hrs old
    }
)

synopsis = response.json()
print(synopsis['synopsis_text'])
```

### Caching Strategy

- Synopses are cached for **24 hours**
- Set `force_regenerate=True` to override cache
- Each synopsis tracks data sources used
- Token usage logged for cost monitoring

---

## 📋 Clinical Workflow Integration

### Morning Clinic Prep

```bash
# Generate synopses for today's patients
for mrn in $(cat todays_patients.txt); do
    curl -X POST http://server1:8000/synopsis/generate/patient \
         -H "Content-Type: application/json" \
         -d "{\"mrn\": \"$mrn\", \"synopsis_type\": \"comprehensive\"}"
done
```

### During Patient Encounter

```python
# Quick lookup during visit
def get_patient_info(mrn):
    response = requests.get(
        f'http://server1:8000/clinical/patient-summary/{mrn}'
    )
    summary = response.json()
    
    print(f"Patient: {summary['patient']['name']}")
    print(f"Age: {summary['patient']['age']}")
    print(f"\nClinical Summary:")
    print(summary['synopsis'])
    
    if not summary['has_recent_synopsis']:
        print("\n⚠️ Synopsis >7 days old - consider regenerating")
```

### Post-Visit Documentation

```python
# Upload PlaudAI recording from visit
def upload_visit_note(mrn, raw_transcript, plaud_note):
    patient = get_patient_by_mrn(mrn)
    
    requests.post('http://server1:8000/upload', json={
        "first_name": patient['first_name'],
        "last_name": patient['last_name'],
        "dob": patient['dob'],
        "athena_mrn": mrn,
        "raw_transcript": raw_transcript,
        "plaud_note": plaud_note,
        "visit_type": "Office Visit",
        "recording_date": datetime.now().isoformat()
    })
```

---

## 🔐 Data Security & PHI Compliance

### Patient Identifiers

All data is **properly tagged and linked**:

✅ **Patient Name** - Indexed for searching  
✅ **MRN** - Unique constraint, primary lookup  
✅ **Date of Birth** - Verification & age calculation  
✅ **Timestamps** - All data creation/update tracked

### HIPAA Considerations

Current system (development):
- ⚠️ No encryption at rest
- ⚠️ No authentication required
- ⚠️ Logs may contain PHI

**For production EMR use, implement:**
- ✅ TLS/SSL encryption in transit
- ✅ Database encryption at rest
- ✅ Authentication (JWT/OAuth)
- ✅ Audit logging (who accessed what/when)
- ✅ Role-based access control
- ✅ PHI redaction in logs
- ✅ Regular security audits
- ✅ Backup encryption

---

## 📊 Example Clinical Queries

### Get All Data for Patient

```sql
-- Connect to database
psql -U postgres -d surgical_command_center

-- Get complete patient record
SELECT 
    p.first_name || ' ' || p.last_name as patient_name,
    p.athena_mrn,
    p.dob,
    COUNT(DISTINCT vt.id) as total_transcripts,
    COUNT(DISTINCT pvi.id) as total_procedures,
    COUNT(DISTINCT cs.id) as total_synopses,
    MAX(vt.recording_date) as last_visit
FROM patients p
LEFT JOIN voice_transcripts vt ON vt.patient_id = p.id
LEFT JOIN pvi_procedures pvi ON pvi.patient_id = p.id
LEFT JOIN clinical_synopses cs ON cs.patient_id = p.id
WHERE p.athena_mrn = 'MRN123456'
GROUP BY p.id, p.first_name, p.last_name, p.athena_mrn, p.dob;
```

### Find Patients Needing Follow-up

```sql
-- Patients with follow-up due
SELECT 
    p.athena_mrn,
    p.first_name || ' ' || p.last_name as patient_name,
    cs.follow_up_date,
    cs.pending_tests
FROM patients p
JOIN clinical_synopses cs ON cs.patient_id = p.id
WHERE cs.follow_up_needed = TRUE
  AND cs.follow_up_date <= CURRENT_DATE + INTERVAL '7 days'
ORDER BY cs.follow_up_date;
```

### Recent PlaudAI Uploads

```sql
-- Last 10 PlaudAI transcripts
SELECT 
    p.athena_mrn,
    p.first_name || ' ' || p.last_name as patient_name,
    vt.recording_date,
    vt.visit_type,
    vt.transcript_title,
    LENGTH(vt.plaud_note) as note_length,
    vt.confidence_score
FROM voice_transcripts vt
JOIN patients p ON p.id = vt.patient_id
ORDER BY vt.recording_date DESC
LIMIT 10;
```

---

## 🚀 Quick Start for Clinical Use

### 1. Upload PlaudAI Recording

```bash
curl -X POST http://server1:8000/upload \
  -H "Content-Type: application/json" \
  -d '{
    "first_name": "Jane",
    "last_name": "Smith",
    "dob": "1970-03-20",
    "athena_mrn": "MRN789012",
    "raw_transcript": "Patient presents with...",
    "plaud_note": "## Office Visit\n...",
    "visit_type": "Office Visit"
  }'
```

### 2. Generate Clinical Synopsis

```bash
# Get patient ID from upload response, then:
curl -X POST http://server1:8000/synopsis/generate/42 \
  -H "Content-Type: application/json" \
  -d '{
    "synopsis_type": "comprehensive",
    "days_back": 365
  }'
```

### 3. Retrieve for Clinical Use

```bash
# Quick lookup by MRN
curl http://server1:8000/clinical/patient-summary/MRN789012
```

---

## 💡 Best Practices

### PlaudAI Recording Tips

1. **Start with patient identifiers**
   - State name, MRN, DOB at beginning
   - Helps with verification

2. **Use structured format**
   - PlaudAI's formatted notes work best
   - Gemini extracts more accurately from organized content

3. **Include key details**
   - Medications
   - Allergies
   - Assessment and plan
   - Follow-up instructions

### Database Management

1. **Regular synopsis updates**
   - Regenerate after significant new data
   - Before major clinical decisions
   - At scheduled intervals (weekly/monthly)

2. **Data quality**
   - Review low confidence scores
   - Manually verify AI-generated content
   - Update structured fields as needed

3. **Backup strategy**
   - Daily database backups
   - Test restore procedures
   - Offsite backup storage

---

## 🔄 Integration with Other Systems

### Athena Health Integration

```python
# Sync with Athena - pull patient demographics
def sync_from_athena(mrn):
    # Get from Athena API
    athena_patient = athena_api.get_patient(mrn)
    
    # Update in our system
    requests.post('http://server1:8000/patients', json={
        "athena_mrn": mrn,
        "first_name": athena_patient['firstname'],
        "last_name": athena_patient['lastname'],
        "dob": athena_patient['dob'],
        # ... other fields
    })
```

### PACS/Imaging Integration

```python
# Link imaging studies to transcripts
def link_imaging_to_visit(transcript_id, study_id):
    # Store study reference in transcript metadata
    # Allows AI synopsis to reference imaging
    pass
```

---

## 📞 Clinical Support

### Common Questions

**Q: How long does synopsis generation take?**  
A: 5-15 seconds depending on data volume

**Q: Can I edit AI-generated synopses?**  
A: Current version stores as-is. Future: add manual editing capability

**Q: What if PlaudAI note is missing?**  
A: System uses raw transcript instead. May have lower confidence.

**Q: How do I find a patient if I don't know their MRN?**  
A: Use search endpoint: `GET /patients?search=john+doe`

**Q: Can multiple people access same patient simultaneously?**  
A: Yes, PostgreSQL handles concurrent access

---

## ✅ Validation Checklist

Before clinical use:

- [ ] All patient identifiers correctly tagged (name, MRN, DOB)
- [ ] PlaudAI transcripts uploading successfully
- [ ] Tags extracting correctly from transcripts
- [ ] AI synopsis generation working with Gemini API
- [ ] Data retrievable by MRN
- [ ] Database backups configured
- [ ] SSL/TLS enabled (production)
- [ ] Authentication configured (production)
- [ ] Test with sample patient data
- [ ] Verify AI synopsis accuracy with clinical staff

---

**Ready for Clinical Use**: Once deployed and validated, this system provides a complete EMR solution for PlaudAI voice recordings with AI-powered clinical intelligence.