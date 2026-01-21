---
path: /home/server1/plaudai_uploader/backend/_legacy/schemas.py
type: model
updated: 2025-01-20
status: active
---

# schemas.py

## Purpose

Pydantic request/response validation models for the FastAPI endpoints. Provides type-safe serialization and input validation for patient data, transcript uploads, clinical synopses, PVI procedures, and batch operations. Enforces constraints like min/max length, required fields, and nested structure validation.

## Exports

- `PatientBase`, `PatientCreate`, `PatientResponse` - Patient CRUD schemas with demographics
- `TranscriptBase`, `TranscriptUpload`, `TranscriptResponse` - Transcript schemas including record_category, record_subtype
- `SynopsisRequest`, `SynopsisResponse` - Synopsis generation request (type, days_back) and response (full text, sections)
- `PatientSummary` - Quick patient lookup response with synopsis preview
- `PVIProcedureBase`, `PVIProcedureCreate`, `PVIProcedureResponse` - Comprehensive PVI registry field schemas (50+ fields)
- `UploadResponse` - Standard upload result with patient_id, transcript_id, tags, warnings
- `BatchUploadItem`, `BatchUploadRequest`, `BatchUploadResponse` - Batch processing (1-50 items)

## Dependencies

- pydantic - Data validation and serialization

## Used By

TBD

## Notes

All Response models use from_attributes=True for SQLAlchemy ORM compatibility. TranscriptUpload includes both patient info and transcript data for single-request uploads. PVI schemas mirror the extensive ORM model fields.
