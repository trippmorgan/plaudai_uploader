---
path: /home/server1/plaudai_uploader/backend/services/shadow_coder/facts_service.py
type: service
updated: 2026-01-25
status: active
---

# facts_service.py

## Purpose

Manages the "Clinical Truth Map" for surgical cases, providing the fact state that drives the coding compliance rules engine. Handles storage, retrieval, and lifecycle of clinical facts extracted from voice notes. Supports fact versioning via supersession (soft deletes), physician verification/attestation, and full audit history tracking.

## Exports

- `FactsService` - Main class for clinical fact management
  - `get_fact_map(case_id): Dict` - Returns current facts keyed by fact_type (latest non-superseded)
  - `get_fact_values(case_id): Dict` - Simplified map of fact_type to value only
  - `add_fact(case_id, fact_type, value, confidence, source_type, ...): Dict` - Adds single fact with metadata
  - `add_facts_batch(case_id, facts, voice_note_id, patient_id): List` - Bulk insert from extraction results
  - `supersede_fact(fact_id, new_fact_id): bool` - Soft-delete a fact when replaced
  - `verify_fact(fact_id, verified_by): bool` - Record physician attestation
  - `get_fact_history(case_id, fact_type): List` - Full audit trail including superseded facts
  - `has_fact(case_id, fact_type, validator): bool` - Check existence with optional validation

## Dependencies

- sqlalchemy - Database ORM for scc_case_facts table operations

## Used By

TBD

## Notes

Uses DISTINCT ON with ordering by createdAt and confidence to resolve latest fact of each type. Source types include: voice_note, manual, ehr_import. Facts are stored as JSONB for flexible value structures.
