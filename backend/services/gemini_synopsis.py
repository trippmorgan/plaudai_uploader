"""
=============================================================================
GEMINI AI CLINICAL SYNOPSIS GENERATOR
=============================================================================

ARCHITECTURAL ROLE:
    This module is the AI SYNTHESIS ENGINE - it aggregates patient data
    from multiple sources and uses Google's Gemini LLM to generate
    comprehensive, human-readable clinical summaries.

DATA FLOW POSITION:
    ┌────────────────────────────────────────────────────────────────────┐
    │                    DATABASE (Source Data)                          │
    │   patients → voice_transcripts → pvi_procedures                   │
    └───────────────┬───────────────────┬────────────────────────────────┘
                    │                   │
                    ▼                   ▼
    ┌────────────────────────────────────────────────────────────────────┐
    │                gemini_synopsis.py (THIS FILE)                      │
    │                                                                    │
    │  ┌──────────────────────────────────────────────────────────────┐ │
    │  │            gather_patient_data()                              │ │
    │  │  Query: Transcripts + Procedures for last N days             │ │
    │  │  Output: Structured dict with demographics, visits, procs    │ │
    │  └──────────────────────────────────────────────────────────────┘ │
    │                               │                                    │
    │                               ▼                                    │
    │  ┌──────────────────────────────────────────────────────────────┐ │
    │  │            build_synopsis_prompt()                            │ │
    │  │  Type-specific prompts:                                      │ │
    │  │  - comprehensive: Full clinical summary (10 sections)        │ │
    │  │  - visit_summary: Last encounter only                        │ │
    │  │  - problem_list: Active medical problems                     │ │
    │  │  - procedure_summary: Recent procedures                      │ │
    │  └──────────────────────────────────────────────────────────────┘ │
    │                               │                                    │
    │                               ▼                                    │
    │  ┌──────────────────────────────────────────────────────────────┐ │
    │  │            Gemini API Call                                    │ │
    │  │  Model: gemini-2.0-flash (fast, cost-effective)              │ │
    │  │  Input: Structured prompt with patient context               │ │
    │  │  Output: Formatted clinical synopsis text                    │ │
    │  └──────────────────────────────────────────────────────────────┘ │
    │                               │                                    │
    │                               ▼                                    │
    │  ┌──────────────────────────────────────────────────────────────┐ │
    │  │            parse_synopsis_sections()                          │ │
    │  │  Extract structured sections from free-text response         │ │
    │  │  Sections: chief_complaint, hpi, medications, assessment...  │ │
    │  └──────────────────────────────────────────────────────────────┘ │
    │                               │                                    │
    │                               ▼                                    │
    │  ┌──────────────────────────────────────────────────────────────┐ │
    │  │            ClinicalSynopsis Record                            │ │
    │  │  Store: synopsis_text, parsed sections, token usage          │ │
    │  │  Cache: Valid for 24 hours (avoid regeneration)              │ │
    │  └──────────────────────────────────────────────────────────────┘ │
    └────────────────────────────────────────────────────────────────────┘

CRITICAL DESIGN PRINCIPLES:

    1. CACHING WITH 24-HOUR TTL:
       Synopses are expensive to generate (~1-2 seconds, API costs).
       - Check for existing synopsis < 24 hours old
       - force_regenerate=True bypasses cache
       - Prevents redundant API calls

    2. SYNOPSIS TYPE SPECIALIZATION:
       Different clinical needs require different outputs:
       - comprehensive: Full H&P-style documentation
       - visit_summary: Quick single-encounter summary
       - problem_list: Active problems with treatments
       - procedure_summary: Surgical history focus

    3. TOKEN TRACKING:
       AI cost management via token counting:
       - tokens_used stored in database
       - Enables cost analysis per patient/synopsis
       - Helps optimize prompt length

    4. SECTION PARSING:
       AI output parsed into structured fields:
       - Enables frontend display by section
       - Allows section-specific queries
       - Provides consistency across synopses

FUNCTION REFERENCE:

    gather_patient_data(db, patient_id, days_back=365) -> Dict
        PARAMS:
          db: SQLAlchemy Session
          patient_id: int - Target patient
          days_back: int - Lookback window (default 365 days)
        RETURNS: Dict with:
          - demographics: {name, mrn, dob, age, birth_sex, race, zip}
          - transcripts: List of {date, visit_type, title, raw, plaud, tags}
          - procedures: List of {date, surgeon, indication, rutherford, ...}
          - date_range: {start, end}
        RAISES: ValueError if patient not found

    calculate_age(dob) -> int
        PARAMS: dob - Date of birth
        RETURNS: Age in years (birthday-aware)

    build_synopsis_prompt(patient_data, synopsis_type) -> str
        PARAMS:
          patient_data: Dict from gather_patient_data()
          synopsis_type: "comprehensive" | "visit_summary" | "problem_list" | "procedure_summary"
        RETURNS: Complete prompt string for Gemini
        INCLUDES: Demographics, last 5 transcripts, last 3 procedures, task instructions

    generate_clinical_synopsis(db, patient_id, synopsis_type, days_back, force_regenerate) -> ClinicalSynopsis
        PARAMS:
          db: SQLAlchemy Session
          patient_id: int - Target patient
          synopsis_type: str - Type of synopsis
          days_back: int - Lookback window
          force_regenerate: bool - Bypass cache
        RETURNS: ClinicalSynopsis ORM object
        RAISES: ValueError if no API key or patient not found

    parse_synopsis_sections(synopsis_text) -> Dict[str, str]
        PARAMS: synopsis_text - Raw Gemini output
        RETURNS: Dict mapping section names to content
        SECTIONS: chief_complaint, history_present_illness, past_medical_history,
                  medications, allergies, social_history, physical_exam, assessment_plan

    get_latest_synopsis(db, patient_id, synopsis_type) -> ClinicalSynopsis|None
        Query for most recent synopsis of given type

    get_all_synopses(db, patient_id) -> List[ClinicalSynopsis]
        Query for all synopses for a patient

    get_patient_summary(db, mrn) -> Dict
        Quick lookup by MRN returning patient info + latest synopsis

PROMPT ENGINEERING:
    The comprehensive synopsis prompt requests 10 sections:
    1. Chief Complaint / Presenting Problems
    2. History of Present Illness
    3. Past Medical History (vascular focus)
    4. Medications
    5. Allergies
    6. Social History (smoking, activity)
    7. Review of Systems
    8. Physical Examination
    9. Assessment and Plan
    10. Pending Items

API CONFIGURATION:
    - Model: GEMINI_MODEL from config (default: gemini-2.0-flash)
    - API Key: GOOGLE_API_KEY from environment
    - No streaming (full response returned)
    - Default timeout via google-generativeai library

SECURITY MODEL:
    - API key stored in environment, not code
    - No PHI sent to logs (only IDs)
    - Token counts tracked (cost monitoring)

COST OPTIMIZATION:
    - 24-hour cache prevents redundant calls
    - Transcript truncation (500 chars) reduces tokens
    - Limited to 5 transcripts + 3 procedures per synopsis

MAINTENANCE NOTES:
    - Change synopsis types: Add to PROMPTS dict and build_synopsis_prompt()
    - Adjust cache TTL: Modify timedelta(hours=24) in generate_clinical_synopsis()
    - Add section markers: Update markers dict in parse_synopsis_sections()

ERROR HANDLING:
    - Missing API key: Raises ValueError with clear message
    - Patient not found: Raises ValueError
    - Gemini API failure: Logs error, re-raises
    - Empty data: Warns but still attempts generation

VERSION: 2.0.0
LAST UPDATED: 2025-12
=============================================================================
"""
import google.generativeai as genai
from sqlalchemy.orm import Session
from typing import Dict, List, Optional
import json
import logging
import time
from datetime import datetime, timedelta

from ..models import Patient, VoiceTranscript, PVIProcedure, ClinicalSynopsis
from ..config import GOOGLE_API_KEY, GEMINI_MODEL

# Initialize logger
logger = logging.getLogger(__name__)

# Configure Gemini AI
if GOOGLE_API_KEY:
    genai.configure(api_key=GOOGLE_API_KEY)
    logger.info(f"🤖 Gemini AI configured with model: {GEMINI_MODEL}")
else:
    logger.warning("⚠️ GOOGLE_API_KEY not configured - AI synopsis generation disabled")

# ==================== Data Aggregation ====================

def gather_patient_data(
    db: Session,
    patient_id: int,
    days_back: int = 365
) -> Dict[str, any]:
    """
    Gather all available patient data from database with logging
    """
    logger.debug(f"🔍 Gathering clinical data for Patient ID: {patient_id} (Last {days_back} days)")
    
    patient = db.query(Patient).filter_by(id=patient_id).first()
    if not patient:
        logger.error(f"❌ Patient {patient_id} not found during data gathering")
        raise ValueError(f"Patient {patient_id} not found")
    
    cutoff_date = datetime.now() - timedelta(days=days_back)
    
    # Get all voice transcripts
    transcripts = db.query(VoiceTranscript).filter(
        VoiceTranscript.patient_id == patient_id,
        VoiceTranscript.created_at >= cutoff_date
    ).order_by(VoiceTranscript.recording_date.desc()).all()
    
    # Get all procedures
    procedures = db.query(PVIProcedure).filter(
        PVIProcedure.patient_id == patient_id,
        PVIProcedure.procedure_date >= cutoff_date.date()
    ).order_by(PVIProcedure.procedure_date.desc()).all()
    
    logger.info(f"📊 Data Found: {len(transcripts)} transcripts, {len(procedures)} procedures")
    
    # Organize data
    patient_data = {
        "demographics": {
            "name": f"{patient.first_name} {patient.last_name}",
            "mrn": patient.athena_mrn,
            "dob": str(patient.dob),
            "age": calculate_age(patient.dob),
            "birth_sex": patient.birth_sex,
            "race": patient.race,
            "zip_code": patient.zip_code
        },
        "transcripts": [
            {
                "date": t.recording_date or t.created_at,
                "visit_type": t.visit_type,
                "title": t.transcript_title,
                "raw_transcript": t.raw_transcript,
                "plaud_note": t.plaud_note,
                "tags": t.tags
            }
            for t in transcripts
        ],
        "procedures": [
            {
                "date": p.procedure_date,
                "surgeon": p.surgeon_name,
                "indication": p.indication,
                "rutherford": p.rutherford_status,
                "arteries_treated": p.arteries_treated,
                "treatment_success": p.treatment_success,
                "complications": p.complications,
                "disposition": p.disposition_status
            }
            for p in procedures
        ],
        "date_range": {
            "start": cutoff_date.date(),
            "end": datetime.now().date()
        }
    }
    
    return patient_data

def calculate_age(dob):
    """Calculate age from date of birth"""
    today = datetime.now().date()
    age = today.year - dob.year
    if today.month < dob.month or (today.month == dob.month and today.day < dob.day):
        age -= 1
    return age

# ==================== Prompt Engineering ====================

def build_synopsis_prompt(patient_data: Dict, synopsis_type: str = "comprehensive") -> str:
    """
    Build AI prompt based on patient data and desired synopsis type
    """
    logger.debug(f"🏗️ Building prompt for type: {synopsis_type}")
    
    name = patient_data["demographics"]["name"]
    mrn = patient_data["demographics"]["mrn"]
    age = patient_data["demographics"]["age"]
    
    base_prompt = f"""You are an expert vascular surgeon creating clinical documentation.

PATIENT INFORMATION:
Name: {name}
MRN: {mrn}
Age: {age}
DOB: {patient_data["demographics"]["dob"]}

"""
    
    # Add transcript data
    if patient_data["transcripts"]:
        base_prompt += "RECENT CLINICAL ENCOUNTERS:\n"
        count = 0
        for i, t in enumerate(patient_data["transcripts"][:5], 1):  # Last 5 transcripts
            base_prompt += f"\n--- Visit {i}: {t['date'].strftime('%Y-%m-%d')} ---\n"
            base_prompt += f"Type: {t['visit_type'] or 'Not specified'}\n"
            if t['plaud_note']:
                base_prompt += f"PlaudAI Note:\n{t['plaud_note']}\n"
            if t['raw_transcript']:
                base_prompt += f"Raw Transcript:\n{t['raw_transcript'][:500]}...\n"
            count += 1
        logger.debug(f"Included {count} encounters in prompt")
    
    # Add procedure data
    if patient_data["procedures"]:
        base_prompt += "\n\nRECENT PROCEDURES:\n"
        count = 0
        for i, p in enumerate(patient_data["procedures"][:3], 1):  # Last 3 procedures
            base_prompt += f"\n--- Procedure {i}: {p['date']} ---\n"
            base_prompt += f"Surgeon: {p['surgeon']}\n"
            base_prompt += f"Indication: {p['indication']}\n"
            base_prompt += f"Classification: {p['rutherford']}\n"
            base_prompt += f"Vessels treated: {json.dumps(p['arteries_treated'])}\n"
            base_prompt += f"Success: {'Yes' if p['treatment_success'] else 'No'}\n"
            if p['complications']:
                base_prompt += f"Complications: {json.dumps(p['complications'])}\n"
            count += 1
        logger.debug(f"Included {count} procedures in prompt")
    
    # Add type-specific instructions
    if synopsis_type == "comprehensive":
        base_prompt += """

TASK: Create a comprehensive clinical synopsis in standard medical format.

Include the following sections:
1. CHIEF COMPLAINT / PRESENTING PROBLEMS
2. HISTORY OF PRESENT ILLNESS
3. PAST MEDICAL HISTORY (with relevant vascular history)
4. MEDICATIONS (extract from notes)
5. ALLERGIES (if mentioned)
6. SOCIAL HISTORY (smoking status, activity level)
7. REVIEW OF SYSTEMS (relevant positives and negatives)
8. PHYSICAL EXAMINATION (from most recent notes)
9. ASSESSMENT AND PLAN
   - Problem list with severity
   - Current treatment plan
   - Follow-up recommendations
10. PENDING ITEMS
    - Tests ordered but not resulted
    - Follow-up appointments needed

Format as clear, professional medical documentation.
"""
    elif synopsis_type == "visit_summary":
        base_prompt += """
TASK: Create a concise visit summary from the most recent encounter.
Include: Date/type, Reason, Findings, Decisions, Plan.
Format as brief clinical note (3-5 paragraphs).
"""
    elif synopsis_type == "problem_list":
        base_prompt += """
TASK: Extract and organize current active medical problems.
Create a numbered problem list with: Name, Severity, Treatment, Last Date.
Prioritize vascular and cardiovascular problems.
"""
    elif synopsis_type == "procedure_summary":
        base_prompt += """
TASK: Summarize recent vascular procedures and outcomes.
Format as structured procedure report.
"""
    
    return base_prompt

# ==================== AI Generation ====================

def generate_clinical_synopsis(
    db: Session,
    patient_id: int,
    synopsis_type: str = "comprehensive",
    days_back: int = 365,
    force_regenerate: bool = False
) -> ClinicalSynopsis:
    """
    Generate AI-powered clinical synopsis from patient data
    """
    logger.info(f"🧠 Requesting AI Synopsis: Patient {patient_id} | Type: {synopsis_type}")
    
    if not GOOGLE_API_KEY:
        logger.error("❌ API Key missing")
        raise ValueError("GOOGLE_API_KEY not configured - cannot generate synopsis")
    
    # Check if recent synopsis exists
    if not force_regenerate:
        recent = db.query(ClinicalSynopsis).filter(
            ClinicalSynopsis.patient_id == patient_id,
            ClinicalSynopsis.synopsis_type == synopsis_type,
            ClinicalSynopsis.created_at >= datetime.now() - timedelta(hours=24)
        ).first()
        
        if recent:
            logger.info(f"✅ Using valid cached synopsis (ID: {recent.id}) created {recent.created_at}")
            return recent
        else:
            logger.info("ℹ️ No recent cache found. Generating new synopsis...")
    else:
        logger.info("🔄 Force regeneration requested.")
    
    # Gather patient data
    start_time = time.time()
    patient_data = gather_patient_data(db, patient_id, days_back)
    
    # Check if there is actually data to summarize
    if not patient_data["transcripts"] and not patient_data["procedures"]:
        logger.warning("⚠️ No clinical data found for this patient. AI result may be empty.")
    
    # Build prompt
    prompt = build_synopsis_prompt(patient_data, synopsis_type)
    
    # Generate with Gemini
    logger.info(f"🚀 Sending request to Gemini ({len(prompt)} chars)...")
    try:
        model = genai.GenerativeModel(GEMINI_MODEL)
        response = model.generate_content(prompt)
        
        synopsis_text = response.text
        tokens_used = response.usage_metadata.total_token_count if hasattr(response, 'usage_metadata') else 0
        
        elapsed_time = time.time() - start_time
        logger.info(f"✨ AI Generation Complete in {elapsed_time:.2f}s. Tokens used: {tokens_used}")
        
    except Exception as e:
        logger.error(f"❌ Gemini generation failed: {e}", exc_info=True)
        raise
    
    # Parse structured sections from response
    sections = parse_synopsis_sections(synopsis_text)
    logger.debug(f"📋 Parsed {len(sections)} structured sections from response")
    
    # Create synopsis record
    synopsis = ClinicalSynopsis(
        patient_id=patient_id,
        synopsis_text=synopsis_text,
        synopsis_type=synopsis_type,
        data_sources={
            "transcripts": len(patient_data["transcripts"]),
            "procedures": len(patient_data["procedures"])
        },
        source_date_range={
            "start": str(patient_data["date_range"]["start"]),
            "end": str(patient_data["date_range"]["end"])
        },
        ai_model=GEMINI_MODEL,
        tokens_used=tokens_used,
        chief_complaint=sections.get("chief_complaint"),
        history_present_illness=sections.get("history_present_illness"),
        past_medical_history=sections.get("past_medical_history"),
        medications=sections.get("medications"),
        allergies=sections.get("allergies"),
        social_history=sections.get("social_history"),
        physical_exam=sections.get("physical_exam"),
        assessment_plan=sections.get("assessment_plan")
    )
    
    db.add(synopsis)
    db.commit()
    db.refresh(synopsis)
    
    logger.info(f"💾 Synopsis saved to database. ID: {synopsis.id}")
    return synopsis

# ==================== Section Parsing ====================

def parse_synopsis_sections(synopsis_text: str) -> Dict[str, any]:
    """
    Parse structured sections from AI-generated synopsis
    """
    sections = {}
    
    # Define section markers
    markers = {
        "chief_complaint": ["CHIEF COMPLAINT", "PRESENTING PROBLEMS"],
        "history_present_illness": ["HISTORY OF PRESENT ILLNESS", "HPI"],
        "past_medical_history": ["PAST MEDICAL HISTORY", "PMH"],
        "medications": ["MEDICATIONS", "CURRENT MEDICATIONS"],
        "allergies": ["ALLERGIES", "DRUG ALLERGIES"],
        "social_history": ["SOCIAL HISTORY"],
        "physical_exam": ["PHYSICAL EXAMINATION", "PHYSICAL EXAM", "EXAM"],
        "assessment_plan": ["ASSESSMENT AND PLAN", "ASSESSMENT", "PLAN"]
    }
    
    lines = synopsis_text.split('\n')
    current_section = None
    current_content = []
    
    for line in lines:
        line_upper = line.strip().upper()
        
        # Check if line is a section header
        for section_key, section_markers in markers.items():
            if any(marker in line_upper for marker in section_markers):
                # Save previous section
                if current_section and current_content:
                    sections[current_section] = '\n'.join(current_content).strip()
                
                # Start new section
                current_section = section_key
                current_content = []
                break
        else:
            # Add to current section
            if current_section and line.strip():
                current_content.append(line.strip())
    
    # Save last section
    if current_section and current_content:
        sections[current_section] = '\n'.join(current_content).strip()
    
    return sections

# ==================== Retrieval Functions ====================

def get_latest_synopsis(
    db: Session,
    patient_id: int,
    synopsis_type: str = "comprehensive"
) -> Optional[ClinicalSynopsis]:
    """Get most recent synopsis for patient"""
    return db.query(ClinicalSynopsis).filter(
        ClinicalSynopsis.patient_id == patient_id,
        ClinicalSynopsis.synopsis_type == synopsis_type
    ).order_by(ClinicalSynopsis.created_at.desc()).first()

def get_all_synopses(
    db: Session,
    patient_id: int
) -> List[ClinicalSynopsis]:
    """Get all synopses for patient"""
    return db.query(ClinicalSynopsis).filter(
        ClinicalSynopsis.patient_id == patient_id
    ).order_by(ClinicalSynopsis.created_at.desc()).all()

# ==================== Quick Access Functions ====================

def get_patient_summary(db: Session, mrn: str) -> Dict:
    """
    Quick patient summary by MRN - for clinical use
    """
    logger.info(f"🔎 Clinical Lookup: Summary requested for MRN {mrn}")
    
    patient = db.query(Patient).filter_by(athena_mrn=mrn).first()
    if not patient:
        logger.warning(f"❌ Patient lookup failed: MRN {mrn} not found")
        raise ValueError(f"Patient with MRN {mrn} not found")
    
    synopsis = get_latest_synopsis(db, patient.id, "comprehensive")
    
    if synopsis:
        logger.info(f"✅ Found synopsis for MRN {mrn} (Date: {synopsis.created_at.date()})")
    else:
        logger.info(f"ℹ️ No synopsis found for MRN {mrn}")
    
    return {
        "patient": {
            "name": f"{patient.first_name} {patient.last_name}",
            "mrn": patient.athena_mrn,
            "dob": str(patient.dob),
            "age": calculate_age(patient.dob)
        },
        "synopsis": synopsis.synopsis_text if synopsis else None,
        "synopsis_date": synopsis.created_at if synopsis else None,
        "has_recent_synopsis": synopsis and (datetime.now() - synopsis.created_at).days < 7
    }