---
path: /home/server1/plaudai_uploader/backend/_legacy/routes/ingest.py
type: api
updated: 2025-01-20
status: active
---

# ingest.py

## Purpose

Ingestion gateway API for all clinical data flowing from the Athena-Scraper Chrome extension. Provides idempotent event ingestion with SHA256 deduplication, automatic patient linking by MRN, HIPAA audit logging, and bidirectional clinical data fetch for instant display in WebUI when opening a patient chart.

## Exports

- `router` - FastAPI APIRouter with prefix="/ingest" and tag="Athena Integration"
- `AthenaEventPayload` - Pydantic schema for incoming Athena events (athena_patient_id, event_type, payload, captured_at)
- `IngestResponse` - Response schema with status, event_id, message
- `generate_idempotency_key(patient_id, event_type, payload) -> str` - SHA256 hash for deduplication
- `log_audit(db, action, resource_type, resource_id, details, error)` - HIPAA audit logging helper
- `parse_timestamp(timestamp_str) -> datetime` - ISO timestamp parser with fallback
- `ingest_athena_event(payload, background_tasks, db) -> IngestResponse` - POST /ingest/athena main handler
- `get_patient_events(athena_patient_id, event_type, limit, db)` - GET /ingest/events/{id} for debugging
- `get_ingestion_stats(db)` - GET /ingest/stats for monitoring
- `get_patient_clinical(athena_mrn, db)` - GET /ingest/clinical/{mrn} bidirectional fetch
- `health_check()` - GET /ingest/health simple health check

## Dependencies

- [[backend--legacy-db]] - get_db session dependency
- [[backend--legacy-models]] - Patient model for auto-linking
- [[backend--legacy-models-athena]] - ClinicalEvent, StructuredFinding, FindingEvidence, IntegrationAuditLog
- [[backend--legacy-telemetry]] - emit_ingest_received, emit_ingest_processed, emit_clinical_fetch, etc. (actually ..services.telemetry)

## Used By

TBD

## Notes

Raw payload stored EXACTLY as received (no transformation) for audit compliance and future re-parsing. Auto-linking to patients is best-effort (events stored even if patient missing). Atomic transactions: event + audit log committed together. Clinical fetch endpoint organizes events by type (medications, problems, labs, vitals, etc.).
