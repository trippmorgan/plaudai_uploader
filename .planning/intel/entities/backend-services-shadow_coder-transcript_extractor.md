---
path: /home/server1/plaudai_uploader/backend/services/shadow_coder/transcript_extractor.py
type: service
updated: 2026-01-25
status: active
---

# transcript_extractor.py

## Purpose

Extracts structured clinical facts from vascular surgery voice transcripts using Claude AI. Designed specifically for PAD (Peripheral Artery Disease) coding compliance, extracting symptom classification, hemodynamics (ABI/TBI), anatomy details, wound documentation, medical management records, procedure techniques, and comorbidities. Also supports carotid-specific extraction and CPT procedure detail analysis.

## Exports

- `TranscriptExtractor` - Main class for AI-powered transcript analysis
  - `is_available: bool` - Property indicating if Claude API is configured
  - `extract_pad_facts(transcript, context): Dict` - Extracts PAD-relevant clinical facts with confidence scores
  - `classify_pad_symptoms(transcript): Dict` - Quick symptom classification (asymptomatic/claudication/rest_pain/tissue_loss)
  - `extract_procedure_details(transcript): Dict` - Extracts CPT coding details with vessel, laterality, techniques

## Dependencies

- anthropic - Claude AI Python SDK for transcript analysis
- json - Response parsing
- re - Regex for JSON extraction from responses
- os - Environment variable access for API key

## Used By

TBD

## Notes

Gracefully degrades if anthropic package not installed or API key not configured. Uses claude-sonnet-4-20250514 model. Extraction prompt includes comprehensive PAD coding schema covering symptoms, hemodynamics, anatomy, wounds, medical management, procedures, comorbidities, and carotid-specific fields.
