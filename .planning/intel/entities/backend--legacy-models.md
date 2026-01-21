---
path: /home/server1/plaudai_uploader/backend/_legacy/models.py
type: model
updated: 2025-01-20
status: active
---

# models.py

## Purpose

Core SQLAlchemy ORM models defining the clinical documentation data structures. Maps Python objects to PostgreSQL tables for patients, voice transcripts, PVI (Peripheral Vascular Intervention) procedures, and AI-generated clinical synopses. Patient is the central entity with cascade delete to all related records.

## Exports

- `Patient` - Patient demographics with athena_mrn as unique identifier, relationships to transcripts, procedures, synopses
- `VoiceTranscript` - Voice transcript storage with raw_transcript, plaud_note, record_category, category_specific_data JSON, tags, confidence_score
- `ClinicalSynopsis` - AI-generated synopsis with structured sections (chief_complaint, HPI, medications, etc.), token tracking, date ranges
- `PVIProcedure` - Comprehensive PVI registry data (60+ fields) for SVS compliance including Rutherford status, ABI/TBI, arteries_treated, complications, 30-day/LTFU outcomes

## Dependencies

- [[backend--legacy-db]] - Provides Base declarative class for ORM inheritance

## Used By

TBD

## Notes

PVIProcedure follows Society for Vascular Surgery data elements for quality reporting. VoiceTranscript stores both raw voice-to-text and PlaudAI-formatted note. JSON columns (tags, category_specific_data, medications) trade query efficiency for flexibility. All timestamps use server_default=func.now().
