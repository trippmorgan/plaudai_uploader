"""
=============================================================================
TASKS API ROUTES
=============================================================================

Task management for ORCC surgical workflow

ENDPOINTS:
    GET    /api/tasks              - List tasks with filters
    POST   /api/tasks              - Create new task
    GET    /api/tasks/{id}         - Get task by ID
    PATCH  /api/tasks/{id}         - Update task
    DELETE /api/tasks/{id}         - Delete task
    POST   /api/tasks/{id}/complete - Mark task complete
    GET    /api/tasks/patient/{mrn} - Get tasks for a patient
    GET    /api/tasks/procedure/{id} - Get tasks for a procedure

=============================================================================
"""
import os
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel, Field
from sqlalchemy import text, create_engine
from sqlalchemy.orm import sessionmaker, Session

# ==================== Logging ====================
logger = logging.getLogger(__name__)

# ==================== Database Connection ====================
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    f"postgresql://{os.getenv('DB_USER', 'scc_user')}:{os.getenv('DB_PASSWORD', 'scc_password')}@{os.getenv('DB_HOST', 'localhost')}:{os.getenv('DB_PORT', '5432')}/{os.getenv('DB_NAME', 'surgical_command_center')}"
)

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ==================== Router ====================
router = APIRouter(prefix="/api/tasks", tags=["Tasks"])


# ==================== Pydantic Models ====================

class TaskCreate(BaseModel):
    """Request to create a new task."""
    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    patient_mrn: Optional[str] = None
    procedure_id: Optional[str] = None
    task_type: str = Field(default="general", description="Type: workup, clearance, scheduling, follow_up, general")
    priority: str = Field(default="normal", description="Priority: low, normal, high, urgent")
    due_date: Optional[datetime] = None
    assigned_to: Optional[str] = None
    created_by: Optional[str] = None
    notes: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)

    class Config:
        json_schema_extra = {
            "example": {
                "title": "Order cardiac clearance",
                "patient_mrn": "12345678",
                "task_type": "clearance",
                "priority": "high",
                "assigned_to": "Dr. Smith"
            }
        }


class TaskUpdate(BaseModel):
    """Request to update a task."""
    title: Optional[str] = None
    description: Optional[str] = None
    task_type: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[str] = None
    due_date: Optional[datetime] = None
    assigned_to: Optional[str] = None
    notes: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class TaskResponse(BaseModel):
    """Task response model."""
    id: str
    title: str
    description: Optional[str]
    patient_mrn: Optional[str]
    procedure_id: Optional[str]
    task_type: str
    status: str
    priority: str
    due_date: Optional[datetime]
    assigned_to: Optional[str]
    created_by: Optional[str]
    completed_at: Optional[datetime]
    notes: Optional[str]
    metadata: Optional[Dict[str, Any]]
    created_at: Optional[datetime]
    updated_at: Optional[datetime]


# ==================== Helper Functions ====================

def row_to_task(row) -> Dict[str, Any]:
    """Convert database row to task dict."""
    return {
        "id": str(row[0]),
        "patient_mrn": row[1],
        "procedure_id": str(row[2]) if row[2] else None,
        "title": row[3],
        "description": row[4],
        "task_type": row[5],
        "status": row[6],
        "priority": row[7],
        "due_date": row[8].isoformat() if row[8] else None,
        "assigned_to": row[9],
        "created_by": row[10],
        "completed_at": row[11].isoformat() if row[11] else None,
        "notes": row[12],
        "metadata": row[13] or {},
        "created_at": row[14].isoformat() if row[14] else None,
        "updated_at": row[15].isoformat() if row[15] else None
    }


# ==================== Endpoints ====================

@router.get("")
async def list_tasks(
    status: Optional[str] = Query(None, description="Filter by status: pending, in_progress, completed, blocked"),
    priority: Optional[str] = Query(None, description="Filter by priority: low, normal, high, urgent"),
    task_type: Optional[str] = Query(None, description="Filter by type: workup, clearance, scheduling, follow_up, general"),
    patient_mrn: Optional[str] = Query(None, description="Filter by patient MRN"),
    procedure_id: Optional[str] = Query(None, description="Filter by procedure ID"),
    assigned_to: Optional[str] = Query(None, description="Filter by assignee"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db)
):
    """
    List tasks with optional filters.

    Returns tasks ordered by priority (urgent first) then due date.
    """
    sql = """
        SELECT
            id, patient_mrn, procedure_id, title, description,
            task_type, status, priority, due_date, assigned_to,
            created_by, completed_at, notes, metadata,
            "createdAt", "updatedAt"
        FROM tasks
        WHERE 1=1
    """
    params = {}

    if status:
        sql += " AND status = :status"
        params["status"] = status

    if priority:
        sql += " AND priority = :priority"
        params["priority"] = priority

    if task_type:
        sql += " AND task_type = :task_type"
        params["task_type"] = task_type

    if patient_mrn:
        sql += " AND patient_mrn = :patient_mrn"
        params["patient_mrn"] = patient_mrn

    if procedure_id:
        sql += " AND procedure_id = CAST(:procedure_id AS uuid)"
        params["procedure_id"] = procedure_id

    if assigned_to:
        sql += " AND assigned_to ILIKE :assigned_to"
        params["assigned_to"] = f"%{assigned_to}%"

    sql += """
        ORDER BY
            CASE priority
                WHEN 'urgent' THEN 1
                WHEN 'high' THEN 2
                WHEN 'normal' THEN 3
                WHEN 'low' THEN 4
            END,
            CASE WHEN due_date IS NULL THEN 1 ELSE 0 END,
            due_date ASC,
            "createdAt" DESC
        LIMIT :limit OFFSET :offset
    """
    params["limit"] = limit
    params["offset"] = offset

    result = db.execute(text(sql), params)
    rows = result.fetchall()

    return {
        "success": True,
        "count": len(rows),
        "tasks": [row_to_task(row) for row in rows]
    }


@router.post("", status_code=201)
async def create_task(task: TaskCreate, db: Session = Depends(get_db)):
    """Create a new task."""
    # Build SQL based on whether procedure_id is provided
    if task.procedure_id:
        sql = text("""
            INSERT INTO tasks (
                id, patient_mrn, procedure_id, title, description,
                task_type, status, priority, due_date, assigned_to,
                created_by, notes, metadata, "createdAt", "updatedAt"
            ) VALUES (
                gen_random_uuid(), :patient_mrn, CAST(:procedure_id AS uuid), :title, :description,
                :task_type, 'pending', :priority, :due_date, :assigned_to,
                :created_by, :notes, CAST(:metadata AS jsonb), NOW(), NOW()
            )
            RETURNING id::text
        """)
    else:
        sql = text("""
            INSERT INTO tasks (
                id, patient_mrn, title, description,
                task_type, status, priority, due_date, assigned_to,
                created_by, notes, metadata, "createdAt", "updatedAt"
            ) VALUES (
                gen_random_uuid(), :patient_mrn, :title, :description,
                :task_type, 'pending', :priority, :due_date, :assigned_to,
                :created_by, :notes, CAST(:metadata AS jsonb), NOW(), NOW()
            )
            RETURNING id::text
        """)

    try:
        params = {
            "patient_mrn": task.patient_mrn,
            "title": task.title,
            "description": task.description,
            "task_type": task.task_type,
            "priority": task.priority,
            "due_date": task.due_date,
            "assigned_to": task.assigned_to,
            "created_by": task.created_by,
            "notes": task.notes,
            "metadata": str(task.metadata or {}).replace("'", '"')
        }
        if task.procedure_id:
            params["procedure_id"] = task.procedure_id
        result = db.execute(sql, params)
        db.commit()
        task_id = result.fetchone()[0]

        return {
            "success": True,
            "task_id": task_id,
            "message": "Task created successfully"
        }
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to create task: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{task_id}")
async def get_task(task_id: str, db: Session = Depends(get_db)):
    """Get a task by ID."""
    sql = text("""
        SELECT
            id, patient_mrn, procedure_id, title, description,
            task_type, status, priority, due_date, assigned_to,
            created_by, completed_at, notes, metadata,
            "createdAt", "updatedAt"
        FROM tasks
        WHERE id = CAST(:task_id AS uuid)
    """)

    result = db.execute(sql, {"task_id": task_id})
    row = result.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")

    return {"success": True, "task": row_to_task(row)}


@router.patch("/{task_id}")
async def update_task(task_id: str, updates: TaskUpdate, db: Session = Depends(get_db)):
    """Update a task."""
    update_fields = []
    params = {"task_id": task_id}

    if updates.title is not None:
        update_fields.append("title = :title")
        params["title"] = updates.title

    if updates.description is not None:
        update_fields.append("description = :description")
        params["description"] = updates.description

    if updates.task_type is not None:
        update_fields.append("task_type = :task_type")
        params["task_type"] = updates.task_type

    if updates.status is not None:
        update_fields.append("status = :status")
        params["status"] = updates.status
        if updates.status == "completed":
            update_fields.append("completed_at = NOW()")

    if updates.priority is not None:
        update_fields.append("priority = :priority")
        params["priority"] = updates.priority

    if updates.due_date is not None:
        update_fields.append("due_date = :due_date")
        params["due_date"] = updates.due_date

    if updates.assigned_to is not None:
        update_fields.append("assigned_to = :assigned_to")
        params["assigned_to"] = updates.assigned_to

    if updates.notes is not None:
        update_fields.append("notes = :notes")
        params["notes"] = updates.notes

    if updates.metadata is not None:
        update_fields.append("metadata = :metadata::jsonb")
        params["metadata"] = str(updates.metadata).replace("'", '"')

    if not update_fields:
        raise HTTPException(status_code=400, detail="No fields to update")

    update_fields.append('"updatedAt" = NOW()')

    sql = text(f"""
        UPDATE tasks
        SET {', '.join(update_fields)}
        WHERE id = CAST(:task_id AS uuid)
        RETURNING id::text
    """)

    try:
        result = db.execute(sql, params)
        db.commit()

        if not result.fetchone():
            raise HTTPException(status_code=404, detail=f"Task {task_id} not found")

        # Return updated task
        return await get_task(task_id, db)
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to update task: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{task_id}")
async def delete_task(task_id: str, db: Session = Depends(get_db)):
    """Delete a task."""
    sql = text("DELETE FROM tasks WHERE id = CAST(:task_id AS uuid) RETURNING id::text")

    try:
        result = db.execute(sql, {"task_id": task_id})
        db.commit()

        if not result.fetchone():
            raise HTTPException(status_code=404, detail=f"Task {task_id} not found")

        return {"success": True, "message": "Task deleted"}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{task_id}/complete")
async def complete_task(
    task_id: str,
    completed_by: Optional[str] = None,
    notes: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Mark a task as completed."""
    sql = text("""
        UPDATE tasks
        SET status = 'completed',
            completed_at = NOW(),
            notes = COALESCE(:notes, notes),
            "updatedAt" = NOW()
        WHERE id = CAST(:task_id AS uuid)
        RETURNING id::text
    """)

    try:
        result = db.execute(sql, {
            "task_id": task_id,
            "notes": notes
        })
        db.commit()

        if not result.fetchone():
            raise HTTPException(status_code=404, detail=f"Task {task_id} not found")

        return {"success": True, "message": "Task completed"}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/patient/{mrn}")
async def get_patient_tasks(
    mrn: str,
    status: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Get all tasks for a patient."""
    sql = """
        SELECT
            id, patient_mrn, procedure_id, title, description,
            task_type, status, priority, due_date, assigned_to,
            created_by, completed_at, notes, metadata,
            "createdAt", "updatedAt"
        FROM tasks
        WHERE patient_mrn = :mrn
    """
    params = {"mrn": mrn}

    if status:
        sql += " AND status = :status"
        params["status"] = status

    sql += """
        ORDER BY
            CASE priority WHEN 'urgent' THEN 1 WHEN 'high' THEN 2 WHEN 'normal' THEN 3 WHEN 'low' THEN 4 END,
            due_date ASC NULLS LAST
    """

    result = db.execute(text(sql), params)
    rows = result.fetchall()

    return {
        "success": True,
        "mrn": mrn,
        "count": len(rows),
        "tasks": [row_to_task(row) for row in rows]
    }


@router.get("/procedure/{procedure_id}")
async def get_procedure_tasks(
    procedure_id: str,
    status: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Get all tasks for a procedure."""
    sql = """
        SELECT
            id, patient_mrn, procedure_id, title, description,
            task_type, status, priority, due_date, assigned_to,
            created_by, completed_at, notes, metadata,
            "createdAt", "updatedAt"
        FROM tasks
        WHERE procedure_id = CAST(:procedure_id AS uuid)
    """
    params = {"procedure_id": procedure_id}

    if status:
        sql += " AND status = :status"
        params["status"] = status

    sql += " ORDER BY priority DESC, due_date ASC NULLS LAST"

    result = db.execute(text(sql), params)
    rows = result.fetchall()

    return {
        "success": True,
        "procedure_id": procedure_id,
        "count": len(rows),
        "tasks": [row_to_task(row) for row in rows]
    }


# ==================== Stats Endpoint ====================

@router.get("/stats/summary")
async def get_task_stats(db: Session = Depends(get_db)):
    """Get task statistics summary."""
    sql = text("""
        SELECT
            status,
            priority,
            COUNT(*) as count
        FROM tasks
        GROUP BY status, priority
    """)

    result = db.execute(sql)
    rows = result.fetchall()

    stats = {
        "by_status": {"pending": 0, "in_progress": 0, "completed": 0, "blocked": 0},
        "by_priority": {"low": 0, "normal": 0, "high": 0, "urgent": 0},
        "total": 0
    }

    for row in rows:
        status, priority, count = row
        if status in stats["by_status"]:
            stats["by_status"][status] += count
        if priority in stats["by_priority"]:
            stats["by_priority"][priority] += count
        stats["total"] += count

    # Get overdue count
    overdue_result = db.execute(text("""
        SELECT COUNT(*) FROM tasks
        WHERE status NOT IN ('completed', 'blocked')
          AND due_date < NOW()
    """))
    stats["overdue"] = overdue_result.scalar() or 0

    return {"success": True, "stats": stats}
