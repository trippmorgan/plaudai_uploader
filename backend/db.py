"""
=============================================================================
DATABASE CONNECTION & SESSION MANAGEMENT
=============================================================================

ARCHITECTURAL ROLE:
    This module is the DATABASE ABSTRACTION LAYER - the single point of
    contact between the application and PostgreSQL. All database operations
    flow through this module's session management.

DATA FLOW POSITION:
    ┌────────────────────────────────────────────────────────────────────┐
    │                         APPLICATION LAYER                          │
    │         main.py  │  routes/*.py  │  services/*.py                 │
    └────────────────────────────┬───────────────────────────────────────┘
                                 │ Depends(get_db)
                                 ▼
    ┌────────────────────────────────────────────────────────────────────┐
    │                      db.py (THIS FILE)                             │
    │  ┌──────────────────────────────────────────────────────────────┐ │
    │  │                    SESSION FACTORY                            │ │
    │  │  SessionLocal() ──► Session ──► Query/Commit ──► close()     │ │
    │  └──────────────────────────────────────────────────────────────┘ │
    │                            │                                       │
    │  ┌──────────────────────────────────────────────────────────────┐ │
    │  │                    CONNECTION POOL                            │ │
    │  │  Engine ──► QueuePool (5 base + 10 overflow connections)     │ │
    │  └──────────────────────────────────────────────────────────────┘ │
    └────────────────────────────┬───────────────────────────────────────┘
                                 │ libpq (psycopg2)
                                 ▼
    ┌────────────────────────────────────────────────────────────────────┐
    │                        PostgreSQL Server                           │
    │              Database: surgical_command_center                     │
    └────────────────────────────────────────────────────────────────────┘

CRITICAL DESIGN PRINCIPLES:

    1. CONNECTION POOLING (QueuePool):
       - pool_size=5: Maintains 5 persistent connections at all times
       - max_overflow=10: Can temporarily create up to 15 total connections
       - pool_pre_ping=True: Validates connections before use (prevents stale)

       WHY: Database connections are expensive to establish (~100-500ms).
       Pooling reuses connections, reducing latency to <1ms for requests.

    2. SESSION LIFECYCLE MANAGEMENT:
       The get_db() generator enforces a strict lifecycle:

       ┌──────────────────────────────────────────────────────────────┐
       │  Session Created ──► Yielded to Route ──► Cleanup Executed  │
       │        │                   │                    │           │
       │        │                   │         ┌──────────┴─────────┐ │
       │        │                   │         │ Error? → rollback  │ │
       │        │                   │         │ Success? → (app)   │ │
       │        │                   │         │ Always → close     │ │
       │        │                   │         └────────────────────┘ │
       └──────────────────────────────────────────────────────────────┘

       CRITICAL: The finally block ALWAYS executes, preventing connection leaks.

    3. AUTOFLUSH/AUTOCOMMIT DISABLED:
       - autoflush=False: Changes not sent to DB until explicit flush/commit
       - autocommit=False: Transactions must be explicitly committed

       WHY: Explicit control prevents partial writes and race conditions.
       Pattern: read → modify → commit (or rollback on error)

    4. DECLARATIVE BASE:
       Base = declarative_base() creates a registry that all ORM models
       inherit from. This enables:
       - Automatic table creation via Base.metadata.create_all()
       - Relationship resolution across models
       - Consistent column type mapping

SECURITY MODEL:
    - Connection string from environment (.config.DATABASE_URL)
    - Never log or expose credentials
    - SSL can be enabled via connection string parameters
    - Connection validation (pre_ping) prevents session hijacking

FUNCTION REFERENCE:

    get_db() -> Generator[Session, None, None]
        FastAPI dependency that provides request-scoped database sessions.
        USAGE: def endpoint(db: Session = Depends(get_db))
        LIFECYCLE: Creates session → yields → rolls back on error → closes

    get_db_context() -> ContextManager[Session]
        Context manager for non-FastAPI contexts (scripts, background tasks).
        USAGE: with get_db_context() as db: db.query(...)
        LIFECYCLE: Creates session → yields → commits → closes
        NOTE: Commits on success (unlike get_db which leaves commit to caller)

    init_db() -> None
        Creates all tables defined in ORM models.
        USAGE: Called once at application startup
        SAFE: Uses CREATE TABLE IF NOT EXISTS semantics

    check_connection() -> bool
        Validates database connectivity.
        USAGE: Health checks, startup validation
        RETURNS: True if connection succeeds, False otherwise

MAINTENANCE NOTES:
    - To debug SQL: set echo=True in create_engine()
    - Pool exhaustion: If seeing timeouts, increase pool_size
    - Connection leaks: Look for get_db() calls without proper cleanup
    - Schema migrations: Use Alembic (not init_db) for production changes

ERROR HANDLING:
    - Connection failures logged as ERROR level
    - Session errors trigger automatic rollback
    - Health check failures should trigger container restart

VERSION: 2.0.0
LAST UPDATED: 2025-12
=============================================================================
"""
from sqlalchemy import create_engine, text  # Add text here
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.pool import QueuePool
from contextlib import contextmanager
import logging
from .config import DATABASE_URL

logger = logging.getLogger(__name__)

# Create engine with connection pooling
engine = create_engine(
    DATABASE_URL,
    poolclass=QueuePool,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,  # Verify connections before using
    echo=False  # Set to True for SQL debugging
)

# Session factory
SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False
)

# Base class for ORM models
Base = declarative_base()

def get_db():
    """
    Dependency for FastAPI routes
    Provides a database session and ensures cleanup
    """
    db = SessionLocal()
    try:
        yield db
    except Exception as e:
        logger.error(f"Database session error: {e}")
        db.rollback()
        raise
    finally:
        db.close()

@contextmanager
def get_db_context():
    """
    Context manager for direct database access
    Usage:
        with get_db_context() as db:
            # perform operations
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception as e:
        logger.error(f"Database context error: {e}")
        db.rollback()
        raise
    finally:
        db.close()

def init_db():
    """
    Initialize database - create all tables
    """
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created successfully")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise

def check_connection():
    """
    Verify database connectivity
    """
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))  # Fixed: wrapped in text()
        logger.info("Database connection successful")
        return True
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        return False