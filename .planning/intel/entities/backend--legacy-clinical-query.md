---
path: /home/server1/plaudai_uploader/backend/_legacy/clinical_query.py
type: service
updated: 2025-01-20
status: active
---

# clinical_query.py

## Purpose

Natural language interface enabling clinicians to ask questions about patients in plain English and receive AI-synthesized answers from medical records. Implements multi-strategy patient identification (MRN, full name, last name, word matching) and constructs context-rich prompts with recent clinical notes and procedure history for Gemini to answer queries.

## Exports

- `extract_patient_from_query(query: str, db: Session) -> Optional[Patient]` - Multi-strategy patient extraction (MRN, full name, last name, word matching)
- `extract_by_mrn(query: str, db: Session) -> Optional[Patient]` - Extract patient by MRN pattern matching
- `extract_by_full_name(query: str, db: Session) -> Optional[Patient]` - Extract by "FirstName LastName" pattern
- `extract_by_last_name(query: str, db: Session) -> Optional[Patient]` - Extract by "Title LastName" pattern
- `extract_by_word_matching(query: str, db: Session) -> Optional[Patient]` - Fallback word-by-word name matching
- `search_by_name_pair(first_name, last_name, db) -> Optional[Patient]` - Database query helper
- `build_query_prompt(query: str, patient_data: Dict) -> str` - Construct Gemini prompt with patient context and instructions
- `process_clinical_query(query: str, db: Session) -> Dict` - Main entry point returning status, patient, response, data_sources

## Dependencies

- [[backend--legacy-models]] - Patient, VoiceTranscript, PVIProcedure ORM models
- [[backend--legacy-config]] - GOOGLE_API_KEY, GEMINI_MODEL
- [[backend--legacy-gemini-synopsis]] - gather_patient_data for data aggregation
- google-generativeai - Google Gemini API client

## Used By

TBD

## Notes

Patient identification priority: MRN (most reliable) > full name > last name (least reliable, warns on ambiguity). Stop words filtered for word matching to reduce false positives. Response instructions emphasize clinical terminology and professional documentation style.
