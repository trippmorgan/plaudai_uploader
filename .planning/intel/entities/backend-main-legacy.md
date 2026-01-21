---
path: /home/server1/plaudai_uploader/backend/main_legacy.py
type: api
updated: 2025-01-20
status: active
---

# main_legacy.py

## Purpose

Full-featured FastAPI application entrypoint for the Albany Vascular AI Clinical System with complete database integration. Provides HTTP API surface for transcript uploads with category-specific Gemini parsing, patient management, clinical synopsis generation, natural language queries, PVI registry integration, EMR chart views, PDF generation, and Athena EMR ingestion. This is the database-integrated version (vs. stateless main.py).

## Exports

- `app` - FastAPI application instance with full endpoint suite
- Endpoints: /upload, /upload-medical-record, /upload-file, /patients, /transcripts, /synopsis/*, /clinical/*, /generate-pdf/*, /stats, /health
- Middleware: request logging with UUID tracing, permissive CORS

## Dependencies

- [[backend--legacy-db]] - Database engine, session factory, init_db, check_connection
- [[backend--legacy-config]] - API_HOST, API_PORT, DEBUG settings (actually .config)
- [[backend--legacy-models]] - Patient, VoiceTranscript, PVIProcedure ORM models
- [[backend--legacy-schemas]] - Pydantic request/response models
- [[backend--legacy-uploader]] - upload_transcript, batch_upload_transcripts, search_patients, etc. (actually .services.uploader)
- [[backend--legacy-gemini-synopsis]] - generate_clinical_synopsis, get_patient_summary (actually .services.gemini_synopsis)
- [[backend-services-parser]] - generate_tags, extract_pvi_fields
- [[backend-services-category-parser]] - parse_by_category, generate_category_summary
- [[backend--legacy-clinical-query]] - process_clinical_query (actually .services.clinical_query)
- [[backend--legacy-telemetry]] - emit_upload_*, emit_patients_queried, emit_clinical_* (actually .services.telemetry)
- [[backend--legacy-routes-ingest]] - Athena integration router

## Used By

TBD

## Notes

Fail-fast startup: refuses to start if database unavailable. Static file serving for frontend (must be last mount). PDF generation creates downloadable medical record documents. Request logging middleware generates unique request IDs for distributed tracing. CORS currently permissive (allow_origins=["*"]) - must be restricted for production.
