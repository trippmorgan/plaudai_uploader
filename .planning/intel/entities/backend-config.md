---
path: /home/server1/plaudai_uploader/backend/config.py
type: config
updated: 2025-01-20
status: active
---

# config.py

## Purpose

Centralized configuration management for the PlaudAI Uploader system. Loads environment variables from .env file and provides typed configuration constants for database connections, API settings, Gemini AI integration, file upload limits, and Medical Mirror Observer telemetry. Acts as single source of truth for all application settings.

## Exports

- `BASE_DIR` - Path to project root directory
- `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD` - PostgreSQL connection parameters
- `DATABASE_URL` - Assembled PostgreSQL connection string
- `API_HOST`, `API_PORT`, `DEBUG` - FastAPI server configuration
- `GOOGLE_API_KEY`, `GEMINI_MODEL` - Gemini AI integration settings
- `PVI_ENABLED` - Toggle for PVI registry integration
- `MAX_UPLOAD_SIZE`, `ALLOWED_EXTENSIONS` - File upload constraints
- `LOG_LEVEL`, `LOG_FILE` - Logging configuration
- `OBSERVER_URL` - Medical Mirror Observer telemetry endpoint

## Dependencies

- python-dotenv - Loads environment variables from .env file
- pathlib - Path resolution for BASE_DIR

## Used By

TBD

## Notes

Default database is surgical_command_center with scc_user. Observer runs on MacBook Pro via Tailscale at port 3000. Set OBSERVER_URL to empty string to disable telemetry.
