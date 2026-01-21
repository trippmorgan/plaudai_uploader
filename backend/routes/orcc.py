"""
=============================================================================
ORCC INTEGRATION API ROUTES
=============================================================================

VERSION: 1.0.0
PURPOSE: API endpoints for OR Command Center (ORCC) integration

ENDPOINTS:
    GET  /api/procedures              - List procedures with filters
    GET  /api/procedures/{id}         - Get single procedure
    PATCH /api/procedures/{id}        - Update procedure fields
    GET  /api/patients                - List/search patients
    GET  /api/patients/{mrn}          - Get patient by MRN
    POST /api/patients                - Create patient

FILTERS:
    surgical_status  - ready, near_ready, workup, hold, scheduled
    patient_mrn      - Patient MRN lookup
    scheduled_location - CRH, ASC, AUMC, etc.

=============================================================================
"""
import os
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, date
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel, Field
from sqlalchemy import create_engine, text
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
router = APIRouter(prefix="/api", tags=["ORCC Integration"])

# ==================== Pydantic Models ====================

class ProcedureBase(BaseModel):
    mrn: str
    patient_name: str
    procedure_type: Optional[str] = "Lower Extremity Angiogram"
    procedure_side: Optional[str] = None  # left, right, bilateral
    procedure_date: Optional[datetime] = None
    surgeon: Optional[str] = None
    scheduled_location: Optional[str] = None  # CRH, ASC, AUMC
    surgical_status: Optional[str] = "workup"  # ready, near_ready, workup, hold, scheduled
    barriers: Optional[List[str]] = []
    cardiology_clearance: Optional[bool] = None
    stress_test_status: Optional[str] = None  # pending, completed, abnormal, not_needed
    vqi_case_id: Optional[str] = None

class ProcedureUpdate(BaseModel):
    procedure_type: Optional[str] = None
    procedure_side: Optional[str] = None
    procedure_date: Optional[datetime] = None
    surgeon: Optional[str] = None
    scheduled_location: Optional[str] = None
    surgical_status: Optional[str] = None
    barriers: Optional[List[str]] = None
    cardiology_clearance: Optional[bool] = None
    stress_test_status: Optional[str] = None
    vqi_case_id: Optional[str] = None
    status: Optional[str] = None  # draft, in_progress, completed, finalized
    # New fields for endovascular planning
    procedure_name: Optional[str] = None
    indication: Optional[Dict[str, Any]] = None
    access_details: Optional[Dict[str, Any]] = None
    inflow_status: Optional[Dict[str, str]] = None
    outflow_status: Optional[Dict[str, str]] = None
    vessel_data: Optional[Dict[str, Any]] = None
    interventions: Optional[List[Dict[str, Any]]] = None
    cpt_codes: Optional[List[str]] = None
    findings: Optional[str] = None
    results: Optional[str] = None


# ==================== Endovascular Planning Models ====================

class IndicationData(BaseModel):
    primary_icd10: str
    primary_icd10_text: Optional[str] = None
    secondary_icd10: Optional[str] = None
    secondary_icd10_text: Optional[str] = None
    rutherford: Optional[str] = None  # r3, r4, r5, r6

class AccessData(BaseModel):
    site: Optional[str] = None  # r_cfa, l_cfa, brachial, pedal
    sheath_size: Optional[str] = None  # 4, 5, 6, 7, 8
    anesthesia: Optional[str] = None  # mac_local, local, general

class VesselStatus(BaseModel):
    status: str  # patent, stenosis_mild, stenosis_mod, stenosis_severe, occluded
    length: Optional[str] = None  # <5cm, 5-10cm, 10-20cm, >20cm
    intervention: Optional[str] = None
    notes: Optional[str] = None

class InterventionData(BaseModel):
    vessel: str  # "L SFA", "R Popliteal", etc.
    vessel_id: str  # "l_sfa", "r_popliteal", etc.
    status: str
    length: Optional[str] = None
    intervention: str  # pta, stent, atherectomy, pta_stent, ath_pta, ath_pta_stent
    notes: Optional[str] = None

class ProcedureCreate(BaseModel):
    """Full procedure creation model for endovascular planning."""
    mrn: str
    patient_name: Optional[str] = None  # Will be looked up if not provided
    procedure_type: Optional[str] = "Lower Extremity Angiogram"
    procedure_name: Optional[str] = None
    procedure_side: Optional[str] = None  # left, right, bilateral
    procedure_date: Optional[date] = None
    scheduled_location: Optional[str] = "ASC"  # ASC, CRH, AUMC
    status: Optional[str] = "draft"  # draft, in_progress, completed, finalized
    surgical_status: Optional[str] = "workup"  # ready, near_ready, workup, hold
    surgeon: Optional[str] = None
    barriers: Optional[List[str]] = []
    cardiology_clearance: Optional[bool] = None
    stress_test_status: Optional[str] = None
    vqi_case_id: Optional[str] = None

    # Endovascular planning fields
    indication: Optional[Dict[str, Any]] = None
    access: Optional[Dict[str, Any]] = None
    inflow: Optional[Dict[str, str]] = None
    outflow: Optional[Dict[str, str]] = None
    vessel_data: Optional[Dict[str, Any]] = None
    interventions: Optional[List[Dict[str, Any]]] = None
    cpt_codes: Optional[List[str]] = None
    findings: Optional[str] = None
    results: Optional[str] = None

class ProcedureResponse(ProcedureBase):
    id: str
    status: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class PatientBase(BaseModel):
    mrn: str
    first_name: str
    last_name: str
    middle_name: Optional[str] = None
    date_of_birth: date
    age: Optional[int] = None
    gender: Optional[str] = "unknown"
    phone_primary: Optional[str] = None
    phone_secondary: Optional[str] = None
    email: Optional[str] = None
    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip_code: Optional[str] = None
    country: Optional[str] = "USA"
    emergency_contact_name: Optional[str] = None
    emergency_contact_phone: Optional[str] = None
    emergency_contact_relationship: Optional[str] = None
    insurance_provider: Optional[str] = None
    insurance_policy_number: Optional[str] = None
    insurance_group_number: Optional[str] = None
    primary_physician: Optional[str] = None
    allergies: Optional[str] = None
    current_medications: Optional[str] = None
    medical_history: Optional[str] = None

class PatientResponse(PatientBase):
    id: str
    active: bool = True
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

# ==================== Procedure Endpoints ====================

@router.get("/procedures", response_model=List[Dict[str, Any]])
async def list_procedures(
    surgical_status: Optional[str] = Query(None, description="Filter by surgical status: ready, near_ready, workup, hold, scheduled"),
    patient_mrn: Optional[str] = Query(None, description="Filter by patient MRN"),
    scheduled_location: Optional[str] = Query(None, description="Filter by location: CRH, ASC, AUMC"),
    status: Optional[str] = Query(None, description="Filter by procedure status: draft, in_progress, completed, finalized"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db)
):
    """
    List procedures with optional filters.

    Query Parameters:
    - surgical_status: ready, near_ready, workup, hold, scheduled
    - patient_mrn: Filter by patient MRN
    - scheduled_location: CRH, ASC, AUMC
    - status: draft, in_progress, completed, finalized
    """
    query = """
        SELECT
            id::text, mrn, patient_name, procedure_type, procedure_side,
            procedure_date, surgeon, scheduled_location, surgical_status::text,
            barriers, cardiology_clearance, stress_test_status::text,
            vqi_case_id, status::text, "createdAt", "updatedAt"
        FROM procedures
        WHERE 1=1
    """
    params = {}

    if surgical_status:
        query += " AND surgical_status = CAST(:surgical_status AS enum_surgical_status)"
        params["surgical_status"] = surgical_status

    if patient_mrn:
        query += " AND mrn = :patient_mrn"
        params["patient_mrn"] = patient_mrn

    if scheduled_location:
        query += " AND scheduled_location = :scheduled_location"
        params["scheduled_location"] = scheduled_location

    if status:
        query += " AND status = CAST(:status AS enum_procedures_status)"
        params["status"] = status

    query += " ORDER BY procedure_date DESC NULLS LAST, \"createdAt\" DESC"
    query += " LIMIT :limit OFFSET :offset"
    params["limit"] = limit
    params["offset"] = offset

    result = db.execute(text(query), params)
    rows = result.fetchall()

    procedures = []
    for row in rows:
        procedures.append({
            "id": row[0],
            "mrn": row[1],
            "patient_name": row[2],
            "procedure_type": row[3],
            "procedure_side": row[4],
            "procedure_date": row[5].isoformat() if row[5] else None,
            "surgeon": row[6],
            "scheduled_location": row[7],
            "surgical_status": row[8],
            "barriers": row[9] or [],
            "cardiology_clearance": row[10],
            "stress_test_status": row[11],
            "vqi_case_id": row[12],
            "status": row[13],
            "created_at": row[14].isoformat() if row[14] else None,
            "updated_at": row[15].isoformat() if row[15] else None
        })

    return procedures


@router.get("/procedures/{procedure_id}", response_model=Dict[str, Any])
async def get_procedure(procedure_id: str, db: Session = Depends(get_db)):
    """Get a single procedure by ID."""
    query = """
        SELECT
            id::text, mrn, patient_name, procedure_type, procedure_side,
            procedure_date, surgeon, scheduled_location, surgical_status::text,
            barriers, cardiology_clearance, stress_test_status::text,
            vqi_case_id, status::text, "createdAt", "updatedAt",
            access_site, sheath_size, closure_method, narrative,
            complications, common_iliac, external_iliac, common_femoral,
            superficial_femoral, profunda, popliteal, anterior_tibial,
            posterior_tibial, peroneal
        FROM procedures
        WHERE id = CAST(:procedure_id AS uuid)
    """
    result = db.execute(text(query), {"procedure_id": procedure_id})
    row = result.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail=f"Procedure {procedure_id} not found")

    return {
        "id": row[0],
        "mrn": row[1],
        "patient_name": row[2],
        "procedure_type": row[3],
        "procedure_side": row[4],
        "procedure_date": row[5].isoformat() if row[5] else None,
        "surgeon": row[6],
        "scheduled_location": row[7],
        "surgical_status": row[8],
        "barriers": row[9] or [],
        "cardiology_clearance": row[10],
        "stress_test_status": row[11],
        "vqi_case_id": row[12],
        "status": row[13],
        "created_at": row[14].isoformat() if row[14] else None,
        "updated_at": row[15].isoformat() if row[15] else None,
        "access_site": row[16],
        "sheath_size": row[17],
        "closure_method": row[18],
        "narrative": row[19],
        "complications": row[20] or [],
        "arterial_findings": {
            "common_iliac": row[21] or {},
            "external_iliac": row[22] or {},
            "common_femoral": row[23] or {},
            "superficial_femoral": row[24] or {},
            "profunda": row[25] or {},
            "popliteal": row[26] or {},
            "anterior_tibial": row[27] or {},
            "posterior_tibial": row[28] or {},
            "peroneal": row[29] or {}
        }
    }


@router.patch("/procedures/{procedure_id}", response_model=Dict[str, Any])
async def update_procedure(
    procedure_id: str,
    updates: ProcedureUpdate,
    db: Session = Depends(get_db)
):
    """
    Update procedure fields (barriers, clearance, location, status, etc.)

    Common updates:
    - surgical_status: Update workup status
    - barriers: Add/remove pending items
    - cardiology_clearance: Mark clearance received
    - stress_test_status: Update stress test result
    """
    # Build dynamic update query
    update_fields = []
    params = {"procedure_id": procedure_id}

    if updates.surgical_status is not None:
        update_fields.append("surgical_status = CAST(:surgical_status AS enum_surgical_status)")
        params["surgical_status"] = updates.surgical_status

    if updates.barriers is not None:
        update_fields.append("barriers = CAST(:barriers AS jsonb)")
        params["barriers"] = updates.barriers

    if updates.cardiology_clearance is not None:
        update_fields.append("cardiology_clearance = :cardiology_clearance")
        params["cardiology_clearance"] = updates.cardiology_clearance

    if updates.stress_test_status is not None:
        update_fields.append("stress_test_status = CAST(:stress_test_status AS enum_stress_test_status)")
        params["stress_test_status"] = updates.stress_test_status

    if updates.scheduled_location is not None:
        update_fields.append("scheduled_location = :scheduled_location")
        params["scheduled_location"] = updates.scheduled_location

    if updates.vqi_case_id is not None:
        update_fields.append("vqi_case_id = :vqi_case_id")
        params["vqi_case_id"] = updates.vqi_case_id

    if updates.status is not None:
        update_fields.append("status = CAST(:status AS enum_procedures_status)")
        params["status"] = updates.status

    if updates.surgeon is not None:
        update_fields.append("surgeon = :surgeon")
        params["surgeon"] = updates.surgeon

    if updates.procedure_date is not None:
        update_fields.append("procedure_date = :procedure_date")
        params["procedure_date"] = updates.procedure_date

    if updates.procedure_type is not None:
        update_fields.append("procedure_type = :procedure_type")
        params["procedure_type"] = updates.procedure_type

    if updates.procedure_side is not None:
        update_fields.append("procedure_side = CAST(:procedure_side AS enum_procedures_procedure_side)")
        params["procedure_side"] = updates.procedure_side

    if not update_fields:
        raise HTTPException(status_code=400, detail="No fields to update")

    # Always update timestamp
    update_fields.append('"updatedAt" = NOW()')

    query = f"""
        UPDATE procedures
        SET {', '.join(update_fields)}
        WHERE id = CAST(:procedure_id AS uuid)
        RETURNING id::text
    """

    result = db.execute(text(query), params)
    db.commit()

    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail=f"Procedure {procedure_id} not found")

    # Return updated procedure
    return await get_procedure(procedure_id, db)


@router.post("/procedures", response_model=Dict[str, Any], status_code=201)
async def create_procedure(procedure: ProcedureCreate, db: Session = Depends(get_db)):
    """
    Create a new procedure for a patient.

    This endpoint supports full endovascular planning data including:
    - Indication/ICD-10 codes
    - Access details
    - Inflow/outflow status
    - Vessel anatomy data
    - Planned interventions
    - CPT codes

    Patient name will be looked up from MRN if not provided.
    """
    import json
    from uuid import uuid4

    # Look up patient by MRN to get name if not provided
    patient_name = procedure.patient_name
    if not patient_name:
        patient_query = text("""
            SELECT CONCAT(last_name, ', ', first_name) as full_name
            FROM scc_patients
            WHERE mrn = :mrn
            LIMIT 1
        """)
        patient_result = db.execute(patient_query, {"mrn": procedure.mrn})
        patient_row = patient_result.fetchone()
        if patient_row:
            patient_name = patient_row[0]
        else:
            patient_name = f"Unknown ({procedure.mrn})"

    procedure_id = str(uuid4())

    # Build insert query with all fields
    sql = text("""
        INSERT INTO procedures (
            id, mrn, patient_name, procedure_type, procedure_name, procedure_side,
            procedure_date, scheduled_location, status, surgical_status,
            surgeon, barriers, cardiology_clearance, stress_test_status, vqi_case_id,
            indication, access_details, inflow_status, outflow_status,
            vessel_data, interventions, cpt_codes, findings, results,
            "createdAt", "updatedAt"
        ) VALUES (
            CAST(:id AS uuid),
            :mrn,
            :patient_name,
            :procedure_type,
            :procedure_name,
            CAST(:procedure_side AS enum_procedures_procedure_side),
            :procedure_date,
            :scheduled_location,
            CAST(:status AS enum_procedures_status),
            CAST(:surgical_status AS enum_surgical_status),
            :surgeon,
            CAST(:barriers AS jsonb),
            :cardiology_clearance,
            CAST(:stress_test_status AS enum_stress_test_status),
            :vqi_case_id,
            CAST(:indication AS jsonb),
            CAST(:access_details AS jsonb),
            CAST(:inflow_status AS jsonb),
            CAST(:outflow_status AS jsonb),
            CAST(:vessel_data AS jsonb),
            CAST(:interventions AS jsonb),
            CAST(:cpt_codes AS jsonb),
            :findings,
            :results,
            NOW(),
            NOW()
        )
        RETURNING id::text
    """)

    try:
        result = db.execute(sql, {
            "id": procedure_id,
            "mrn": procedure.mrn,
            "patient_name": patient_name,
            "procedure_type": procedure.procedure_type,
            "procedure_name": procedure.procedure_name,
            "procedure_side": procedure.procedure_side,
            "procedure_date": procedure.procedure_date,
            "scheduled_location": procedure.scheduled_location,
            "status": procedure.status or "draft",
            "surgical_status": procedure.surgical_status or "workup",
            "surgeon": procedure.surgeon,
            "barriers": json.dumps(procedure.barriers or []),
            "cardiology_clearance": procedure.cardiology_clearance,
            "stress_test_status": procedure.stress_test_status,
            "vqi_case_id": procedure.vqi_case_id,
            "indication": json.dumps(procedure.indication or {}),
            "access_details": json.dumps(procedure.access or {}),
            "inflow_status": json.dumps(procedure.inflow or {}),
            "outflow_status": json.dumps(procedure.outflow or {}),
            "vessel_data": json.dumps(procedure.vessel_data or {}),
            "interventions": json.dumps(procedure.interventions or []),
            "cpt_codes": json.dumps(procedure.cpt_codes or []),
            "findings": procedure.findings,
            "results": procedure.results
        })
        db.commit()

        # Return the created procedure
        return {
            "id": procedure_id,
            "mrn": procedure.mrn,
            "patient_name": patient_name,
            "procedure_type": procedure.procedure_type,
            "procedure_name": procedure.procedure_name,
            "procedure_side": procedure.procedure_side,
            "procedure_date": str(procedure.procedure_date) if procedure.procedure_date else None,
            "scheduled_location": procedure.scheduled_location,
            "status": procedure.status or "draft",
            "surgical_status": procedure.surgical_status or "workup",
            "indication": procedure.indication or {},
            "access": procedure.access or {},
            "inflow": procedure.inflow or {},
            "outflow": procedure.outflow or {},
            "vessel_data": procedure.vessel_data or {},
            "interventions": procedure.interventions or [],
            "cpt_codes": procedure.cpt_codes or [],
            "message": "Procedure created successfully"
        }

    except Exception as e:
        db.rollback()
        logger.error(f"Failed to create procedure: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/planning/{mrn}", response_model=Dict[str, Any])
async def get_planning_data(mrn: str, db: Session = Depends(get_db)):
    """
    Get planning data for a patient by MRN.

    Returns the most recent planned procedure with full vessel data,
    interventions, and ICD-10/CPT codes for the workspace to load.
    """
    # Get patient info
    patient_query = text("""
        SELECT id::text, mrn, first_name, last_name
        FROM scc_patients
        WHERE mrn = :mrn
        LIMIT 1
    """)
    patient_result = db.execute(patient_query, {"mrn": mrn})
    patient_row = patient_result.fetchone()

    if not patient_row:
        raise HTTPException(status_code=404, detail=f"Patient with MRN {mrn} not found")

    # Get most recent procedure with planning data
    procedure_query = text("""
        SELECT
            id::text, mrn, patient_name, procedure_type, procedure_name, procedure_side::text,
            procedure_date, scheduled_location, status::text, surgical_status::text,
            indication, access_details, inflow_status, outflow_status,
            vessel_data, interventions, cpt_codes, findings, results,
            "createdAt", "updatedAt"
        FROM procedures
        WHERE mrn = :mrn
        ORDER BY "createdAt" DESC
        LIMIT 1
    """)
    proc_result = db.execute(procedure_query, {"mrn": mrn})
    proc_row = proc_result.fetchone()

    if not proc_row:
        # Return patient info with empty procedure data
        return {
            "patient": {
                "id": patient_row[0],
                "mrn": patient_row[1],
                "name": f"{patient_row[3]}, {patient_row[2]}"
            },
            "procedure": None,
            "indication": {},
            "vessel_data": {},
            "interventions": [],
            "cpt_codes": []
        }

    return {
        "patient": {
            "id": patient_row[0],
            "mrn": patient_row[1],
            "name": f"{patient_row[3]}, {patient_row[2]}"
        },
        "procedure": {
            "id": proc_row[0],
            "mrn": proc_row[1],
            "patient_name": proc_row[2],
            "type": proc_row[3],
            "name": proc_row[4],
            "side": proc_row[5],
            "date": proc_row[6].isoformat() if proc_row[6] else None,
            "location": proc_row[7],
            "status": proc_row[8],
            "surgical_status": proc_row[9],
            "created_at": proc_row[19].isoformat() if proc_row[19] else None,
            "updated_at": proc_row[20].isoformat() if proc_row[20] else None
        },
        "indication": proc_row[10] or {},
        "access": proc_row[11] or {},
        "inflow": proc_row[12] or {},
        "outflow": proc_row[13] or {},
        "vessel_data": proc_row[14] or {},
        "interventions": proc_row[15] or [],
        "cpt_codes": proc_row[16] or [],
        "findings": proc_row[17],
        "results": proc_row[18]
    }


# ==================== Patient Endpoints ====================

@router.get("/patients", response_model=List[Dict[str, Any]])
async def list_patients(
    search: Optional[str] = Query(None, description="Search by name or MRN"),
    active: Optional[bool] = Query(None, description="Filter by active status"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db)
):
    """
    List patients with optional search.

    Searches by:
    - MRN (exact or partial)
    - First name (partial, case-insensitive)
    - Last name (partial, case-insensitive)
    """
    query = """
        SELECT
            id::text, mrn, first_name, last_name, middle_name,
            date_of_birth, age, gender::text, phone_primary, phone_secondary,
            email, address_line1, city, state, zip_code,
            insurance_provider, primary_physician, active,
            "createdAt", "updatedAt"
        FROM scc_patients
        WHERE 1=1
    """
    params = {}

    if search:
        query += """
            AND (
                mrn ILIKE :search
                OR first_name ILIKE :search
                OR last_name ILIKE :search
                OR CONCAT(first_name, ' ', last_name) ILIKE :search
            )
        """
        params["search"] = f"%{search}%"

    if active is not None:
        query += " AND active = :active"
        params["active"] = active

    query += ' ORDER BY last_name, first_name LIMIT :limit OFFSET :offset'
    params["limit"] = limit
    params["offset"] = offset

    result = db.execute(text(query), params)
    rows = result.fetchall()

    patients = []
    for row in rows:
        patients.append({
            "id": row[0],
            "mrn": row[1],
            "first_name": row[2],
            "last_name": row[3],
            "middle_name": row[4],
            "date_of_birth": row[5].isoformat() if row[5] else None,
            "age": row[6],
            "gender": row[7],
            "phone_primary": row[8],
            "phone_secondary": row[9],
            "email": row[10],
            "address_line1": row[11],
            "city": row[12],
            "state": row[13],
            "zip_code": row[14],
            "insurance_provider": row[15],
            "primary_physician": row[16],
            "active": row[17],
            "created_at": row[18].isoformat() if row[18] else None,
            "updated_at": row[19].isoformat() if row[19] else None
        })

    return patients


@router.get("/patients/{mrn}", response_model=Dict[str, Any])
async def get_patient_by_mrn(mrn: str, db: Session = Depends(get_db)):
    """
    Get patient by MRN with related procedures.
    """
    # Get patient
    patient_query = """
        SELECT
            id::text, mrn, first_name, last_name, middle_name,
            date_of_birth, age, gender::text, phone_primary, phone_secondary,
            email, address_line1, address_line2, city, state, zip_code, country,
            emergency_contact_name, emergency_contact_phone, emergency_contact_relationship,
            insurance_provider, insurance_policy_number, insurance_group_number,
            primary_physician, allergies, current_medications, medical_history,
            primary_language, race, ethnicity, marital_status::text,
            ssn_last_four, active, notes, "createdAt", "updatedAt"
        FROM scc_patients
        WHERE mrn = :mrn
    """
    result = db.execute(text(patient_query), {"mrn": mrn})
    row = result.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail=f"Patient with MRN {mrn} not found")

    patient = {
        "id": row[0],
        "mrn": row[1],
        "first_name": row[2],
        "last_name": row[3],
        "middle_name": row[4],
        "date_of_birth": row[5].isoformat() if row[5] else None,
        "age": row[6],
        "gender": row[7],
        "phone_primary": row[8],
        "phone_secondary": row[9],
        "email": row[10],
        "address_line1": row[11],
        "address_line2": row[12],
        "city": row[13],
        "state": row[14],
        "zip_code": row[15],
        "country": row[16],
        "emergency_contact_name": row[17],
        "emergency_contact_phone": row[18],
        "emergency_contact_relationship": row[19],
        "insurance_provider": row[20],
        "insurance_policy_number": row[21],
        "insurance_group_number": row[22],
        "primary_physician": row[23],
        "allergies": row[24],
        "current_medications": row[25],
        "medical_history": row[26],
        "primary_language": row[27],
        "race": row[28],
        "ethnicity": row[29],
        "marital_status": row[30],
        "ssn_last_four": row[31],
        "active": row[32],
        "notes": row[33],
        "created_at": row[34].isoformat() if row[34] else None,
        "updated_at": row[35].isoformat() if row[35] else None
    }

    # Get related procedures
    proc_query = """
        SELECT
            id::text, procedure_type, procedure_side, procedure_date,
            surgical_status::text, status::text, surgeon, scheduled_location
        FROM procedures
        WHERE mrn = :mrn
        ORDER BY procedure_date DESC NULLS LAST
        LIMIT 10
    """
    proc_result = db.execute(text(proc_query), {"mrn": mrn})
    procedures = []
    for prow in proc_result.fetchall():
        procedures.append({
            "id": prow[0],
            "procedure_type": prow[1],
            "procedure_side": prow[2],
            "procedure_date": prow[3].isoformat() if prow[3] else None,
            "surgical_status": prow[4],
            "status": prow[5],
            "surgeon": prow[6],
            "scheduled_location": prow[7]
        })

    patient["procedures"] = procedures
    return patient


@router.post("/patients", response_model=Dict[str, Any], status_code=201)
async def create_patient(patient: PatientBase, db: Session = Depends(get_db)):
    """
    Create a new patient.

    Required fields: mrn, first_name, last_name, date_of_birth
    """
    # Check if MRN already exists
    check_query = "SELECT id FROM scc_patients WHERE mrn = :mrn"
    existing = db.execute(text(check_query), {"mrn": patient.mrn}).fetchone()
    if existing:
        raise HTTPException(status_code=409, detail=f"Patient with MRN {patient.mrn} already exists")

    # Calculate age if not provided
    age = patient.age
    if age is None and patient.date_of_birth:
        today = date.today()
        age = today.year - patient.date_of_birth.year
        if (today.month, today.day) < (patient.date_of_birth.month, patient.date_of_birth.day):
            age -= 1

    query = """
        INSERT INTO scc_patients (
            id, mrn, first_name, last_name, middle_name,
            date_of_birth, age, gender, phone_primary, phone_secondary,
            email, address_line1, address_line2, city, state, zip_code, country,
            emergency_contact_name, emergency_contact_phone, emergency_contact_relationship,
            insurance_provider, insurance_policy_number, insurance_group_number,
            primary_physician, allergies, current_medications, medical_history,
            active, "createdAt", "updatedAt"
        ) VALUES (
            gen_random_uuid(), :mrn, :first_name, :last_name, :middle_name,
            :date_of_birth, :age, CAST(:gender AS enum_patients_gender), :phone_primary, :phone_secondary,
            :email, :address_line1, :address_line2, :city, :state, :zip_code, :country,
            :emergency_contact_name, :emergency_contact_phone, :emergency_contact_relationship,
            :insurance_provider, :insurance_policy_number, :insurance_group_number,
            :primary_physician, :allergies, :current_medications, :medical_history,
            true, NOW(), NOW()
        )
        RETURNING id::text
    """

    params = {
        "mrn": patient.mrn,
        "first_name": patient.first_name,
        "last_name": patient.last_name,
        "middle_name": patient.middle_name,
        "date_of_birth": patient.date_of_birth,
        "age": age,
        "gender": patient.gender or "unknown",
        "phone_primary": patient.phone_primary,
        "phone_secondary": patient.phone_secondary,
        "email": patient.email,
        "address_line1": patient.address_line1,
        "address_line2": patient.address_line2,
        "city": patient.city,
        "state": patient.state,
        "zip_code": patient.zip_code,
        "country": patient.country or "USA",
        "emergency_contact_name": patient.emergency_contact_name,
        "emergency_contact_phone": patient.emergency_contact_phone,
        "emergency_contact_relationship": patient.emergency_contact_relationship,
        "insurance_provider": patient.insurance_provider,
        "insurance_policy_number": patient.insurance_policy_number,
        "insurance_group_number": patient.insurance_group_number,
        "primary_physician": patient.primary_physician,
        "allergies": patient.allergies,
        "current_medications": patient.current_medications,
        "medical_history": patient.medical_history
    }

    result = db.execute(text(query), params)
    db.commit()

    patient_id = result.fetchone()[0]

    return {
        "status": "success",
        "patient_id": patient_id,
        "mrn": patient.mrn,
        "message": "Patient created successfully"
    }


# ==================== Health/Status Endpoint ====================

@router.get("/orcc/status")
async def orcc_status(db: Session = Depends(get_db)):
    """ORCC integration status check."""
    try:
        # Check database connection
        result = db.execute(text("SELECT COUNT(*) FROM procedures"))
        proc_count = result.scalar()

        result = db.execute(text("SELECT COUNT(*) FROM scc_patients"))
        patient_count = result.scalar()

        # Count by surgical status
        status_query = """
            SELECT surgical_status::text, COUNT(*)
            FROM procedures
            WHERE surgical_status IS NOT NULL
            GROUP BY surgical_status
        """
        status_result = db.execute(text(status_query))
        status_counts = {row[0]: row[1] for row in status_result.fetchall()}

        return {
            "status": "healthy",
            "database": "connected",
            "procedures_count": proc_count,
            "patients_count": patient_count,
            "surgical_status_breakdown": status_counts,
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }
    except Exception as e:
        logger.error(f"ORCC status check failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
