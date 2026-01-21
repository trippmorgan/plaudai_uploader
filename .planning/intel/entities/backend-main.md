---
path: /home/server1/plaudai_uploader/backend/main.py
type: api
updated: 2025-01-20
status: active
---

# main.py

## Purpose

Stateless AI processing service for SCC (Surgical Command Center) integration. Provides pure AI processing endpoints for transcript parsing, Gemini-powered synopsis generation, and PVI registry field extraction without database dependencies. This is the refactored v2.0.0 architecture where PlaudAI acts as a processing service and SCC owns all data storage.

## Exports

- `app` - FastAPI application instance with three main endpoints
- `ParseRequest` - Pydantic model for transcript parsing requests
- `ParseResponse` - Pydantic model for parsing results with sections, tags, PVI fields
- `SynopsisRequest` - Pydantic model for AI synopsis generation requests
- `SynopsisResponse` - Pydantic model with synopsis text and metadata
- `ExtractRequest` - Pydantic model for PVI field extraction requests
- `ExtractResponse` - Pydantic model for extracted PVI fields and tags

## Dependencies

- [[backend-services-parser]] - Provides segment_summary, generate_tags, extract_pvi_fields, calculate_confidence_score, process_transcript
- [[backend-services-gemini-synopsis-stateless]] - Provides generate_synopsis_stateless, calculate_age
- fastapi - Web framework for API endpoints and middleware
- pydantic - Request/response validation models

## Used By

TBD

## Notes

This is the newer stateless architecture. The full database-integrated version is in main_legacy.py. CORS is restricted to SCC origins only (localhost:3001, 127.0.0.1:3001, Tailscale IP).
