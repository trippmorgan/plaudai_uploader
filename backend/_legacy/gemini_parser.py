"""
Gemini AI Parser for Medical Records
Extracts structured data from PlaudAI transcripts based on record type
"""
import google.generativeai as genai
import json
import logging
from typing import Dict, Optional
from ..config import GOOGLE_API_KEY, GEMINI_MODEL

logger = logging.getLogger(__name__)

if GOOGLE_API_KEY:
    genai.configure(api_key=GOOGLE_API_KEY)
    logger.info(f"🤖 Gemini Parser configured")

# ==================== Prompts by Record Type ====================

OPERATIVE_NOTE_PROMPT = """
You are a vascular surgeon's AI scribe. Extract structured data from this operative note.

Return ONLY valid JSON with these fields:
{
  "procedure_name": "Primary procedure performed",
  "procedure_date": "YYYY-MM-DD",
  "surgeon": "Surgeon name",
  "assistant": "Assistant name(s)",
  "anesthesia_type": "General/Local/MAC",
  "indication": "Clinical indication",
  "preop_diagnosis": "Diagnosis before surgery",
  "postop_diagnosis": "Diagnosis after surgery",
  "findings": ["Key intraoperative findings"],
  "procedure_details": "Step-by-step procedure description",
  "devices_used": ["List of devices/implants"],
  "complications": ["Any complications, empty if none"],
  "estimated_blood_loss": "Amount in mL",
  "specimens": ["Specimens sent to pathology"],
  "closure": "How wounds were closed",
  "drains": "Drains placed",
  "disposition": "Where patient went after surgery"
}

TRANSCRIPT:
"""

IMAGING_PROMPT = """
You are a radiologist's AI assistant. Extract structured data from this imaging report.

Return ONLY valid JSON:
{
  "study_type": "Ultrasound/CT/MRI/X-Ray",
  "study_subtype": "Specific study (e.g., Carotid Doppler, Chest CT)",
  "study_date": "YYYY-MM-DD",
  "indication": "Reason for study",
  "technique": "Imaging technique/protocol",
  "comparison": "Prior studies compared",
  "findings": {
    "key_findings": ["Most important findings"],
    "detailed_findings": "Full description of findings"
  },
  "measurements": [
    {"structure": "What was measured", "value": "Measurement with units"}
  ],
  "impression": "Radiologist's interpretation/conclusion",
  "recommendations": ["Recommended follow-up"]
}

REPORT:
"""

LAB_RESULT_PROMPT = """
You are a clinical pathologist's AI assistant. Extract lab data.

Return ONLY valid JSON:
{
  "test_date": "YYYY-MM-DD",
  "lab_panel": "Name of lab panel/test",
  "results": [
    {
      "test_name": "Test name",
      "value": "Result value",
      "unit": "Unit of measurement",
      "reference_range": "Normal range",
      "flag": "High/Low/Normal"
    }
  ],
  "interpretation": "Clinical interpretation",
  "critical_values": ["Any critical results"]
}

LAB REPORT:
"""

OFFICE_VISIT_PROMPT = """
You are a physician's AI scribe for an office visit note.

Return ONLY valid JSON:
{
  "visit_date": "YYYY-MM-DD",
  "visit_type": "New patient/Follow-up/Consultation",
  "chief_complaint": "Patient's main concern",
  "hpi": "History of present illness",
  "medications": ["Current medications"],
  "allergies": ["Known allergies"],
  "vitals": {
    "bp": "Blood pressure",
    "hr": "Heart rate",
    "temp": "Temperature",
    "weight": "Weight"
  },
  "physical_exam": "Physical examination findings",
  "assessment": "Clinical assessment",
  "plan": "Treatment plan and follow-up"
}

VISIT NOTE:
"""

# ==================== Parser Functions ====================

def parse_with_gemini(
    text: str,
    record_type: str,
    patient_context: Optional[Dict] = None
) -> Dict:
    """
    Parse medical text with Gemini AI based on record type
    """
    if not GOOGLE_API_KEY:
        logger.warning("⚠️ Gemini API key not configured")
        return {"error": "Gemini API not configured"}
    
    # Select appropriate prompt
    prompts = {
        "operative_note": OPERATIVE_NOTE_PROMPT,
        "ultrasound": IMAGING_PROMPT,
        "ct_scan": IMAGING_PROMPT,
        "mri": IMAGING_PROMPT,
        "xray": IMAGING_PROMPT,
        "lab_result": LAB_RESULT_PROMPT,
        "office_visit": OFFICE_VISIT_PROMPT
    }
    
    prompt_template = prompts.get(record_type, OFFICE_VISIT_PROMPT)
    
    # Add patient context if available
    if patient_context:
        context = f"\nPATIENT CONTEXT:\n"
        context += f"Name: {patient_context.get('name')}\n"
        context += f"MRN: {patient_context.get('mrn')}\n"
        context += f"Age: {patient_context.get('age')}\n\n"
        prompt = context + prompt_template + text
    else:
        prompt = prompt_template + text
    
    try:
        logger.info(f"🚀 Sending {record_type} to Gemini...")
        model = genai.GenerativeModel(GEMINI_MODEL)
        response = model.generate_content(prompt)
        
        # Clean response
        clean_text = response.text.replace("```json", "").replace("```", "").strip()
        parsed_data = json.loads(clean_text)
        
        logger.info(f"✅ Gemini parsing complete for {record_type}")
        return parsed_data
        
    except json.JSONDecodeError as e:
        logger.error(f"❌ Gemini returned invalid JSON: {e}")
        return {
            "error": "Failed to parse JSON",
            "raw_response": response.text if 'response' in locals() else "No response"
        }
    except Exception as e:
        logger.error(f"❌ Gemini parsing failed: {e}", exc_info=True)
        return {"error": str(e)}

def generate_record_summary(parsed_data: Dict, record_type: str) -> str:
    """
    Generate a human-readable summary from parsed data
    """
    if record_type == "operative_note":
        return f"""
Procedure: {parsed_data.get('procedure_name', 'N/A')}
Surgeon: {parsed_data.get('surgeon', 'N/A')}
Date: {parsed_data.get('procedure_date', 'N/A')}

Indication: {parsed_data.get('indication', 'N/A')}

Key Findings: {', '.join(parsed_data.get('findings', ['None documented']))}

Complications: {', '.join(parsed_data.get('complications', ['None']))}
        """.strip()
    
    elif record_type in ["ultrasound", "ct_scan", "mri", "xray"]:
        findings = parsed_data.get('findings', {})
        return f"""
Study: {parsed_data.get('study_subtype', 'N/A')}
Date: {parsed_data.get('study_date', 'N/A')}

Key Findings: {', '.join(findings.get('key_findings', ['None documented']))}

Impression: {parsed_data.get('impression', 'N/A')}
        """.strip()
    
    elif record_type == "lab_result":
        critical = parsed_data.get('critical_values', [])
        critical_str = f"\nCRITICAL VALUES: {', '.join(critical)}" if critical else ""
        return f"""
Lab Panel: {parsed_data.get('lab_panel', 'N/A')}
Date: {parsed_data.get('test_date', 'N/A')}
{critical_str}

Interpretation: {parsed_data.get('interpretation', 'N/A')}
        """.strip()
    
    else:  # office_visit
        return f"""
Visit Type: {parsed_data.get('visit_type', 'N/A')}
Chief Complaint: {parsed_data.get('chief_complaint', 'N/A')}

Assessment: {parsed_data.get('assessment', 'N/A')}

Plan: {parsed_data.get('plan', 'N/A')}
        """.strip()