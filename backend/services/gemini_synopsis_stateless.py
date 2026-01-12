"""
=============================================================================
STATELESS GEMINI AI SYNOPSIS GENERATOR
=============================================================================

VERSION: 2.0.0 - Refactored for SCC Integration
PURPOSE: Pure AI processing - no database dependencies

ENDPOINTS SERVED:
    POST /api/synopsis - Generate AI clinical synopsis from provided text

DATA FLOW:
    SCC Backend → POST /api/synopsis → {transcript_text, patient_context}
                                     ↓
                              Gemini API Call
                                     ↓
                              {synopsis, sections, model, tokens}

REMOVED (handled by SCC):
    - Database queries (gather_patient_data)
    - Synopsis caching (get_latest_synopsis)
    - Patient lookups (get_patient_summary)

KEPT:
    - build_synopsis_prompt() - prompt engineering
    - parse_synopsis_sections() - output parsing
    - calculate_age() - utility function
    - Gemini API integration

=============================================================================
"""
import google.generativeai as genai
from typing import Dict, Optional
import logging
import time
import os

# Initialize logger
logger = logging.getLogger(__name__)

# Get config from environment
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash-exp")

# Configure Gemini AI
if GOOGLE_API_KEY:
    genai.configure(api_key=GOOGLE_API_KEY)
    logger.info(f"Gemini AI configured with model: {GEMINI_MODEL}")
else:
    logger.warning("GOOGLE_API_KEY not configured - AI synopsis generation disabled")


def calculate_age(dob_str: str) -> Optional[int]:
    """Calculate age from date of birth string (YYYY-MM-DD)"""
    if not dob_str:
        return None
    try:
        from datetime import datetime
        dob = datetime.strptime(dob_str, "%Y-%m-%d").date()
        today = datetime.now().date()
        age = today.year - dob.year
        if today.month < dob.month or (today.month == dob.month and today.day < dob.day):
            age -= 1
        return age
    except Exception:
        return None


def build_synopsis_prompt(
    transcript_text: str,
    patient_context: Optional[Dict] = None,
    style: str = "comprehensive"
) -> str:
    """
    Build AI prompt for synopsis generation

    Args:
        transcript_text: Raw transcript or PlaudAI note
        patient_context: Optional {name, mrn, age, dob} from SCC
        style: "comprehensive" | "visit_summary" | "problem_list"
    """
    # Build patient header if context provided
    patient_header = ""
    if patient_context:
        patient_header = f"""
PATIENT INFORMATION:
Name: {patient_context.get('name', 'Unknown')}
MRN: {patient_context.get('mrn', 'Unknown')}
Age: {patient_context.get('age', 'Unknown')}
DOB: {patient_context.get('dob', 'Unknown')}
"""

    base_prompt = f"""You are an expert vascular surgeon creating clinical documentation.
{patient_header}
CLINICAL ENCOUNTER:
{transcript_text}

"""

    # Add style-specific instructions
    if style == "comprehensive":
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
8. PHYSICAL EXAMINATION (from notes)
9. ASSESSMENT AND PLAN
   - Problem list with severity
   - Current treatment plan
   - Follow-up recommendations
10. PENDING ITEMS
    - Tests ordered but not resulted
    - Follow-up appointments needed

Format as clear, professional medical documentation.
"""
    elif style == "visit_summary":
        base_prompt += """
TASK: Create a concise visit summary from this encounter.
Include: Date/type, Reason, Findings, Decisions, Plan.
Format as brief clinical note (3-5 paragraphs).
"""
    elif style == "problem_list":
        base_prompt += """
TASK: Extract and organize current active medical problems.
Create a numbered problem list with: Name, Severity, Treatment.
Prioritize vascular and cardiovascular problems.
"""
    elif style == "procedure_summary":
        base_prompt += """
TASK: Summarize the vascular procedure and outcomes.
Format as structured procedure report including:
- Indication, Procedure performed, Vessels treated
- Technical success, Complications, Disposition
"""

    return base_prompt


def parse_synopsis_sections(synopsis_text: str) -> Dict[str, str]:
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
        matched = False
        for section_key, section_markers in markers.items():
            if any(marker in line_upper for marker in section_markers):
                # Save previous section
                if current_section and current_content:
                    sections[current_section] = '\n'.join(current_content).strip()

                # Start new section
                current_section = section_key
                current_content = []
                matched = True
                break

        if not matched and current_section and line.strip():
            current_content.append(line.strip())

    # Save last section
    if current_section and current_content:
        sections[current_section] = '\n'.join(current_content).strip()

    return sections


async def generate_synopsis_stateless(
    transcript_text: str,
    patient_context: Optional[Dict] = None,
    style: str = "comprehensive"
) -> Dict:
    """
    Stateless synopsis generation - no database access.

    Args:
        transcript_text: Raw transcript or PlaudAI note
        patient_context: Optional patient demographics from SCC
            {name: str, mrn: str, age: int, dob: str}
        style: "comprehensive" | "visit_summary" | "problem_list" | "procedure_summary"

    Returns:
        {
            "synopsis": str,
            "sections": Dict[str, str],
            "model_used": str,
            "tokens_used": int,
            "processing_time_ms": int
        }
    """
    if not GOOGLE_API_KEY:
        logger.error("GOOGLE_API_KEY not configured")
        raise ValueError("GOOGLE_API_KEY not configured - cannot generate synopsis")

    if not transcript_text or not transcript_text.strip():
        raise ValueError("transcript_text cannot be empty")

    logger.info(f"Generating {style} synopsis ({len(transcript_text)} chars)")
    start_time = time.time()

    # Build prompt
    prompt = build_synopsis_prompt(transcript_text, patient_context, style)

    # Generate with Gemini
    try:
        model = genai.GenerativeModel(GEMINI_MODEL)
        response = model.generate_content(prompt)

        synopsis_text = response.text
        tokens_used = 0
        if hasattr(response, 'usage_metadata') and response.usage_metadata:
            tokens_used = response.usage_metadata.total_token_count

        elapsed_ms = int((time.time() - start_time) * 1000)
        logger.info(f"Synopsis generated in {elapsed_ms}ms, {tokens_used} tokens")

    except Exception as e:
        logger.error(f"Gemini generation failed: {e}", exc_info=True)
        raise

    # Parse sections
    sections = parse_synopsis_sections(synopsis_text)

    return {
        "synopsis": synopsis_text,
        "sections": sections,
        "model_used": GEMINI_MODEL,
        "tokens_used": tokens_used,
        "processing_time_ms": elapsed_ms
    }
