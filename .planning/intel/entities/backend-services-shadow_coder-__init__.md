---
path: /home/server1/plaudai_uploader/backend/services/shadow_coder/__init__.py
type: module
updated: 2026-01-25
status: active
---

# __init__.py

## Purpose

Package initializer for the Shadow Coder services module. Exposes the three core services for clinical transcript processing: TranscriptExtractor for Claude-based fact extraction, FactsService for clinical truth map management, and RulesEngine for coding compliance evaluation.

## Exports

- `TranscriptExtractor` - Claude AI-powered transcript fact extraction
- `FactsService` - Clinical fact storage and retrieval service
- `RulesEngine` - Coding compliance rules evaluation engine

## Dependencies

- [[backend-services-shadow_coder-transcript_extractor]] - TranscriptExtractor class
- [[backend-services-shadow_coder-facts_service]] - FactsService class
- [[backend-services-shadow_coder-rules_engine]] - RulesEngine class

## Used By

TBD
