# PlaudAI Central Database Schema Reference

> **Version:** 2.1.0
> **Database:** PostgreSQL `surgical_command_center`
> **Last Updated:** 2026-01-21
> **Purpose:** Single source of truth for all integrations (OR Command Center, Athena-Scraper, PlaudAI)

---

## Table of Contents

1. [Connection Information](#1-connection-information)
2. [Quick Reference - All 24 Tables](#2-quick-reference---all-24-tables)
3. [Core Patient & Clinical Tables](#3-core-patient--clinical-tables)
4. [SCC Integration Tables](#4-scc-integration-tables)
5. [Athena EMR Integration Tables](#5-athena-emr-integration-tables)
6. [Operational & Analytics Tables](#6-operational--analytics-tables)
7. [Template & Quality Tables](#7-template--quality-tables)
8. [Enum Types](#8-enum-types)
9. [Demographics Data Entry Contract (ORCC)](#9-demographics-data-entry-contract-orcc)
10. [Query Patterns](#10-query-patterns)
11. [API Contracts](#11-api-contracts)

---

## 1. Connection Information

```bash
# Environment Variables (.env)
DB_HOST=localhost
DB_PORT=5432
DB_NAME=surgical_command_center
DB_USER=scc_user
DB_PASSWORD=scc_password
```

**Connection String:**
```
postgresql://scc_user:scc_password@localhost:5432/surgical_command_center
```

**psql Command:**
```bash
PGPASSWORD=scc_password psql -h localhost -U scc_user -d surgical_command_center
```

---

## 2. Quick Reference - All 24 Tables

| # | Table | Purpose | Owner |
|---|-------|---------|-------|
| 1 | `patients` | Central patient demographics | scc_user |
| 2 | `voice_transcripts` | PlaudAI voice notes | scc_user |
| 3 | `clinical_synopses` | AI-generated clinical summaries | scc_user |
| 4 | `pvi_procedures` | SVS vascular procedure registry | scc_user |
| 5 | `clinical_events` | Raw Athena EMR events (append-only) | scc_user |
| 6 | `structured_findings` | Extracted clinical values (ABI, stenosis) | scc_user |
| 7 | `finding_evidences` | Text provenance for findings | scc_user |
| 8 | `athena_documents` | PDF/image metadata from Athena | scc_user |
| 9 | `integration_audit_log` | HIPAA audit trail | scc_user |
| 10 | `scc_patients` | SCC-specific patient records (UUID-based) | scc_user |
| 11 | `scc_voice_notes` | SCC voice note processing queue | scc_user |
| 12 | `scc_case_facts` | Extracted facts from voice notes | scc_user |
| 13 | `scc_prompt_instances` | Clinical decision support prompts | scc_user |
| 14 | `procedures` | Real-time procedure documentation | scc_user |
| 15 | `transcriptions` | Whisper transcription logs | scc_user |
| 16 | `realtime_sessions` | Real-time transcription sessions | scc_user |
| 17 | `template_definitions` | Procedure template library | scc_user |
| 18 | `template_usage` | Template usage tracking | scc_user |
| 19 | `extracted_fields` | Fields extracted from templates | scc_user |
| 20 | `corrections` | User corrections to extracted data | scc_user |
| 21 | `problematic_templates` | Flagged low-quality templates | scc_user |
| 22 | `quality_metrics_daily` | Daily quality aggregates | scc_user |
| 23 | `system_performance` | GPU/processing metrics | scc_user |
| 24 | `audit_logs` | Comprehensive HIPAA audit log | scc_user |

---

## 3. Core Patient & Clinical Tables

### 3.1 patients

**Purpose:** Central patient demographics. All clinical data links here. This is the PRIMARY patient table.

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `id` | INTEGER | NO | auto | Primary key |
| `athena_mrn` | VARCHAR(20) | NO | | **UNIQUE** - Athena MRN (primary lookup key) |
| `mrn` | VARCHAR(255) | YES | | Alternate MRN field |
| `first_name` | VARCHAR(100) | YES | | First name |
| `last_name` | VARCHAR(100) | YES | | Last name |
| `middle_name` | VARCHAR(255) | YES | | Middle name |
| `dob` | DATE | NO | | Date of birth (legacy field) |
| `date_of_birth` | DATE | YES | | Date of birth (new field) |
| `age` | INTEGER | YES | | Calculated age |
| `gender` | VARCHAR(20) | YES | 'unknown' | Gender (use birth_sex for clinical) |
| `birth_sex` | VARCHAR(10) | YES | | Biological sex: M, F, Other |
| `race` | VARCHAR(50) | YES | | Race |
| `ethnicity` | VARCHAR(255) | YES | | Ethnicity |
| `primary_language` | VARCHAR(255) | YES | 'English' | Primary language |
| `marital_status` | VARCHAR(50) | YES | | Marital status |
| `phone_primary` | VARCHAR(255) | YES | | Primary phone |
| `phone_secondary` | VARCHAR(255) | YES | | Secondary phone |
| `email` | VARCHAR(255) | YES | | Email address |
| `address_line1` | VARCHAR(255) | YES | | Address line 1 |
| `address_line2` | VARCHAR(255) | YES | | Address line 2 |
| `city` | VARCHAR(255) | YES | | City |
| `state` | VARCHAR(255) | YES | | State |
| `zip_code` | VARCHAR(10) | YES | | ZIP code |
| `country` | VARCHAR(255) | YES | 'USA' | Country |
| `center_site_location` | VARCHAR(100) | YES | | Facility location |
| `insurance_type` | VARCHAR(50) | YES | | Insurance category |
| `insurance_provider` | VARCHAR(255) | YES | | Insurance company |
| `insurance_policy_number` | VARCHAR(255) | YES | | Policy number |
| `insurance_group_number` | VARCHAR(255) | YES | | Group number |
| `primary_physician` | VARCHAR(255) | YES | | Primary physician |
| `allergies` | TEXT | YES | | Allergies (text) |
| `current_medications` | TEXT | YES | | Current medications |
| `medical_history` | TEXT | YES | | Medical history |
| `emergency_contact_name` | VARCHAR(255) | YES | | Emergency contact name |
| `emergency_contact_phone` | VARCHAR(255) | YES | | Emergency contact phone |
| `emergency_contact_relationship` | VARCHAR(255) | YES | | Relationship |
| `ssn_last_four` | VARCHAR(4) | YES | | Last 4 SSN digits |
| `notes` | TEXT | YES | | General notes |
| `active` | BOOLEAN | YES | true | Active patient flag |
| `created_by` | VARCHAR(255) | YES | | Created by user |
| `last_updated_by` | VARCHAR(255) | YES | | Last updated by |
| `created_at` | TIMESTAMP | YES | now() | Created timestamp |
| `updated_at` | TIMESTAMP | YES | now() | Updated timestamp |
| `createdAt` | TIMESTAMPTZ | YES | now() | Sequelize created |
| `updatedAt` | TIMESTAMPTZ | YES | now() | Sequelize updated |

**Indexes:**
- `patients_pkey` - PRIMARY KEY (id)
- `patients_athena_mrn_key` - UNIQUE (athena_mrn)
- `idx_patients_mrn` - (athena_mrn)
- `idx_patients_name` - (last_name, first_name)
- `idx_patients_name_search` - GIN trigram on full name
- `idx_patients_dob` - (dob)

**Foreign Key References (other tables point here):**
- `voice_transcripts.patient_id` → CASCADE DELETE
- `clinical_synopses.patient_id` → CASCADE DELETE
- `pvi_procedures.patient_id` → CASCADE DELETE
- `clinical_events.patient_id` (optional)
- `structured_findings.patient_id`
- `athena_documents.patient_id`

---

### 3.2 voice_transcripts

**Purpose:** Stores PlaudAI voice recordings with raw and formatted transcripts.

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `id` | INTEGER | NO | auto | Primary key |
| `patient_id` | INTEGER | NO | | FK → patients.id |
| `plaud_recording_id` | VARCHAR(100) | YES | | PlaudAI recording ID |
| `raw_transcript` | TEXT | NO | | Unprocessed voice-to-text |
| `plaud_note` | TEXT | YES | | PlaudAI formatted note |
| `recording_duration` | FLOAT | YES | | Duration in seconds |
| `recording_date` | TIMESTAMP | YES | | When recorded |
| `visit_date` | TIMESTAMP | YES | now() | Clinical visit date |
| `visit_type` | VARCHAR(100) | YES | | Office visit, Procedure, etc. |
| `transcript_title` | VARCHAR(200) | YES | | Human-readable title |
| `record_category` | VARCHAR(50) | YES | | operative_note, imaging, lab_result, office_visit |
| `record_subtype` | VARCHAR(100) | YES | | CT Abdomen, Carotid Duplex, etc. |
| `category_specific_data` | JSON | YES | | Parsed structured data |
| `tags` | JSONB | YES | | Auto-generated medical tags |
| `confidence_score` | FLOAT | YES | | 0.0-1.0 parsing confidence |
| `is_processed` | BOOLEAN | YES | false | Processing complete flag |
| `processing_notes` | TEXT | YES | | Processing status messages |
| `created_at` | TIMESTAMP | YES | now() | Created |
| `updated_at` | TIMESTAMP | YES | now() | Updated |

**Constraints:**
- `voice_transcripts_confidence_score_check` - CHECK (0.0 <= confidence_score <= 1.0)

**Indexes:**
- Full-text search on `raw_transcript` and `plaud_note`
- GIN index on `tags` for JSONB queries
- Index on `record_category` for filtering

---

### 3.3 clinical_synopses

**Purpose:** AI-generated clinical summaries using Google Gemini.

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `id` | INTEGER | NO | auto | Primary key |
| `patient_id` | INTEGER | NO | | FK → patients.id |
| `transcript_id` | INTEGER | YES | | FK → voice_transcripts.id |
| `synopsis_text` | TEXT | NO | | Full AI-generated summary |
| `synopsis_type` | VARCHAR(50) | NO | | comprehensive, visit_summary, problem_list, procedure_summary |
| `data_sources` | JSONB | YES | | Records used for generation |
| `source_date_range` | JSONB | YES | | {start, end} dates |
| `ai_model` | VARCHAR(50) | YES | | gemini-2.0-flash-exp |
| `generation_timestamp` | TIMESTAMP | YES | now() | When generated |
| `tokens_used` | INTEGER | YES | | Token count |
| `chief_complaint` | TEXT | YES | | Chief complaint |
| `history_present_illness` | TEXT | YES | | HPI |
| `past_medical_history` | JSONB | YES | | PMH list |
| `medications` | JSONB | YES | | Medications array |
| `allergies` | JSONB | YES | | Allergies array |
| `social_history` | TEXT | YES | | Social history |
| `family_history` | TEXT | YES | | Family history |
| `review_of_systems` | JSONB | YES | | ROS |
| `physical_exam` | TEXT | YES | | PE findings |
| `assessment_plan` | TEXT | YES | | A&P |
| `follow_up_needed` | BOOLEAN | YES | false | Follow-up required |
| `follow_up_date` | DATE | YES | | Scheduled follow-up |
| `pending_tests` | JSONB | YES | | Pending orders |
| `created_at` | TIMESTAMP | YES | now() | Created |
| `updated_at` | TIMESTAMP | YES | now() | Updated |

---

### 3.4 pvi_procedures

**Purpose:** SVS-compliant Peripheral Vascular Intervention registry (80+ fields).

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `id` | INTEGER | NO | auto | Primary key |
| `patient_id` | INTEGER | NO | | FK → patients.id |
| `transcript_id` | INTEGER | YES | | FK → voice_transcripts.id |
| `procedure_date` | DATE | NO | | Date of procedure |
| `surgeon_name` | VARCHAR(100) | YES | | Primary surgeon |
| `assistant_names` | TEXT | YES | | Assisting staff |
| **Demographics** |
| `smoking_history` | VARCHAR(50) | YES | | Never, Former, Current |
| `comorbidities` | JSONB | YES | | List of conditions |
| `stress_testing` | VARCHAR(50) | YES | | Stress test status |
| `functional_status` | VARCHAR(50) | YES | | Functional capacity |
| `living_status` | VARCHAR(50) | YES | | Living situation |
| `ambulation_status` | VARCHAR(50) | YES | | Mobility status |
| `creatinine` | FLOAT | YES | | Serum creatinine |
| `transfer_from_other_center` | BOOLEAN | YES | | Transfer flag |
| **Prior Medications** |
| `prior_antiplatelet` | BOOLEAN | YES | | On antiplatelet |
| `prior_statin` | BOOLEAN | YES | | On statin |
| `prior_beta_blocker` | BOOLEAN | YES | | On beta blocker |
| `prior_ace_inhibitor` | BOOLEAN | YES | | On ACE inhibitor |
| `prior_arb` | BOOLEAN | YES | | On ARB |
| `prior_anticoagulation` | BOOLEAN | YES | | On anticoagulation |
| `prior_cilostazol` | BOOLEAN | YES | | On cilostazol |
| **Clinical History** |
| `indication` | VARCHAR(100) | YES | | Acute/Chronic Rutherford |
| `rutherford_status` | VARCHAR(50) | YES | | Rutherford 0-6 |
| `aneurysm_vs_occlusive` | VARCHAR(50) | YES | | Disease type |
| `prior_inflow_intervention` | BOOLEAN | YES | | Prior aortoiliac |
| `prior_wifi` | VARCHAR(50) | YES | | Prior infrainguinal |
| `prior_amputation` | BOOLEAN | YES | | Prior amputation |
| `preop_abi` | FLOAT | YES | | Preoperative ABI |
| `preop_tbi` | FLOAT | YES | | Preoperative TBI |
| **Procedure Details** |
| `covid_status` | VARCHAR(50) | YES | | COVID status |
| `access_site` | VARCHAR(100) | YES | | Access location |
| `sheath_size` | VARCHAR(20) | YES | | Sheath French size |
| `closure_method` | VARCHAR(100) | YES | | Closure technique |
| `concomitant_endarterectomy` | BOOLEAN | YES | | Combined open |
| `radiation_exposure` | FLOAT | YES | | Fluoroscopy mGy |
| `contrast_volume` | FLOAT | YES | | Contrast mL |
| `nephropathy_prophylaxis` | BOOLEAN | YES | | Prophylaxis given |
| **Treatment** |
| `arteries_treated` | JSONB | YES | | Treated arteries array |
| `arteries_locations` | JSONB | YES | | Anatomical locations |
| `tasc_grade` | VARCHAR(10) | YES | | TASC A/B/C/D |
| `treated_length` | FLOAT | YES | | Lesion length cm |
| `occlusion_length` | FLOAT | YES | | Occlusion length cm |
| `calcification_grade` | VARCHAR(50) | YES | | Calcification severity |
| `device_details` | JSONB | YES | | Devices used |
| `treatment_success` | BOOLEAN | YES | | Technical success |
| `treatment_failure_reason` | TEXT | YES | | Failure reason |
| `pharmacologic_intervention` | JSONB | YES | | Intra-procedural meds |
| `mechanical_thrombectomy` | BOOLEAN | YES | | Thrombectomy |
| `embolic_protection_used` | BOOLEAN | YES | | EPD used |
| `reentry_device_used` | BOOLEAN | YES | | Reentry device |
| `final_technical_result` | VARCHAR(50) | YES | | Final result |
| **Complications** |
| `complications` | JSONB | YES | | Complications array |
| `remote_lesion_dissection` | BOOLEAN | YES | | Non-target dissection |
| `target_lesion_dissection` | BOOLEAN | YES | | Target dissection |
| `perforation_treatment` | TEXT | YES | | Perforation management |
| `thrombosis_treatment` | TEXT | YES | | Thrombosis management |
| `pseudoaneurysm_treatment` | TEXT | YES | | Pseudoaneurysm management |
| `amputation_level` | VARCHAR(50) | YES | | Amputation level |
| `amputation_planning` | TEXT | YES | | Amputation details |
| **Discharge** |
| `disposition_status` | VARCHAR(50) | YES | | Discharge disposition |
| `discharge_medications` | JSONB | YES | | Discharge meds |
| `mortality` | BOOLEAN | YES | false | In-hospital mortality |
| `mortality_date` | DATE | YES | | Death date |
| **30-Day Follow-up** |
| `followup_30day_captured` | BOOLEAN | YES | false | 30-day collected |
| `readmission_30day` | BOOLEAN | YES | | Readmission |
| `readmission_reason` | TEXT | YES | | Readmission reason |
| `reintervention_30day` | BOOLEAN | YES | | Reintervention |
| `reintervention_type` | TEXT | YES | | Reintervention type |
| **Long-term Follow-up** |
| `ltfu_captured` | BOOLEAN | YES | false | LTFU collected |
| `ltfu_months` | INTEGER | YES | | Months since procedure |
| `ltfu_smoking_status` | VARCHAR(50) | YES | | Current smoking |
| `ltfu_living_status` | VARCHAR(50) | YES | | Current living |
| `ltfu_mortality` | BOOLEAN | YES | | Death since discharge |
| `ltfu_medications` | JSONB | YES | | Current medications |
| `ltfu_ambulation` | VARCHAR(50) | YES | | Current ambulation |
| `ltfu_ipsilateral_symptoms` | TEXT | YES | | Ipsilateral symptoms |
| `ltfu_patency_documentation` | TEXT | YES | | Patency documentation |
| `ltfu_ipsilateral_abi` | FLOAT | YES | | Follow-up ABI |
| `ltfu_ipsilateral_tbi` | FLOAT | YES | | Follow-up TBI |
| `ltfu_reintervention` | BOOLEAN | YES | | Late reintervention |
| `ltfu_reintervention_type` | TEXT | YES | | Late reintervention type |
| `ltfu_amputation_since_discharge` | BOOLEAN | YES | | Amputation since |
| `created_at` | TIMESTAMP | YES | now() | Created |
| `updated_at` | TIMESTAMP | YES | now() | Updated |

---

## 4. SCC Integration Tables

### 4.1 scc_patients

**Purpose:** SCC-specific patient records with UUID primary keys (for OR Command Center).

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `id` | UUID | NO | | Primary key |
| `mrn` | VARCHAR(255) | NO | | **UNIQUE** MRN |
| `first_name` | VARCHAR(255) | NO | | First name |
| `last_name` | VARCHAR(255) | NO | | Last name |
| `middle_name` | VARCHAR(255) | YES | | Middle name |
| `date_of_birth` | DATE | NO | | Date of birth |
| `age` | INTEGER | YES | | Age |
| `gender` | ENUM | YES | 'unknown' | male, female, other, unknown |
| `phone_primary` | VARCHAR(255) | YES | | Primary phone |
| `phone_secondary` | VARCHAR(255) | YES | | Secondary phone |
| `email` | VARCHAR(255) | YES | | Email |
| `address_line1` | VARCHAR(255) | YES | | Address |
| `address_line2` | VARCHAR(255) | YES | | Address 2 |
| `city` | VARCHAR(255) | YES | | City |
| `state` | VARCHAR(255) | YES | | State |
| `zip_code` | VARCHAR(255) | YES | | ZIP |
| `country` | VARCHAR(255) | YES | 'USA' | Country |
| `emergency_contact_name` | VARCHAR(255) | YES | | Emergency contact |
| `emergency_contact_phone` | VARCHAR(255) | YES | | Emergency phone |
| `emergency_contact_relationship` | VARCHAR(255) | YES | | Relationship |
| `insurance_provider` | VARCHAR(255) | YES | | Insurance |
| `insurance_policy_number` | VARCHAR(255) | YES | | Policy # |
| `insurance_group_number` | VARCHAR(255) | YES | | Group # |
| `primary_physician` | VARCHAR(255) | YES | | Primary MD |
| `allergies` | TEXT | YES | | Allergies |
| `current_medications` | TEXT | YES | | Medications |
| `medical_history` | TEXT | YES | | History |
| `primary_language` | VARCHAR(255) | YES | 'English' | Language |
| `race` | VARCHAR(255) | YES | | Race |
| `ethnicity` | VARCHAR(255) | YES | | Ethnicity |
| `marital_status` | ENUM | YES | | Marital status |
| `ssn_last_four` | VARCHAR(4) | YES | | SSN last 4 |
| `active` | BOOLEAN | YES | true | Active flag |
| `notes` | TEXT | YES | | Notes |
| `created_by` | VARCHAR(255) | YES | | Created by |
| `last_updated_by` | VARCHAR(255) | YES | | Updated by |
| `createdAt` | TIMESTAMPTZ | NO | now() | Created |
| `updatedAt` | TIMESTAMPTZ | NO | now() | Updated |

---

### 4.2 scc_voice_notes

**Purpose:** SCC voice note processing queue with deduplication.

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `id` | UUID | NO | | Primary key |
| `transcript` | TEXT | NO | | Voice transcript text |
| `summary` | TEXT | YES | | AI-generated summary |
| `content_hash` | VARCHAR(64) | NO | | **UNIQUE** SHA256 deduplication |
| `audio_ref` | VARCHAR(500) | YES | | Audio file reference |
| `mrn` | VARCHAR(50) | YES | | Patient MRN |
| `patient_name` | VARCHAR(200) | YES | | Patient name |
| `captured_at` | TIMESTAMPTZ | YES | | Recording timestamp |
| `status` | ENUM | YES | 'pending' | pending, processing, extracted, failed |
| `provenance` | JSONB | YES | {} | Source metadata |
| `extracted_facts_raw` | JSONB | YES | | Raw extracted data |
| `error_log` | JSONB | YES | | Error details |
| `createdAt` | TIMESTAMPTZ | NO | | Created |
| `updatedAt` | TIMESTAMPTZ | NO | | Updated |

---

### 4.3 scc_case_facts

**Purpose:** Structured facts extracted from voice notes for clinical decision support.

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `id` | UUID | NO | | Primary key |
| `case_id` | UUID | NO | | Case/procedure ID |
| `patient_id` | UUID | YES | | FK → scc_patients.id |
| `fact_type` | VARCHAR(100) | NO | | Type of fact (diagnosis, medication, etc.) |
| `value_json` | JSONB | NO | | Structured fact data |
| `confidence` | FLOAT | YES | 1.0 | Extraction confidence |
| `source_type` | ENUM | YES | 'voice_note' | voice_note, ehr_import, manual, lab_result, imaging |
| `voice_note_id` | UUID | YES | | FK → scc_voice_notes.id |
| `source_ref` | JSONB | YES | | Source reference |
| `verified` | BOOLEAN | YES | false | User verified |
| `verified_by` | VARCHAR(100) | YES | | Verified by user |
| `verified_at` | TIMESTAMPTZ | YES | | Verification timestamp |
| `superseded_by` | UUID | YES | | Replaced by fact ID |
| `superseded_at` | TIMESTAMPTZ | YES | | Superseded timestamp |
| `createdAt` | TIMESTAMPTZ | NO | | Created |
| `updatedAt` | TIMESTAMPTZ | NO | | Updated |

---

### 4.4 procedures

**Purpose:** Real-time vascular procedure documentation with arterial findings.

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `id` | UUID | NO | | Primary key |
| `patient_name` | VARCHAR(255) | NO | | Patient name |
| `mrn` | VARCHAR(255) | NO | | MRN |
| `dob` | DATE | YES | | Date of birth |
| `age` | INTEGER | YES | | Age |
| `procedure_type` | VARCHAR(255) | NO | 'Lower Extremity Angiogram' | Procedure type |
| `procedure_date` | TIMESTAMPTZ | YES | | Procedure date |
| `surgeon` | VARCHAR(255) | YES | | Surgeon |
| `procedure_side` | ENUM | YES | | left, right, bilateral |
| `access_site` | VARCHAR(255) | YES | | Access site |
| `access_guide` | VARCHAR(255) | YES | | Access guide |
| `sheath_size` | VARCHAR(255) | YES | | Sheath size |
| `closure_method` | VARCHAR(255) | YES | | Closure method |
| **Arterial Findings (JSONB)** |
| `common_iliac` | JSONB | YES | {} | Common iliac findings |
| `external_iliac` | JSONB | YES | {} | External iliac findings |
| `common_femoral` | JSONB | YES | {} | Common femoral findings |
| `superficial_femoral` | JSONB | YES | {} | SFA findings |
| `profunda` | JSONB | YES | {} | Profunda findings |
| `popliteal` | JSONB | YES | {} | Popliteal findings |
| `anterior_tibial` | JSONB | YES | {} | Anterior tibial findings |
| `posterior_tibial` | JSONB | YES | {} | Posterior tibial findings |
| `peroneal` | JSONB | YES | {} | Peroneal findings |
| `tibial_peroneal_trunk` | JSONB | YES | {} | TPT findings |
| **Complications** |
| `complications` | JSONB | YES | [] | Complications list |
| `puncture_site_hematoma` | BOOLEAN | YES | false | Hematoma |
| `hematoma_severity` | ENUM | YES | 'none' | none, minor, moderate |
| **Other** |
| `stent_planned` | BOOLEAN | YES | | Stent planned |
| `patent_outflow_proximal` | JSONB | YES | [] | Proximal outflow |
| `patent_outflow_distal` | JSONB | YES | [] | Distal outflow |
| `procedure_duration` | INTEGER | YES | | Duration minutes |
| `voice_commands_used` | INTEGER | YES | 0 | Voice commands count |
| `status` | ENUM | YES | 'draft' | draft, in_progress, completed, finalized |
| `ultralinq_data` | JSONB | YES | {} | UltraLinQ data |
| `athena_data` | JSONB | YES | {} | Athena data |
| `mirror_ledger_hash` | VARCHAR(255) | YES | | Audit hash |
| `narrative` | TEXT | YES | | Procedure narrative |
| `created_by` | VARCHAR(255) | YES | | Created by |
| `modified_by` | VARCHAR(255) | YES | | Modified by |
| `createdAt` | TIMESTAMPTZ | NO | | Created |
| `updatedAt` | TIMESTAMPTZ | NO | | Updated |

---

## 5. Athena EMR Integration Tables

### 5.1 clinical_events

**Purpose:** Append-only storage for raw Athena EMR data. **NEVER UPDATE OR DELETE.**

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `id` | VARCHAR(36) | NO | | UUID primary key |
| `patient_id` | INTEGER | YES | | FK → patients.id (optional) |
| `athena_patient_id` | VARCHAR(50) | YES | | Athena MRN |
| `event_type` | VARCHAR(50) | YES | | medication, problem, vital, lab, allergy, encounter |
| `event_subtype` | VARCHAR(50) | YES | | active, historical, search |
| `raw_payload` | JSON | NO | | **Complete unmodified Athena response** |
| `source_system` | VARCHAR(50) | YES | | 'athena' |
| `source_endpoint` | TEXT | YES | | Intercepted API endpoint |
| `idempotency_key` | VARCHAR(128) | YES | | **UNIQUE** SHA256 deduplication hash |
| `captured_at` | TIMESTAMP | YES | | When event occurred |
| `ingested_at` | TIMESTAMP | YES | | When stored |
| `confidence` | FLOAT | YES | | Classification confidence |
| `indexer_version` | VARCHAR(20) | YES | | Classifier version |

**Deduplication Formula:**
```python
idempotency_key = SHA256(f"{athena_patient_id}:{event_type}:{json.dumps(payload, sort_keys=True)}")[:64]
```

---

### 5.2 structured_findings

**Purpose:** Extracted clinical values (ABI, stenosis, etc.).

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `id` | INTEGER | NO | auto | Primary key |
| `patient_id` | INTEGER | YES | | FK → patients.id |
| `athena_patient_id` | VARCHAR(50) | YES | | Athena MRN |
| `source_event_id` | VARCHAR(36) | YES | | FK → clinical_events.id |
| `finding_type` | VARCHAR(50) | YES | | ABI, TBI, Stenosis, AneurysmSize, Rutherford |
| `value` | VARCHAR(100) | YES | | Extracted value (string) |
| `unit` | VARCHAR(20) | YES | | mm, %, ratio, cm |
| `side` | VARCHAR(20) | YES | | **CRITICAL:** Left, Right, Bilateral |
| `location` | VARCHAR(100) | YES | | SFA, Popliteal, Carotid, Aorta |
| `confidence` | FLOAT | YES | | Extraction confidence |
| `parser_version` | VARCHAR(20) | YES | | Parser version |
| `created_at` | TIMESTAMP | YES | | Created |

---

### 5.3 finding_evidences

**Purpose:** Text provenance showing source text for each finding.

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `id` | INTEGER | NO | auto | Primary key |
| `finding_id` | INTEGER | YES | | FK → structured_findings.id |
| `text_excerpt` | TEXT | YES | | Exact matched text |
| `context_before` | TEXT | YES | | ~50 chars before |
| `context_after` | TEXT | YES | | ~50 chars after |
| `source_field` | VARCHAR(100) | YES | | note_text, result_value |

---

### 5.4 athena_documents

**Purpose:** Document file metadata from Athena.

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `id` | VARCHAR(36) | NO | | UUID primary key |
| `patient_id` | INTEGER | YES | | FK → patients.id |
| `athena_patient_id` | VARCHAR(50) | YES | | Athena MRN |
| `source_event_id` | VARCHAR(36) | YES | | FK → clinical_events.id |
| `title` | VARCHAR(255) | YES | | Document title |
| `document_type` | VARCHAR(50) | YES | | cta, mri, ultrasound, surgical, pathology |
| `file_name` | VARCHAR(255) | YES | | Original filename |
| `mime_type` | VARCHAR(100) | YES | | MIME type |
| `storage_path` | TEXT | YES | | Local file path |
| `athena_url` | TEXT | YES | | Original Athena URL |
| `document_date` | TIMESTAMP | YES | | Document date |
| `created_at` | TIMESTAMP | YES | | Created |

---

## 6. Operational & Analytics Tables

### 6.1 transcriptions

**Purpose:** Whisper transcription logs.

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `id` | UUID | NO | | Primary key |
| `timestamp` | TIMESTAMP | NO | now() | Transcription time |
| `audio_duration` | FLOAT | NO | | Audio seconds |
| `processing_time` | FLOAT | NO | | Processing seconds |
| `word_count` | INTEGER | NO | | Word count |
| `confidence_avg` | FLOAT | NO | | Average confidence |
| `text` | TEXT | NO | | Transcription text |
| `patient_id` | VARCHAR(50) | YES | | Patient reference |
| `procedure_id` | VARCHAR(50) | YES | | Procedure reference |
| `surgeon_id` | VARCHAR(50) | YES | | Surgeon reference |
| `model_used` | VARCHAR(50) | YES | 'medium.en' | Whisper model |
| `language` | VARCHAR(10) | YES | 'en' | Language |
| `created_at` | TIMESTAMP | NO | now() | Created |
| `updated_at` | TIMESTAMP | NO | now() | Updated |

---

### 6.2 realtime_sessions

**Purpose:** Real-time transcription session tracking.

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `session_id` | UUID | NO | uuid_generate_v4() | Primary key |
| `user_id` | VARCHAR(50) | NO | | User identifier |
| `started_at` | TIMESTAMP | NO | now() | Session start |
| `ended_at` | TIMESTAMP | YES | | Session end |
| `total_chunks_processed` | INTEGER | YES | 0 | Chunks processed |
| `total_duration` | FLOAT | YES | | Total duration |
| `final_transcription` | TEXT | YES | | Final transcript |
| `avg_chunk_confidence` | FLOAT | YES | | Average confidence |
| `created_at` | TIMESTAMP | NO | now() | Created |

---

### 6.3 audit_logs (Comprehensive HIPAA)

**Purpose:** Full HIPAA-compliant audit trail.

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `id` | UUID | NO | | Primary key |
| `action` | ENUM | NO | | CREATE, READ, UPDATE, DELETE, LOGIN, LOGOUT, EXPORT, PRINT, SEARCH, VIEW, VOICE_COMMAND, FIELD_UPDATE |
| `resource_type` | ENUM | NO | | patient, procedure, imaging, document, user, system, report |
| `resource_id` | VARCHAR(255) | YES | | Resource identifier |
| `mrn` | VARCHAR(255) | YES | | Patient MRN |
| `user_id` | VARCHAR(255) | YES | 'system' | Acting user |
| `username` | VARCHAR(255) | YES | | Username |
| `user_role` | VARCHAR(255) | YES | | User role |
| `source` | ENUM | YES | 'web_ui' | web_ui, api, websocket, dragon_voice, system, import, integration |
| `field_name` | VARCHAR(255) | YES | | Changed field |
| `old_value` | JSONB | YES | | Previous value |
| `new_value` | JSONB | YES | | New value |
| `before_snapshot` | JSONB | YES | | Full record before |
| `after_snapshot` | JSONB | YES | | Full record after |
| `ip_address` | VARCHAR(255) | YES | | Client IP |
| `user_agent` | VARCHAR(255) | YES | | User agent |
| `session_id` | VARCHAR(255) | YES | | Session ID |
| `correlation_id` | VARCHAR(255) | YES | | Request correlation |
| `endpoint` | VARCHAR(255) | YES | | API endpoint |
| `http_method` | VARCHAR(255) | YES | | HTTP method |
| `success` | BOOLEAN | YES | true | Success flag |
| `error_message` | TEXT | YES | | Error details |
| `duration_ms` | INTEGER | YES | | Request duration |
| `description` | TEXT | YES | | Human description |
| `metadata` | JSONB | YES | | Additional data |
| `timestamp` | TIMESTAMPTZ | NO | | Event timestamp |

---

## 7. Template & Quality Tables

### 7.1 template_definitions

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `id` | UUID | NO | uuid_generate_v4() | Primary key |
| `template_key` | VARCHAR(100) | NO | | Template identifier |
| `version` | INTEGER | NO | 1 | Version number |
| `template_text` | TEXT | NO | | Template content |
| `template_source` | VARCHAR(20) | NO | | static, dynamic, ai_generated |
| `created_by` | VARCHAR(50) | YES | | Creator |
| `created_at` | TIMESTAMP | NO | now() | Created |
| `is_active` | BOOLEAN | YES | true | Active flag |
| `usage_count` | INTEGER | YES | 0 | Usage count |
| `avg_confidence` | FLOAT | YES | | Average confidence |
| `avg_corrections` | FLOAT | YES | | Average corrections |

---

### 7.2 quality_metrics_daily

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `date` | DATE | NO | | Primary key |
| `total_transcriptions` | INTEGER | YES | 0 | Daily transcriptions |
| `avg_transcription_confidence` | FLOAT | YES | | Average confidence |
| `avg_transcription_time` | FLOAT | YES | | Average time |
| `total_transcription_words` | INTEGER | YES | 0 | Total words |
| `total_template_usage` | INTEGER | YES | 0 | Template uses |
| `avg_template_confidence` | FLOAT | YES | | Template confidence |
| `avg_template_time` | FLOAT | YES | | Template time |
| `dynamic_template_count` | INTEGER | YES | 0 | Dynamic templates |
| `static_template_count` | INTEGER | YES | 0 | Static templates |
| `total_corrections` | INTEGER | YES | 0 | Corrections |
| `notes_with_corrections` | INTEGER | YES | 0 | Notes corrected |
| `correction_rate` | FLOAT | YES | | Correction rate |
| `active_users` | INTEGER | YES | 0 | Active users |
| `updated_at` | TIMESTAMP | NO | now() | Updated |

---

## 8. Enum Types

### 8.1 Gender
```sql
enum_patients_gender: male, female, other, unknown
```

### 8.2 Marital Status
```sql
enum_patients_marital_status: single, married, divorced, widowed, separated, unknown, other
```

### 8.3 Procedure Side
```sql
enum_procedures_procedure_side: left, right, bilateral
```

### 8.4 Procedure Status
```sql
enum_procedures_status: draft, in_progress, completed, finalized
```

### 8.5 Hematoma Severity
```sql
enum_procedures_hematoma_severity: none, minor, moderate
```

### 8.6 Voice Note Status
```sql
enum_scc_voice_notes_status: pending, processing, extracted, failed
```

### 8.7 Case Fact Source Type
```sql
enum_scc_case_facts_source_type: voice_note, ehr_import, manual, lab_result, imaging
```

### 8.8 Prompt Instance Status
```sql
enum_scc_prompt_instances_status: active, snoozed, resolved, dismissed, expired
```

### 8.9 Prompt Instance Severity
```sql
enum_scc_prompt_instances_severity: info, warn, block
```

### 8.10 Prompt Resolution Type
```sql
enum_scc_prompt_instances_resolution_type: fact_added, manual_dismiss, attestation, order_placed, auto_expired
```

### 8.11 Audit Log Action
```sql
enum_audit_logs_action: CREATE, READ, UPDATE, DELETE, LOGIN, LOGOUT, EXPORT, PRINT, SEARCH, VIEW, VOICE_COMMAND, FIELD_UPDATE
```

### 8.12 Audit Log Resource Type
```sql
enum_audit_logs_resource_type: patient, procedure, imaging, document, user, system, report
```

### 8.13 Audit Log Source
```sql
enum_audit_logs_source: web_ui, api, websocket, dragon_voice, system, import, integration
```

---

## 9. Demographics Data Entry Contract (ORCC)

### 9.1 Patient Create/Update (for OR Command Center)

**Use `scc_patients` table for UUID-based operations or `patients` table for integer-based.**

```json
{
  "mrn": "12345678",
  "first_name": "John",
  "last_name": "Smith",
  "middle_name": "Robert",
  "date_of_birth": "1955-03-15",
  "age": 70,
  "gender": "male",
  "phone_primary": "518-555-0100",
  "phone_secondary": "518-555-0101",
  "email": "john.smith@email.com",
  "address_line1": "123 Main Street",
  "address_line2": "Apt 4B",
  "city": "Albany",
  "state": "NY",
  "zip_code": "12180",
  "country": "USA",
  "emergency_contact_name": "Jane Smith",
  "emergency_contact_phone": "518-555-0200",
  "emergency_contact_relationship": "Spouse",
  "insurance_provider": "Medicare",
  "insurance_policy_number": "1EG4-TE5-MK72",
  "insurance_group_number": "GRP123456",
  "primary_physician": "Dr. Mary Jones",
  "allergies": "Penicillin, Sulfa drugs",
  "current_medications": "Aspirin 81mg daily, Metoprolol 25mg BID",
  "medical_history": "HTN, CAD s/p stent 2020, PAD",
  "primary_language": "English",
  "race": "White",
  "ethnicity": "Non-Hispanic",
  "marital_status": "married",
  "ssn_last_four": "1234",
  "active": true,
  "notes": "VIP patient - CEO of local company"
}
```

### 9.2 Validation Rules

| Field | Required | Type | Format/Constraints |
|-------|----------|------|-------------------|
| `mrn` | YES | String | Max 255 chars, UNIQUE |
| `first_name` | YES | String | Max 255 chars |
| `last_name` | YES | String | Max 255 chars |
| `middle_name` | NO | String | Max 255 chars |
| `date_of_birth` | YES | Date | YYYY-MM-DD, must be in past |
| `age` | NO | Integer | Auto-calculated preferred |
| `gender` | NO | Enum | male, female, other, unknown |
| `phone_primary` | NO | String | Max 255 chars |
| `phone_secondary` | NO | String | Max 255 chars |
| `email` | NO | String | Valid email format |
| `address_line1` | NO | String | Max 255 chars |
| `address_line2` | NO | String | Max 255 chars |
| `city` | NO | String | Max 255 chars |
| `state` | NO | String | 2-letter code preferred |
| `zip_code` | NO | String | 5 or 9 digits |
| `country` | NO | String | Default 'USA' |
| `emergency_contact_name` | NO | String | Max 255 chars |
| `emergency_contact_phone` | NO | String | Max 255 chars |
| `emergency_contact_relationship` | NO | String | Max 255 chars |
| `insurance_provider` | NO | String | Max 255 chars |
| `insurance_policy_number` | NO | String | Max 255 chars |
| `insurance_group_number` | NO | String | Max 255 chars |
| `primary_physician` | NO | String | Max 255 chars |
| `allergies` | NO | Text | Free text |
| `current_medications` | NO | Text | Free text |
| `medical_history` | NO | Text | Free text |
| `primary_language` | NO | String | Default 'English' |
| `race` | NO | String | Max 255 chars |
| `ethnicity` | NO | String | Max 255 chars |
| `marital_status` | NO | Enum | single, married, divorced, widowed, separated, unknown, other |
| `ssn_last_four` | NO | String | Exactly 4 digits |
| `active` | NO | Boolean | Default true |
| `notes` | NO | Text | Free text |

### 9.3 Patient Lookup Patterns

**By MRN (Primary):**
```sql
SELECT * FROM scc_patients WHERE mrn = '12345678';
-- OR
SELECT * FROM patients WHERE athena_mrn = '12345678';
```

**By Name:**
```sql
SELECT * FROM scc_patients
WHERE LOWER(last_name) LIKE LOWER('%smith%')
  AND LOWER(first_name) LIKE LOWER('%john%');
```

**By DOB + Name (for verification):**
```sql
SELECT * FROM scc_patients
WHERE date_of_birth = '1955-03-15'
  AND last_name ILIKE '%smith%';
```

---

## 10. Query Patterns

### 10.1 Get Patient with All Related Data

```sql
SELECT
  p.id, p.athena_mrn, p.first_name, p.last_name, p.dob,
  COUNT(DISTINCT vt.id) AS transcript_count,
  COUNT(DISTINCT pvi.id) AS procedure_count,
  COUNT(DISTINCT cs.id) AS synopsis_count,
  COUNT(DISTINCT ce.id) AS athena_event_count
FROM patients p
LEFT JOIN voice_transcripts vt ON vt.patient_id = p.id
LEFT JOIN pvi_procedures pvi ON pvi.patient_id = p.id
LEFT JOIN clinical_synopses cs ON cs.patient_id = p.id
LEFT JOIN clinical_events ce ON ce.patient_id = p.id
WHERE p.athena_mrn = '12345678'
GROUP BY p.id;
```

### 10.2 Get Athena Events by Type

```sql
SELECT id, event_type, event_subtype, captured_at,
       raw_payload->>'medicationname' AS medication_name
FROM clinical_events
WHERE athena_patient_id = '12345678'
  AND event_type = 'medication'
ORDER BY captured_at DESC;
```

### 10.3 Get Low ABI Patients

```sql
SELECT DISTINCT
  p.athena_mrn, p.first_name, p.last_name,
  sf.value AS abi_value, sf.side
FROM structured_findings sf
JOIN patients p ON p.id = sf.patient_id
WHERE sf.finding_type = 'ABI'
  AND CAST(sf.value AS FLOAT) < 0.9
ORDER BY CAST(sf.value AS FLOAT) ASC;
```

### 10.4 Check Duplicate Before Insert

```sql
SELECT id FROM clinical_events
WHERE idempotency_key = 'computed_hash_here';
```

---

## 11. API Contracts

### 11.1 Create/Update Patient (ORCC)

**Endpoint:** `POST /api/patients` or `PUT /api/patients/:id`

**Request:**
```json
{
  "mrn": "12345678",
  "first_name": "John",
  "last_name": "Smith",
  "date_of_birth": "1955-03-15",
  "gender": "male",
  "phone_primary": "518-555-0100",
  "address_line1": "123 Main Street",
  "city": "Albany",
  "state": "NY",
  "zip_code": "12180"
}
```

**Response:**
```json
{
  "status": "success",
  "patient_id": "uuid-or-integer",
  "mrn": "12345678",
  "message": "Patient created successfully"
}
```

### 11.2 Search Patients

**Endpoint:** `GET /api/patients?search=<term>`

**Response:**
```json
{
  "patients": [
    {
      "id": "uuid",
      "mrn": "12345678",
      "first_name": "John",
      "last_name": "Smith",
      "date_of_birth": "1955-03-15",
      "age": 70
    }
  ],
  "total": 1
}
```

### 11.3 Get Patient Detail

**Endpoint:** `GET /api/patients/:mrn`

**Response:**
```json
{
  "demographics": { ... },
  "procedures": [ ... ],
  "voice_notes": [ ... ],
  "clinical_events": { ... },
  "latest_synopsis": "..."
}
```

---

## Document Info

**Maintainers:** Albany Vascular Development Team
**Last Updated:** 2026-01-21
**Tables Documented:** 24
**Enum Types Documented:** 13
