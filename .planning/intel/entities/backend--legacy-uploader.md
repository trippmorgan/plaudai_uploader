---
path: /home/server1/plaudai_uploader/backend/_legacy/uploader.py
type: service
updated: 2025-01-20
status: active
---

# uploader.py

## Purpose

Primary data ingestion service orchestrating patient creation, transcript storage, and PVI procedure record generation from PlaudAI voice recordings. Implements upsert semantics for patients (by athena_mrn), automatic PVI field extraction from transcripts, and comprehensive audit logging. Central coordinator for the upload workflow.

## Exports

- `get_or_create_patient(db: Session, patient_data: Dict) -> Patient` - Upsert patient by athena_mrn with demographic update tracking
- `upload_transcript(db: Session, patient_data, raw_transcript, ...) -> Dict` - Main upload function returning patient_id, transcript_id, tags, confidence
- `create_pvi_procedure(db: Session, patient_id, transcript_id, pvi_fields) -> int` - Create PVI procedure from extracted fields
- `batch_upload_transcripts(db: Session, items: list) -> Dict` - Process multiple uploads with partial failure tolerance
- `get_patient_transcripts(db: Session, patient_id) -> list` - Query patient's transcripts
- `get_patient_procedures(db: Session, patient_id) -> list` - Query patient's PVI procedures
- `search_patients(db: Session, search_term) -> list` - Case-insensitive search by name or MRN

## Dependencies

- [[backend--legacy-models]] - Patient, VoiceTranscript, PVIProcedure ORM models
- [[backend-services-parser]] - process_transcript for parsing pipeline (actually ../services/parser.py)

## Used By

TBD

## Notes

Auto-creates PVI procedure when >= 3 fields extracted from transcript. Dual text storage: raw_transcript (unprocessed) and plaud_note (formatted). All operations within single transaction with rollback on failure. Comprehensive logging with emoji prefixes for traceability.
