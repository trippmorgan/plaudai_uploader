---
path: /home/server1/plaudai_uploader/backend/routes/tasks.py
type: api
updated: 2026-01-25
status: active
---

# tasks.py

## Purpose

Provides RESTful API endpoints for surgical workflow task management within the ORCC system. Enables creation, retrieval, updating, and completion tracking of tasks associated with patients and procedures. Supports filtering by status, priority, patient MRN, and procedure, with priority-based ordering for clinical workflow efficiency.

## Exports

- `router` - FastAPI APIRouter with prefix "/api/tasks" containing all task endpoints
- `TaskCreate` - Pydantic model for task creation requests
- `TaskUpdate` - Pydantic model for task update requests
- `TaskResponse` - Pydantic model for task response serialization
- `get_db()` - Database session dependency generator
- `row_to_task(row): Dict` - Converts database row to task dictionary

## Dependencies

- fastapi - Web framework for API routing and dependency injection
- pydantic - Request/response model validation
- sqlalchemy - Database ORM and connection management

## Used By

TBD
