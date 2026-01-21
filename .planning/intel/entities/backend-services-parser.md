---
path: /home/server1/plaudai_uploader/backend/services/parser.py
type: service
updated: 2025-01-20
status: active
---

# parser.py

## Purpose

Local rule-based NLP pipeline for extracting structured clinical data from unstructured voice transcripts without external API calls. Provides offline-capable extraction using regex patterns and keyword matching for vascular surgery terminology. Extracts PVI (Peripheral Vascular Intervention) registry fields compliant with SVS (Society for Vascular Surgery) specifications.

## Exports

- `segment_summary(summary: str) -> Dict[str, str]` - Parse markdown-style sections from PlaudAI transcript into key-value pairs
- `generate_tags(text: str) -> List[str]` - Generate medical tags using keyword matching against ~35 vascular-specific categories
- `extract_pvi_fields(text: str) -> Dict[str, any]` - Extract PVI registry fields (smoking_history, rutherford_status, ABI, arteries_treated, etc.)
- `calculate_confidence_score(text: str, extracted_fields: Dict) -> float` - Calculate 0.0-1.0 confidence based on text length, field count, and critical fields
- `process_transcript(transcript_text: str) -> Tuple[Dict, List, Dict, float]` - Main pipeline returning sections, tags, pvi_fields, confidence

## Dependencies

- re - Regular expression pattern matching
- logging - Application logging

## Used By

TBD

## Notes

O(n) performance with typical processing time under 10ms per transcript. Limitations include keyword-only matching (no semantic understanding), English only, no misspelling handling, and potential false positives with negation (e.g., "not claudication" still tags claudication).
