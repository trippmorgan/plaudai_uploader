---
path: /home/server1/plaudai_uploader/backend/services/category_parser.py
type: service
updated: 2025-01-20
status: active
---

# category_parser.py

## Purpose

Specialized AI extraction engine using Google Gemini to extract structured data from medical records based on their category (operative_note, imaging, lab_result, office_visit). Unlike parser.py which uses regex, this module employs semantic understanding via LLM for category-specific JSON schema extraction with tailored prompts for each record type.

## Exports

- `PROMPTS` - Dictionary of category-specific prompt templates with JSON schemas
- `parse_by_category(text: str, category: str) -> Dict` - Parse medical text using category-specific Gemini prompt, returns structured dict or error
- `generate_category_summary(parsed_data: Dict, category: str) -> str` - Generate human-readable summary from parsed data formatted by category

## Dependencies

- [[backend-config]] - Provides GOOGLE_API_KEY, GEMINI_MODEL configuration
- google-generativeai - Google Gemini API client
- json - JSON parsing and serialization

## Used By

TBD

## Notes

Each category has tailored JSON schema: operative_note extracts procedure details, devices, complications; imaging extracts stenosis_percent, measurements, impression; lab_result extracts critical_values, abnormal flags; office_visit extracts medications, vitals, plan. More expensive than regex parsing - use for high-value extraction only.
