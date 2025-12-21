
#python"""
#Category-Specific Gemini Parser
#Uses different prompts based on medical record type

import google.generativeai as genai
import json
import logging
from typing import Dict
from ..config import GOOGLE_API_KEY, GEMINI_MODEL

logger = logging.getLogger(__name__)

if GOOGLE_API_KEY:
    genai.configure(api_key=GOOGLE_API_KEY)
    logger.info("🤖 Category Parser configured")

# ==================== Category-Specific Prompts ====================

PROMPTS = {
    "operative_note": """
You are a vascular surgery AI scribe. Extract structured data from this operative note.

Return ONLY valid JSON:
{
  "procedure_name": "Primary procedure performed",
  "surgeon": "Surgeon name",
  "date": "YYYY-MM-DD",
  "preop_diagnosis": "Diagnosis before surgery",
  "postop_diagnosis": "Diagnosis after surgery",
  "procedure_details": "Step-by-step description",
  "findings": ["Key intraoperative findings"],
  "devices_used": ["Devices/implants used"],
  "estimated_blood_loss": "Amount in mL",
  "complications": ["Complications or 'None'"],
  "specimens": ["Specimens sent to pathology"],
  "closure": "How wounds were closed",
  "disposition": "Post-op destination"
}

OPERATIVE NOTE:
""",

    "imaging": """
You are a radiologist's AI assistant. Extract structured data from this imaging report.

Return ONLY valid JSON:
{
  "study_type": "CT/Ultrasound/MRI/X-Ray",
  "study_name": "Specific study (e.g., CT Angiogram, Carotid Duplex)",
  "study_date": "YYYY-MM-DD",
  "indication": "Reason for study",
  "technique": "Imaging protocol used",
  "findings": {
    "key_findings": ["Most important findings"],
    "aneurysm_size": "Size if aneurysm present",
    "stenosis_percent": "Stenosis percentage if present",
    "detailed_findings": "Full description"
  },
  "measurements": [
    {"structure": "What was measured", "value": "Measurement with units"}
  ],
  "impression": "Radiologist's conclusion",
  "recommendations": ["Follow-up recommendations"]
}

IMAGING REPORT:
""",

    "lab_result": """
You are a clinical pathologist's AI assistant. Extract lab data.

Return ONLY valid JSON:
{
  "collection_date": "YYYY-MM-DD",
  "lab_panel": "Panel name (e.g., Basic Metabolic Panel, CBC)",
  "results": [
    {
      "test_name": "Test name",
      "value": "Result value",
      "unit": "Unit of measurement",
      "reference_range": "Normal range",
      "flag": "High/Low/Normal"
    }
  ],
  "abnormal_values": [
    {"test": "Test name", "value": "Result", "flag": "High/Low"}
  ],
  "critical_values": ["Any critical results"],
  "creatinine": "Value if present",
  "gfr": "Value if present",
  "inr": "Value if present",
  "hemoglobin": "Value if present",
  "wbc": "Value if present",
  "interpretation": "Clinical significance of results"
}

LAB RESULTS:
""",

    "office_visit": """
You are a physician's AI scribe for office visits.

Return ONLY valid JSON:
{
  "visit_date": "YYYY-MM-DD",
  "visit_type": "New patient/Follow-up/Consultation",
  "chief_complaint": "Patient's main concern",
  "hpi": "History of present illness",
  "medications": ["Current medications with dosages"],
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

OFFICE VISIT NOTE:
"""
}

# ==================== Parser Functions ====================

def parse_by_category(text: str, category: str) -> Dict:
    """
    Parse medical text with category-specific Gemini prompts
    
    Args:
        text: The medical text to parse
        category: operative_note, imaging, lab_result, or office_visit
    
    Returns:
        Dictionary with parsed structured data
    """
    if not GOOGLE_API_KEY:
        logger.warning("⚠️ Gemini API key not configured")
        return {"error": "Gemini API not configured"}
    
    # Get appropriate prompt
    prompt_template = PROMPTS.get(category, PROMPTS["office_visit"])
    prompt = prompt_template + text
    
    try:
        logger.info(f"🚀 Parsing {category} with Gemini...")
        model = genai.GenerativeModel(GEMINI_MODEL)
        response = model.generate_content(prompt)
        
        # Clean and parse JSON
        clean_text = response.text.replace("```json", "").replace("```", "").strip()
        parsed_data = json.loads(clean_text)
        
        logger.info(f"✅ Category parsing complete for {category}")
        return parsed_data
        
    except json.JSONDecodeError as e:
        logger.error(f"❌ Invalid JSON from Gemini: {e}")
        return {
            "error": "Failed to parse JSON",
            "raw_response": response.text if 'response' in locals() else ""
        }
    except Exception as e:
        logger.error(f"❌ Category parsing failed: {e}", exc_info=True)
        return {"error": str(e)}


def generate_category_summary(parsed_data: Dict, category: str) -> str:
    """
    Generate human-readable summary from parsed data
    
    Args:
        parsed_data: The structured data from Gemini
        category: The record category
    
    Returns:
        String with formatted summary
    """
    if not parsed_data or 'error' in parsed_data:
        return "⚠️ Parsing failed - see structured data for details"
    
    if category == "operative_note":
        complications = parsed_data.get('complications', [])
        comp_str = ', '.join(complications) if complications and complications != ['None'] else 'None'
        
        return f"""
Procedure: {parsed_data.get('procedure_name', 'N/A')}
Surgeon: {parsed_data.get('surgeon', 'N/A')}
Date: {parsed_data.get('date', 'N/A')}

Pre-op Diagnosis: {parsed_data.get('preop_diagnosis', 'N/A')}
Post-op Diagnosis: {parsed_data.get('postop_diagnosis', 'N/A')}

Key Findings: {', '.join(parsed_data.get('findings', ['None documented']))}
EBL: {parsed_data.get('estimated_blood_loss', 'N/A')}
Complications: {comp_str}

Disposition: {parsed_data.get('disposition', 'N/A')}
        """.strip()
    
    elif category == "imaging":
        findings = parsed_data.get('findings', {})
        key_findings = findings.get('key_findings', ['None documented'])
        
        return f"""
Study: {parsed_data.get('study_name', 'N/A')}
Type: {parsed_data.get('study_type', 'N/A')}
Date: {parsed_data.get('study_date', 'N/A')}

Indication: {parsed_data.get('indication', 'N/A')}

Key Findings:
{chr(10).join('  • ' + finding for finding in key_findings)}

Impression: {parsed_data.get('impression', 'N/A')}

Recommendations: {', '.join(parsed_data.get('recommendations', ['None']))}
        """.strip()
    
    elif category == "lab_result":
        abnormal = parsed_data.get('abnormal_values', [])
        critical = parsed_data.get('critical_values', [])
        
        critical_str = ""
        if critical:
            critical_str = f"\n\n⚠️ CRITICAL VALUES: {', '.join(critical)}"
        
        abnormal_str = ""
        if abnormal:
            abnormal_str = "\n\nAbnormal Results:\n"
            for item in abnormal[:5]:  # Show first 5
                abnormal_str += f"  • {item.get('test', 'Unknown')}: {item.get('value', 'N/A')} ({item.get('flag', 'N/A')})\n"
        
        return f"""
Panel: {parsed_data.get('lab_panel', 'N/A')}
Collection Date: {parsed_data.get('collection_date', 'N/A')}
{critical_str}
{abnormal_str}
Key Labs:
  • Creatinine: {parsed_data.get('creatinine', 'N/A')}
  • GFR: {parsed_data.get('gfr', 'N/A')}
  • INR: {parsed_data.get('inr', 'N/A')}
  • Hemoglobin: {parsed_data.get('hemoglobin', 'N/A')}
  • WBC: {parsed_data.get('wbc', 'N/A')}

Interpretation: {parsed_data.get('interpretation', 'N/A')}
        """.strip()
    
    else:  # office_visit
        medications = parsed_data.get('medications', [])
        med_str = '\n'.join(f"  • {med}" for med in medications[:5]) if medications else "  None documented"
        
        return f"""
Visit Type: {parsed_data.get('visit_type', 'N/A')}
Date: {parsed_data.get('visit_date', 'N/A')}

Chief Complaint: {parsed_data.get('chief_complaint', 'N/A')}

HPI: {parsed_data.get('hpi', 'N/A')[:200]}{'...' if len(parsed_data.get('hpi', '')) > 200 else ''}

Current Medications:
{med_str}

Assessment: {parsed_data.get('assessment', 'N/A')}

Plan: {parsed_data.get('plan', 'N/A')}
        """.strip()
