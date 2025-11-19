"""
PlaudAI Uploader - Database ORM Models
Enhanced with PVI Registry fields
"""
from sqlalchemy import Column, Integer, String, Text, Date, DateTime, JSON, Float, Boolean, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from .db import Base

class Patient(Base):
    """Patient demographic information"""
    __tablename__ = "patients"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    first_name = Column(String(100))
    last_name = Column(String(100))
    dob = Column(Date)
    athena_mrn = Column(String(20), unique=True, nullable=False, index=True)
    
    # Demographics (PVI Registry)
    birth_sex = Column(String(10))  # M/F/Other
    race = Column(String(50))
    zip_code = Column(String(10))
    
    # Clinical info
    center_site_location = Column(String(100))
    insurance_type = Column(String(50))
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    transcripts = relationship("VoiceTranscript", back_populates="patient", cascade="all, delete-orphan")
    procedures = relationship("PVIProcedure", back_populates="patient", cascade="all, delete-orphan")
    # ✅ This fixes your "Mapper has no property synopses" error
    synopses = relationship("ClinicalSynopsis", back_populates="patient", cascade="all, delete-orphan")

class VoiceTranscript(Base):
    """Voice transcript from PlaudAI with parsing results"""
    __tablename__ = "voice_transcripts"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False, index=True)
    
    # PlaudAI specific data
    plaud_recording_id = Column(String(100))  # Original PlaudAI recording ID
    raw_transcript = Column(Text, nullable=False)  # Raw voice-to-text transcript
    plaud_note = Column(Text)  # PlaudAI's configured/formatted note
    recording_duration = Column(Float)  # Duration in seconds
    recording_date = Column(DateTime)  # When recording was made
    
    # Transcript metadata
    visit_date = Column(DateTime(timezone=True), server_default=func.now())
    visit_type = Column(String(100))  # Office visit, procedure, follow-up, etc.
    transcript_title = Column(String(200))
    
    # Parsing results
    tags = Column(JSON)  # Auto-generated medical tags
    confidence_score = Column(Float)  # AI confidence in parsing
    
    # Processing status
    is_processed = Column(Boolean, default=False)
    processing_notes = Column(Text)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    patient = relationship("Patient", back_populates="transcripts")
    procedure = relationship("PVIProcedure", back_populates="transcript", uselist=False)
    clinical_synopsis = relationship("ClinicalSynopsis", back_populates="transcript", uselist=False)

class ClinicalSynopsis(Base):
    """AI-generated clinical synopsis from patient data"""
    __tablename__ = "clinical_synopses"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False, index=True)
    transcript_id = Column(Integer, ForeignKey("voice_transcripts.id"), index=True)
    
    # Synopsis content
    synopsis_text = Column(Text, nullable=False)  # AI-generated summary
    synopsis_type = Column(String(50))  # comprehensive, visit_summary, problem_list, etc.
    
    # Source data used
    data_sources = Column(JSON)  # List of tables/records used
    source_date_range = Column(JSON)  # {start: date, end: date}
    
    # AI metadata
    ai_model = Column(String(50))  # gemini-2.0-flash, local-llama, etc.
    generation_timestamp = Column(DateTime(timezone=True), server_default=func.now())
    tokens_used = Column(Integer)
    
    # Clinical sections (JSON structure)
    chief_complaint = Column(Text)
    history_present_illness = Column(Text)
    past_medical_history = Column(JSON)  # Structured list
    medications = Column(JSON)  # Current meds list
    allergies = Column(JSON)
    social_history = Column(Text)
    family_history = Column(Text)
    review_of_systems = Column(JSON)
    physical_exam = Column(Text)
    assessment_plan = Column(Text)
    
    # Follow-up tracking
    follow_up_needed = Column(Boolean)
    follow_up_date = Column(Date)
    pending_tests = Column(JSON)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    patient = relationship("Patient", back_populates="synopses")
    transcript = relationship("VoiceTranscript", back_populates="clinical_synopsis")

class PVIProcedure(Base):
    """Peripheral Vascular Intervention Registry Data"""
    __tablename__ = "pvi_procedures"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=False, index=True)
    transcript_id = Column(Integer, ForeignKey("voice_transcripts.id"), index=True)
    
    # Basic Info
    procedure_date = Column(Date, nullable=False)
    surgeon_name = Column(String(100))
    assistant_names = Column(Text)
    
    # Demographics for this procedure
    smoking_history = Column(String(50))  # Never/Former/Current
    comorbidities = Column(JSON)  # List of conditions
    stress_testing = Column(String(50))
    functional_status = Column(String(50))
    living_status = Column(String(50))
    ambulation_status = Column(String(50))
    creatinine = Column(Float)
    transfer_from_other_center = Column(Boolean)
    
    # Prior medications (PVI focused)
    prior_antiplatelet = Column(Boolean)
    prior_statin = Column(Boolean)
    prior_beta_blocker = Column(Boolean)
    prior_ace_inhibitor = Column(Boolean)
    prior_arb = Column(Boolean)
    prior_anticoagulation = Column(Boolean)
    prior_cilostazol = Column(Boolean)
    
    # History
    indication = Column(String(100))  # Acute/Chronic Rutherford
    rutherford_status = Column(String(50))
    aneurysm_vs_occlusive = Column(String(50))
    prior_inflow_intervention = Column(Boolean)
    prior_wifi = Column(String(50))
    prior_amputation = Column(Boolean)
    preop_abi = Column(Float)
    preop_tbi = Column(Float)
    
    # Procedure Details
    covid_status = Column(String(50))
    access_site = Column(String(100))
    sheath_size = Column(String(20))
    closure_method = Column(String(100))
    concomitant_endarterectomy = Column(Boolean)
    radiation_exposure = Column(Float)  # mGy
    contrast_volume = Column(Float)  # mL
    nephropathy_prophylaxis = Column(Boolean)
    
    # Treatment specifics
    arteries_treated = Column(JSON)  # List of arteries
    arteries_locations = Column(JSON)  # Anatomical locations
    tasc_grade = Column(String(10))  # A/B/C/D
    treated_length = Column(Float)  # cm
    occlusion_length = Column(Float)  # cm
    calcification_grade = Column(String(50))
    
    # Devices and techniques
    device_details = Column(JSON)
    treatment_success = Column(Boolean)
    treatment_failure_reason = Column(Text)
    pharmacologic_intervention = Column(JSON)
    mechanical_thrombectomy = Column(Boolean)
    embolic_protection_used = Column(Boolean)
    reentry_device_used = Column(Boolean)
    final_technical_result = Column(String(50))
    
    # Post-procedure
    complications = Column(JSON)
    remote_lesion_dissection = Column(Boolean)
    target_lesion_dissection = Column(Boolean)
    perforation_treatment = Column(Text)
    thrombosis_treatment = Column(Text)
    pseudoaneurysm_treatment = Column(Text)
    amputation_level = Column(String(50))
    amputation_planning = Column(Text)
    
    # Discharge
    disposition_status = Column(String(50))
    discharge_medications = Column(JSON)
    mortality = Column(Boolean, default=False)
    mortality_date = Column(Date)
    
    # Follow-up (30 day)
    followup_30day_captured = Column(Boolean, default=False)
    readmission_30day = Column(Boolean)
    readmission_reason = Column(Text)
    reintervention_30day = Column(Boolean)
    reintervention_type = Column(Text)
    
    # LTFU (9-21 months)
    ltfu_captured = Column(Boolean, default=False)
    ltfu_months = Column(Integer)
    ltfu_smoking_status = Column(String(50))
    ltfu_living_status = Column(String(50))
    ltfu_mortality = Column(Boolean)
    ltfu_medications = Column(JSON)
    ltfu_ambulation = Column(String(50))
    ltfu_ipsilateral_symptoms = Column(Text)
    ltfu_patency_documentation = Column(Text)
    ltfu_ipsilateral_abi = Column(Float)
    ltfu_ipsilateral_tbi = Column(Float)
    ltfu_reintervention = Column(Boolean)
    ltfu_reintervention_type = Column(Text)
    ltfu_amputation_since_discharge = Column(Boolean)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    patient = relationship("Patient", back_populates="procedures")
    transcript = relationship("VoiceTranscript", back_populates="procedure")