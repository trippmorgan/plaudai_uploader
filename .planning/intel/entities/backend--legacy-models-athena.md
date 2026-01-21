---
path: /home/server1/plaudai_uploader/backend/_legacy/models_athena.py
type: model
updated: 2025-01-20
status: active
---

# models_athena.py

## Purpose

Athena EMR integration data models forming a separate append-only data domain for raw EMR data captured from the Athena-Scraper Chrome extension. Implements idempotency via SHA256 hashing for deduplication, HIPAA-compliant audit logging, and structured finding extraction with laterality tracking critical for vascular surgery.

## Exports

- `generate_uuid() -> str` - Generate UUID string for primary keys
- `ClinicalEvent` - Append-only raw EMR event storage with idempotency_key, raw_payload JSONB, patient linkage
- `StructuredFinding` - Extracted clinical values (ABI, TBI, stenosis) with side/laterality and location fields
- `FindingEvidence` - Provenance tracking with text excerpts and surrounding context for clinical validation
- `AthenaDocument` - Document file metadata (PDFs, images) with storage paths
- `IntegrationAuditLog` - HIPAA audit trail tracking all actions (INGEST, PARSE, VIEW, EXPORT, ERROR)

## Dependencies

- [[backend--legacy-db]] - Provides Base declarative class for ORM inheritance

## Used By

TBD

## Notes

ClinicalEvent is NEVER updated or deleted (append-only for audit compliance). idempotency_key = SHA256(patient_id:event_type:sorted_json_payload) prevents duplicates. StructuredFinding.side field is CRITICAL for vascular surgery (left vs right leg findings). patient_id is nullable to allow events before patient creation.
