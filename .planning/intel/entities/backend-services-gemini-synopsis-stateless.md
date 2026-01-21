---
path: /home/server1/plaudai_uploader/backend/services/gemini_synopsis_stateless.py
type: service
updated: 2025-01-20
status: active
---

# gemini_synopsis_stateless.py

## Purpose

Stateless AI synopsis generation service using Google Gemini. Generates clinical synopses from transcript text without database dependencies, designed for SCC integration where the caller provides all context and handles data storage. Supports multiple synopsis styles (comprehensive, visit_summary, problem_list, procedure_summary) with structured section parsing.

## Exports

- `calculate_age(dob_str: str) -> Optional[int]` - Calculate age from YYYY-MM-DD date string
- `build_synopsis_prompt(transcript_text: str, patient_context: Optional[Dict], style: str) -> str` - Construct Gemini prompt with patient context and style-specific instructions
- `parse_synopsis_sections(synopsis_text: str) -> Dict[str, str]` - Parse AI output into structured sections (chief_complaint, HPI, medications, etc.)
- `generate_synopsis_stateless(transcript_text: str, patient_context: Optional[Dict], style: str) -> Dict` - Main async function returning synopsis, sections, model_used, tokens_used, processing_time_ms

## Dependencies

- google-generativeai - Google Gemini API client library

## Used By

TBD

## Notes

Requires GOOGLE_API_KEY environment variable. Default model is gemini-2.0-flash-exp. This is the stateless refactor of gemini_synopsis.py which includes database operations. Comprehensive style generates 10-section H&P format.
