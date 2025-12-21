"""
PlaudAI Uploader - Clinical Query Service
Natural language patient information retrieval with Gemini AI
"""
import re
import logging
from typing import Optional, Dict, List
from sqlalchemy.orm import Session
from sqlalchemy import or_
import google.generativeai as genai

from ..models import Patient, VoiceTranscript, PVIProcedure
from ..config import GOOGLE_API_KEY, GEMINI_MODEL
from .gemini_synopsis import gather_patient_data

logger = logging.getLogger(__name__)

# Configure Gemini
if GOOGLE_API_KEY:
    genai.configure(api_key=GOOGLE_API_KEY)
    logger.info(f"🤖 Clinical Query Service initialized with {GEMINI_MODEL}")
else:
    logger.warning("⚠️ GOOGLE_API_KEY not configured - clinical queries disabled")


def extract_patient_from_query(query: str, db: Session) -> Optional[Patient]:
    """
    Extract patient identifier from natural language query.
    
    Supports:
    - MRN: "MRN123456", "patient MRN: 123456"
    - Names: "Mr. Jones", "patient John Doe", "for Jane Smith"
    
    Returns Patient object or None if not found/ambiguous
    """
    query_lower = query.lower().strip()
    logger.debug(f"🔍 Extracting patient from query: '{query}'")
    
    # Strategy 1: Look for MRN (most reliable)
    patient = extract_by_mrn(query_lower, db)
    if patient:
        logger.info(f"✅ Found patient by MRN: {patient.athena_mrn}")
        return patient
    
    # Strategy 2: Look for full name patterns
    patient = extract_by_full_name(query_lower, db)
    if patient:
        logger.info(f"✅ Found patient by full name: {patient.first_name} {patient.last_name}")
        return patient
    
    # Strategy 3: Look for last name only (less reliable)
    patient = extract_by_last_name(query_lower, db)
    if patient:
        logger.info(f"✅ Found patient by last name: {patient.last_name}")
        return patient
    
    logger.warning(f"❌ Could not identify patient from query: '{query}'")
    return None


def extract_by_mrn(query: str, db: Session) -> Optional[Patient]:
    """
    Extract patient by MRN.
    
    Patterns:
    - "MRN123456"
    - "patient MRN: 123456"
    - "MRN 123456"
    - "for MRN123456"
    """
    # Look for MRN patterns
    mrn_patterns = [
        r'mrn\s*[:\-]?\s*([a-zA-Z0-9]+)',  # MRN: 123456 or MRN-123456
        r'\b([a-zA-Z]*\d{5,})\b',          # Alphanumeric with 5+ digits
    ]
    
    for pattern in mrn_patterns:
        match = re.search(pattern, query)
        if match:
            potential_mrn = match.group(1).upper()
            logger.debug(f"🔎 Trying MRN: {potential_mrn}")
            
            # Try exact match
            patient = db.query(Patient).filter_by(athena_mrn=potential_mrn).first()
            if patient:
                return patient
            
            # Try partial match (MRN might be entered without prefix)
            patient = db.query(Patient).filter(
                Patient.athena_mrn.ilike(f"%{potential_mrn}%")
            ).first()
            if patient:
                return patient
    
    return None


def extract_by_full_name(query: str, db: Session) -> Optional[Patient]:
    """
    Extract patient by full name.
    
    Patterns:
    - "Mr. John Doe"
    - "patient Jane Smith"
    - "for John Doe"
    - "about Sarah Johnson"
    """
    # Remove common prefixes/words
    clean_query = query
    for word in ['mr.', 'mrs.', 'ms.', 'miss', 'dr.', 'patient', 'for', 'about', 'regarding']:
        clean_query = clean_query.replace(word, ' ')
    
    # Look for two consecutive capitalized words (likely a name)
    # Pattern: Find pairs of words that could be names
    name_pattern = r'\b([A-Z][a-z]+)\s+([A-Z][a-z]+)\b'
    
    # First try original query (may have proper capitalization)
    original_query = query.replace('mr.', 'Mr.').replace('mrs.', 'Mrs.').replace('ms.', 'Ms.')
    match = re.search(name_pattern, original_query, re.IGNORECASE)
    
    if not match:
        # Try to find two words that look like names in cleaned query
        words = [w.strip() for w in clean_query.split() if len(w.strip()) > 1]
        if len(words) >= 2:
            # Try consecutive word pairs
            for i in range(len(words) - 1):
                first_name = words[i]
                last_name = words[i + 1]
                
                if len(first_name) > 1 and len(last_name) > 1:
                    patient = search_by_name_pair(first_name, last_name, db)
                    if patient:
                        return patient
        return None
    
    first_name = match.group(1)
    last_name = match.group(2)
    
    return search_by_name_pair(first_name, last_name, db)


def extract_by_last_name(query: str, db: Session) -> Optional[Patient]:
    """
    Extract patient by last name only (use cautiously - may be ambiguous).
    
    Patterns:
    - "Mr. Jones"
    - "patient Smith"
    """
    # Look for title + single name
    title_patterns = [
        r'(?:mr\.?|mrs\.?|ms\.?|miss|dr\.?)\s+([A-Z][a-z]+)',
        r'patient\s+([A-Z][a-z]+)',
    ]
    
    for pattern in title_patterns:
        match = re.search(pattern, query, re.IGNORECASE)
        if match:
            last_name = match.group(1)
            logger.debug(f"🔎 Trying last name: {last_name}")
            
            # Search by last name
            patients = db.query(Patient).filter(
                Patient.last_name.ilike(f"%{last_name}%")
            ).all()
            
            if len(patients) == 1:
                return patients[0]
            elif len(patients) > 1:
                logger.warning(f"⚠️ Ambiguous: {len(patients)} patients match '{last_name}'")
                # Return most recently updated patient
                return sorted(patients, key=lambda p: p.updated_at, reverse=True)[0]
    
    return None


def search_by_name_pair(first_name: str, last_name: str, db: Session) -> Optional[Patient]:
    """
    Search database for patient by first and last name.
    Uses case-insensitive partial matching.
    """
    logger.debug(f"🔎 Searching for: {first_name} {last_name}")
    
    # Try exact match first
    patient = db.query(Patient).filter(
        Patient.first_name.ilike(first_name),
        Patient.last_name.ilike(last_name)
    ).first()
    
    if patient:
        return patient
    
    # Try partial match
    patient = db.query(Patient).filter(
        Patient.first_name.ilike(f"%{first_name}%"),
        Patient.last_name.ilike(f"%{last_name}%")
    ).first()
    
    if patient:
        return patient
    
    # Try last name only as fallback
    patients = db.query(Patient).filter(
        Patient.last_name.ilike(f"%{last_name}%")
    ).all()
    
    if len(patients) == 1:
        return patients[0]
    
    return None


def build_query_prompt(query: str, patient_data: Dict) -> str:
    """
    Build context-aware Gemini prompt for clinical queries.
    
    Includes:
    - Patient demographics
    - Recent transcripts (with both raw and formatted notes)
    - Procedure history
    - Specific question from user
    """
    demographics = patient_data.get('demographics', {})
    transcripts = patient_data.get('transcripts', [])
    procedures = patient_data.get('procedures', [])
    
    prompt = f"""You are a clinical assistant helping review patient medical records.

PATIENT INFORMATION:
Name: {demographics.get('name', 'Unknown')}
MRN: {demographics.get('mrn', 'Unknown')}
Age: {demographics.get('age', 'Unknown')} years old
Date of Birth: {demographics.get('dob', 'Unknown')}
Sex: {demographics.get('birth_sex', 'Not specified')}

USER'S QUESTION:
"{query}"

"""
    
    # Add recent clinical notes
    if transcripts:
        prompt += "\n" + "="*60 + "\n"
        prompt += "RECENT CLINICAL NOTES:\n"
        prompt += "="*60 + "\n\n"
        
        for i, t in enumerate(transcripts[:5], 1):  # Last 5 notes
            visit_date = t.get('date')
            if visit_date:
                date_str = visit_date.strftime('%Y-%m-%d')
            else:
                date_str = "Date unknown"
            
            prompt += f"\n{'─'*60}\n"
            prompt += f"VISIT {i}: {date_str}\n"
            prompt += f"Type: {t.get('visit_type', 'Not specified')}\n"
            prompt += f"Title: {t.get('title', 'Untitled')}\n"
            prompt += f"{'─'*60}\n\n"
            
            # Prioritize formatted note, fall back to raw
            if t.get('plaud_note'):
                prompt += t['plaud_note'] + "\n\n"
            elif t.get('raw_transcript'):
                # Truncate very long transcripts
                raw = t['raw_transcript']
                if len(raw) > 1000:
                    prompt += raw[:1000] + "...\n[transcript truncated]\n\n"
                else:
                    prompt += raw + "\n\n"
            
            # Add extracted tags if available
            if t.get('tags'):
                prompt += f"Tags: {', '.join(t['tags'])}\n\n"
    
    # Add procedure history
    if procedures:
        prompt += "\n" + "="*60 + "\n"
        prompt += "PROCEDURE HISTORY:\n"
        prompt += "="*60 + "\n\n"
        
        for i, p in enumerate(procedures[:5], 1):  # Last 5 procedures
            prompt += f"{i}. Date: {p.get('date', 'Unknown')}\n"
            prompt += f"   Surgeon: {p.get('surgeon', 'Not specified')}\n"
            prompt += f"   Indication: {p.get('indication', 'Not specified')}\n"
            
            if p.get('rutherford'):
                prompt += f"   Rutherford: {p['rutherford']}\n"
            
            if p.get('arteries_treated'):
                arteries = p['arteries_treated']
                if isinstance(arteries, list):
                    prompt += f"   Vessels treated: {', '.join(arteries)}\n"
                else:
                    prompt += f"   Vessels treated: {arteries}\n"
            
            success = p.get('treatment_success')
            if success is not None:
                prompt += f"   Technical success: {'Yes' if success else 'No'}\n"
            
            if p.get('complications'):
                comps = p['complications']
                if isinstance(comps, list) and len(comps) > 0:
                    prompt += f"   Complications: {', '.join(comps)}\n"
                elif comps:
                    prompt += f"   Complications: {comps}\n"
            
            if p.get('disposition'):
                prompt += f"   Disposition: {p['disposition']}\n"
            
            prompt += "\n"
    
    # Add instructions for response format
    prompt += "\n" + "="*60 + "\n"
    prompt += "INSTRUCTIONS:\n"
    prompt += "="*60 + "\n\n"
    prompt += """Please provide a concise, clinically relevant answer to the user's question based on the available data above.

FORMAT YOUR RESPONSE AS:
- Clear, professional medical documentation
- Use clinical terminology appropriately
- Organize information logically (chronological or by problem)
- Highlight important findings, changes, or concerns
- If the question asks for specific data (dates, values, etc.), provide it clearly
- If information is missing, state that explicitly rather than speculating

STYLE:
- Write as you would verbally present to a physician
- Be concise but complete
- Use bullet points for lists when appropriate
- Include relevant dates to provide context
- If discussing multiple visits or procedures, organize chronologically

Begin your response:
"""
    
    return prompt


def process_clinical_query(query: str, db: Session) -> Dict:
    """
    Main entry point for clinical queries.
    
    Args:
        query: Natural language query from user
        db: Database session
        
    Returns:
        Dictionary with status, patient info, response, and metadata
    """
    logger.info(f"🔍 Processing clinical query: '{query}'")
    
    if not GOOGLE_API_KEY:
        logger.error("❌ Gemini API key not configured")
        return {
            "status": "error",
            "message": "AI service not configured. Please set GOOGLE_API_KEY."
        }
    
    try:
        # Step 1: Extract patient
        patient = extract_patient_from_query(query, db)
        
        if not patient:
            logger.warning("❌ Patient not found")
            return {
                "status": "error",
                "message": "Could not identify patient from your query. Please provide a name or MRN."
            }
        
        # Step 2: Gather patient data
        logger.info(f"📊 Gathering data for patient ID: {patient.id}")
        patient_data = gather_patient_data(db, patient.id, days_back=365)
        
        # Check if we have any data
        transcript_count = len(patient_data.get('transcripts', []))
        procedure_count = len(patient_data.get('procedures', []))
        
        if transcript_count == 0 and procedure_count == 0:
            logger.warning(f"⚠️ No clinical data found for patient {patient.id}")
            return {
                "status": "success",
                "patient": {
                    "name": f"{patient.first_name} {patient.last_name}",
                    "mrn": patient.athena_mrn
                },
                "response": f"Patient {patient.first_name} {patient.last_name} is in the system, but no clinical notes or procedures have been recorded yet.",
                "data_sources": {
                    "transcripts": 0,
                    "procedures": 0
                }
            }
        
        # Step 3: Build prompt
        logger.info("🏗️ Building Gemini prompt")
        prompt = build_query_prompt(query, patient_data)
        
        # Step 4: Call Gemini
        logger.info(f"🤖 Sending to Gemini ({len(prompt)} characters)")
        model = genai.GenerativeModel(GEMINI_MODEL)
        response = model.generate_content(prompt)
        
        logger.info("✅ Query processed successfully")
        
        return {
            "status": "success",
            "patient": {
                "name": f"{patient.first_name} {patient.last_name}",
                "mrn": patient.athena_mrn
            },
            "response": response.text,
            "data_sources": {
                "transcripts": transcript_count,
                "procedures": procedure_count
            }
        }
        
    except Exception as e:
        logger.error(f"❌ Clinical query failed: {e}", exc_info=True)
        return {
            "status": "error",
            "message": f"Query processing failed: {str(e)}"
        }