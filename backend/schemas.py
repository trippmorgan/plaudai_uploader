"""
PlaudAI Uploader - Pydantic Schemas for Validation
"""
from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any
from datetime import date, datetime

# ==================== Patient Schemas ====================

class PatientBase(BaseModel):
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    dob: date
    athena_mrn: str = Field(..., min_length=1, max_length=20)
    birth_sex: Optional[str] = None
    race: Optional[str] = None
    zip_code: Optional[str] = None
    center_site_location: Optional[str] = None
    insurance_type: Optional[str] = None

class PatientCreate(PatientBase):
    pass

class PatientResponse(PatientBase):
    id: int
    created_at: datetime
    
    class Config:
        from_attributes = True

# ==================== Transcript Schemas ====================

class TranscriptBase(BaseModel):
    transcript_title: Optional[str] = "PlaudAI Voice Note"
    raw_transcript: str = Field(..., min_length=10, description="Raw voice-to-text transcript from PlaudAI")
    plaud_note: Optional[str] = Field(None, description="PlaudAI's formatted/configured note")
    visit_type: Optional[str] = Field(None, description="e.g., Office visit, Procedure, Follow-up")
    recording_duration: Optional[float] = None
    recording_date: Optional[datetime] = None
    plaud_recording_id: Optional[str] = None

class TranscriptUpload(TranscriptBase):
    # Patient info
    first_name: str
    last_name: str
    dob: date
    athena_mrn: str
    
    # ✅ ADD THESE THREE NEW LINES
    record_category: Optional[str] = "office_visit"  # operative_note, imaging, lab_result, office_visit
    record_subtype: Optional[str] = None  # e.g., "CT Abdomen", "Carotid Duplex"
    
    
    # Optional patient demographics
    birth_sex: Optional[str] = None
    race: Optional[str] = None
    zip_code: Optional[str] = None

class TranscriptResponse(TranscriptBase):
    id: int
    patient_id: int
    tags: Optional[List[str]] = []
    confidence_score: Optional[float] = None
    is_processed: bool
    created_at: datetime
    
    class Config:
        from_attributes = True

# ==================== Clinical Synopsis Schemas ====================

class SynopsisRequest(BaseModel):
    synopsis_type: str = Field(default="comprehensive", 
                               description="comprehensive, visit_summary, problem_list, procedure_summary")
    days_back: int = Field(default=365, ge=1, le=3650)
    force_regenerate: bool = False

class SynopsisResponse(BaseModel):
    synopsis_id: int
    patient_id: int
    synopsis_type: str
    synopsis_text: str
    ai_model: str
    tokens_used: Optional[int]
    data_sources: Dict[str, Any]
    generated_at: datetime
    
    # Structured sections (if available)
    chief_complaint: Optional[str] = None
    history_present_illness: Optional[str] = None
    assessment_plan: Optional[str] = None
    
    class Config:
        from_attributes = True

class PatientSummary(BaseModel):
    patient: Dict[str, Any]
    synopsis: Optional[str]
    synopsis_date: Optional[datetime]
    has_recent_synopsis: bool

# ==================== PVI Procedure Schemas ====================

class PVIProcedureBase(BaseModel):
    # Basic info
    procedure_date: date
    surgeon_name: Optional[str] = None
    assistant_names: Optional[str] = None
    
    # Demographics
    smoking_history: Optional[str] = None
    comorbidities: Optional[List[str]] = None
    stress_testing: Optional[str] = None
    functional_status: Optional[str] = None
    living_status: Optional[str] = None
    ambulation_status: Optional[str] = None
    creatinine: Optional[float] = None
    transfer_from_other_center: Optional[bool] = None
    
    # Prior medications
    prior_antiplatelet: Optional[bool] = None
    prior_statin: Optional[bool] = None
    prior_beta_blocker: Optional[bool] = None
    prior_ace_inhibitor: Optional[bool] = None
    prior_arb: Optional[bool] = None
    prior_anticoagulation: Optional[bool] = None
    prior_cilostazol: Optional[bool] = None
    
    # History
    indication: Optional[str] = None
    rutherford_status: Optional[str] = None
    aneurysm_vs_occlusive: Optional[str] = None
    prior_inflow_intervention: Optional[bool] = None
    prior_wifi: Optional[str] = None
    prior_amputation: Optional[bool] = None
    preop_abi: Optional[float] = None
    preop_tbi: Optional[float] = None
    
    # Procedure details
    covid_status: Optional[str] = None
    access_site: Optional[str] = None
    sheath_size: Optional[str] = None
    closure_method: Optional[str] = None
    concomitant_endarterectomy: Optional[bool] = None
    radiation_exposure: Optional[float] = None
    contrast_volume: Optional[float] = None
    nephropathy_prophylaxis: Optional[bool] = None
    
    # Treatment
    arteries_treated: Optional[List[str]] = None
    arteries_locations: Optional[List[str]] = None
    tasc_grade: Optional[str] = None
    treated_length: Optional[float] = None
    occlusion_length: Optional[float] = None
    calcification_grade: Optional[str] = None
    device_details: Optional[Dict[str, Any]] = None
    treatment_success: Optional[bool] = None
    treatment_failure_reason: Optional[str] = None
    
    # Post-procedure
    complications: Optional[List[str]] = None
    disposition_status: Optional[str] = None
    discharge_medications: Optional[List[str]] = None

class PVIProcedureCreate(PVIProcedureBase):
    patient_id: int
    transcript_id: Optional[int] = None

class PVIProcedureResponse(PVIProcedureBase):
    id: int
    patient_id: int
    transcript_id: Optional[int] = None
    created_at: datetime
    
    class Config:
        from_attributes = True

# ==================== Upload Response ====================

class UploadResponse(BaseModel):
    status: str = "success"
    message: str
    patient_id: int
    transcript_id: int
    tags: List[str]
    confidence_score: Optional[float] = None
    warnings: Optional[List[str]] = []
    
# ==================== Batch Upload ====================

class BatchUploadItem(BaseModel):
    transcript_title: str
    transcript_text: str
    patient_data: PatientCreate

class BatchUploadRequest(BaseModel):
    items: List[BatchUploadItem] = Field(..., min_items=1, max_items=50)

class BatchUploadResponse(BaseModel):
    status: str
    total: int
    successful: int
    failed: int
    results: List[Dict[str, Any]]