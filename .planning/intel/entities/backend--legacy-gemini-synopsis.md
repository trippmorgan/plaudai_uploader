---
path: /home/server1/plaudai_uploader/backend/_legacy/gemini_synopsis.py
type: service
updated: 2025-01-20
status: active
---

# gemini_synopsis.py

## Purpose

AI synthesis engine that aggregates patient data from multiple sources (transcripts, procedures) and uses Google Gemini to generate comprehensive clinical summaries. Implements 24-hour caching to avoid redundant API calls, supports multiple synopsis types, tracks token usage for cost management, and parses AI output into structured sections for frontend display.

## Exports

- `gather_patient_data(db: Session, patient_id: int, days_back: int) -> Dict` - Aggregate demographics, transcripts, procedures for patient
- `calculate_age(dob) -> int` - Birthday-aware age calculation
- `build_synopsis_prompt(patient_data: Dict, synopsis_type: str) -> str` - Construct Gemini prompt with patient context and type-specific instructions
- `generate_clinical_synopsis(db, patient_id, synopsis_type, days_back, force_regenerate) -> ClinicalSynopsis` - Main generation function with caching
- `parse_synopsis_sections(synopsis_text: str) -> Dict[str, str]` - Extract structured sections from AI output
- `get_latest_synopsis(db, patient_id, synopsis_type) -> ClinicalSynopsis` - Query most recent cached synopsis
- `get_all_synopses(db, patient_id) -> List[ClinicalSynopsis]` - Query all patient synopses
- `get_patient_summary(db, mrn: str) -> Dict` - Quick MRN-based lookup with synopsis

## Dependencies

- [[backend--legacy-models]] - Patient, VoiceTranscript, PVIProcedure, ClinicalSynopsis ORM models
- [[backend--legacy-config]] - GOOGLE_API_KEY, GEMINI_MODEL configuration (actually ..config)
- google-generativeai - Google Gemini API client

## Used By

TBD

## Notes

24-hour cache TTL with force_regenerate bypass. Comprehensive synopsis includes 10 sections (CC, HPI, PMH, Meds, Allergies, SH, ROS, PE, A/P, Pending). Cost optimization: limits to 5 transcripts + 3 procedures per synopsis, truncates transcript text to 500 chars.
