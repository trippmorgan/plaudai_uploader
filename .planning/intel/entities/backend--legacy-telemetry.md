---
path: /home/server1/plaudai_uploader/backend/_legacy/telemetry.py
type: service
updated: 2025-01-20
status: active
---

# telemetry.py

## Purpose

Telemetry bridge for sending application events to the Medical Mirror Observer system for AI-powered analysis and pattern detection. Provides non-blocking, fire-and-forget event emission with graceful degradation when Observer is unreachable. Supports correlation IDs for tracing related events across the request lifecycle.

## Exports

- `emit(stage, action, data, success, correlation_id) -> str` - Main async event emitter returning correlation ID
- `emit_sync(stage, action, data, success, correlation_id) -> str` - Synchronous wrapper for non-async contexts
- `emit_upload_received(has_patient_info, record_type, mrn) -> str` - Convenience for upload start
- `emit_upload_processed(correlation_id, patient_id, transcript_id, confidence, category, tags_count) -> str` - Convenience for upload success
- `emit_upload_failed(correlation_id, error) -> str` - Convenience for upload failure
- `emit_patients_queried(result_count, query_type) -> str` - Convenience for patient queries
- `emit_clinical_query(query_length, patient_found) -> str` - Convenience for AI query start
- `emit_clinical_response(correlation_id, response_length, data_sources) -> str` - Convenience for AI query response
- `emit_ingest_received(event_type, has_patient_link) -> str` - Convenience for Athena ingest
- `emit_ingest_processed(correlation_id, event_type, status) -> str` - Convenience for ingest completion
- `emit_clinical_fetch(athena_mrn) -> str` - Convenience for bidirectional data fetch
- `emit_clinical_fetch_success(correlation_id, patient_id, event_count, duration_ms) -> str` - Convenience for fetch success

## Dependencies

- [[backend--legacy-config]] - OBSERVER_URL configuration (actually ..config)
- httpx - Async HTTP client for event delivery

## Used By

TBD

## Notes

2-second timeout prevents blocking application flow. No PHI sent to Observer (only counts, types, IDs). Event stages: upload, query, ai-query, ingest, synopsis, plaud-fetch. Graceful degradation logs warnings but never raises exceptions.
