---
path: /home/server1/plaudai_uploader/backend/routes/orcc.py
type: api
updated: 2026-01-21
status: active
---

# orcc.py

## Purpose

Provides REST API endpoints for OR Command Center (ORCC) integration with the Surgical Command Center database. Enables external systems to query and update surgical procedures, manage patient records, and track surgical readiness status through a CRUD interface. Supports filtering procedures by surgical status, location, and patient MRN.

## Exports

- `router` - FastAPI APIRouter with prefix "/api" containing all ORCC endpoints
- `ProcedureBase` - Pydantic model for procedure creation with fields: mrn, patient_name, procedure_type, surgical_status, barriers, cardiology_clearance, stress_test_status
- `ProcedureUpdate` - Pydantic model for PATCH updates supporting partial procedure modifications
- `ProcedureResponse` - Pydantic response model with procedure details and timestamps
- `PatientBase` - Pydantic model for patient creation with demographics, contact info, insurance, and medical history
- `PatientResponse` - Pydantic response model with patient details and active status
- `get_db()` - Dependency injection function providing database sessions

### API Endpoints:

- `GET /api/procedures` - List procedures with filters (surgical_status, patient_mrn, scheduled_location, status)
- `GET /api/procedures/{id}` - Get single procedure with arterial findings detail
- `PATCH /api/procedures/{id}` - Update procedure fields (barriers, clearance, status, etc.)
- `GET /api/patients` - List/search patients by name or MRN
- `GET /api/patients/{mrn}` - Get patient by MRN with related procedures
- `POST /api/patients` - Create new patient record
- `GET /api/orcc/status` - Health check with procedure and patient counts

## Dependencies

- fastapi - Web framework for REST API (APIRouter, HTTPException, Query, Depends)
- pydantic - Request/response validation models
- sqlalchemy - Database connection and raw SQL execution
- os - Environment variable access for DATABASE_URL construction
- logging - Request and error logging
- datetime - Timestamp handling for responses
- uuid - UUID type handling for procedure IDs

## Used By

TBD

## Notes

Uses raw SQL queries with text() rather than ORM models, enabling direct access to the SCC database schema (procedures, scc_patients tables). Surgical status workflow: workup -> near_ready -> ready -> scheduled. Supports PostgreSQL enums for surgical_status, stress_test_status, and procedure_side. The database connection is separate from the main PlaudAI database session factory to support independent ORCC deployment.
