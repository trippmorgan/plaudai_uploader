---
path: /home/server1/plaudai_uploader/backend/routes/shadow_coder.py
type: api
updated: 2026-01-25
status: active
---

# shadow_coder.py

## Purpose

Implements the Shadow Coder API for automated clinical coding compliance from voice transcripts. Handles ingestion of Plaud voice notes and Zapier webhooks, orchestrates transcript extraction via Claude AI, manages clinical facts storage, and runs rules engine evaluation to generate coding prompts. Serves as the main integration point between voice capture, AI extraction, and coding compliance enforcement.

## Exports

- `router` - FastAPI APIRouter with prefix "/api/shadow-coder" containing all Shadow Coder endpoints
- `PlaudIntakeRequest` - Pydantic model for Plaud voice note ingestion
- `ZapierIntakeRequest` - Flexible Pydantic model accepting various Zapier payload formats
- `AddFactRequest` - Pydantic model for manually adding facts to a case
- `PromptActionRequest` - Pydantic model for prompt actions (resolve, snooze, dismiss)
- `AnalyzeRequest` - Pydantic model for one-shot transcript analysis
- `get_db()` - Database session dependency generator
- `get_facts_service(db)` - FactsService dependency provider
- `get_rules_engine(db, facts_service)` - RulesEngine dependency provider

## Dependencies

- [[backend-services-shadow_coder-__init__]] - Imports TranscriptExtractor, FactsService, RulesEngine
- [[backend-services-shadow_coder-transcript_extractor]] - Claude-powered transcript extraction
- [[backend-services-shadow_coder-facts_service]] - Clinical fact storage and retrieval
- [[backend-services-shadow_coder-rules_engine]] - Coding compliance rule evaluation
- fastapi - Web framework for API routing
- pydantic - Request/response validation
- sqlalchemy - Database operations

## Used By

TBD

## Notes

Migrated from SCC Node.js scc-shadow-coder service. Supports deduplication via SHA-256 content hashing. Case resolution logic determines target case from MRN by checking scc_patients and procedures tables.
