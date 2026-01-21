---
path: /home/server1/plaudai_uploader/backend/_legacy/db.py
type: util
updated: 2025-01-20
status: active
---

# db.py

## Purpose

Database abstraction layer providing connection pooling, session management, and SQLAlchemy ORM setup for PostgreSQL. Acts as single point of contact between the application and database with QueuePool connection pooling (5 base + 10 overflow), automatic connection validation via pre_ping, and proper transaction management with rollback on error.

## Exports

- `engine` - SQLAlchemy engine with QueuePool connection pooling
- `SessionLocal` - Session factory for creating database sessions
- `Base` - SQLAlchemy declarative base class for ORM models
- `get_db() -> Generator[Session]` - FastAPI dependency that yields request-scoped sessions with cleanup
- `get_db_context() -> ContextManager[Session]` - Context manager for non-FastAPI contexts with auto-commit
- `init_db() -> None` - Create all tables defined in ORM models
- `check_connection() -> bool` - Validate database connectivity for health checks

## Dependencies

- [[backend--legacy-config]] - Provides DATABASE_URL connection string (actually imports from relative .config)
- sqlalchemy - ORM and database connection management

## Used By

TBD

## Notes

autoflush=False and autocommit=False require explicit commit for transaction control. The get_db() finally block always executes to prevent connection leaks. For production schema migrations, use Alembic instead of init_db().
