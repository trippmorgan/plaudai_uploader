"""
PlaudAI Uploader - Text Parsing & Segmentation Service
Enhanced with PVI Registry field extraction
"""
import re
from typing import Dict, List, Tuple
import logging

logger = logging.getLogger(__name__)

# ==================== Markdown Section Parser ====================

def segment_summary(summary: str) -> Dict[str, str]:
    """
    Parse markdown-style sections from PlaudAI transcript
    
    Example input:
    ## Chief Complaint
    Patient presents with...
    
    ## Assessment
    Peripheral arterial disease...
    
    Returns: {'Chief Complaint': 'Patient presents...', 'Assessment': '...'}
    """
    sections = {}
    current_header = None
    current_content = []
    
    for line in summary.splitlines():
        # Check for markdown header (## Header)
        header_match = re.match(r"##\s*(.*)", line.strip())
        
        if header_match:
            # Save previous section
            if current_header and current_content:
                sections[current_header] = "\n".join(current_content).strip()
            
            # Start new section
            current_header = header_match.group(1).strip()
            current_content = []
        elif current_header:
            # Add content to current section
            if line.strip():
                current_content.append(line.strip())
    
    # Save last section
    if current_header and current_content:
        sections[current_header] = "\n".join(current_content).strip()
    
    return sections

# ==================== Medical Tag Generation ====================

def generate_tags(text: str) -> List[str]:
    """
    Generate medical tags based on keyword matching
    Enhanced for vascular/peripheral procedures
    """
    text_lower = text.lower()
    tags = []
    
    # Define keyword mappings
    tag_keywords = {
        # Vascular conditions
        "pad": ["pad", "peripheral arterial disease", "peripheral artery disease"],
        "cli": ["critical limb ischemia", "cli", "limb-threatening"],
        "claudication": ["claudication", "intermittent claudication"],
        "aneurysm": ["aneurysm", "aneurysmal"],
        
        # Anatomical locations
        "infrarenal": ["infrarenal", "infra-renal"],
        "femoral": ["femoral", "sfa", "superficial femoral", "common femoral", "cfa"],
        "popliteal": ["popliteal", "pop"],
        "tibial": ["tibial", "anterior tibial", "posterior tibial", "at", "pt"],
        "profunda": ["profunda", "deep femoral"],
        
        # Procedures
        "angioplasty": ["angioplasty", "pta", "balloon"],
        "stent": ["stent", "stenting", "stented"],
        "atherectomy": ["atherectomy", "debulking"],
        "thrombectomy": ["thrombectomy", "thrombus removal"],
        "bypass": ["bypass", "graft"],
        
        # Findings
        "occlusion": ["occlusion", "occluded", "100%", "cto"],
        "stenosis": ["stenosis", "stenotic", "narrowing"],
        "dissection": ["dissection", "dissected"],
        "thrombus": ["thrombus", "clot", "thrombosis"],
        "calcification": ["calcification", "calcified", "calcium"],
        
        # Complications
        "perforation": ["perforation", "perforated"],
        "hemorrhage": ["hemorrhage", "bleeding", "hematoma"],
        "ischemia": ["ischemia", "ischemic"],
        
        # Access
        "femoral_access": ["femoral access", "cfa access", "groin puncture"],
        "radial_access": ["radial access", "wrist access"],
        "closure_device": ["closure device", "angio-seal", "perclose", "mynx"],
        
        # Rutherford classification
        "rutherford": ["rutherford"],
        
        # General medical
        "diabetes": ["diabetes", "diabetic", "dm"],
        "hypertension": ["hypertension", "htn", "high blood pressure"],
        "smoking": ["smoking", "smoker", "tobacco"],
        "dialysis": ["dialysis", "hemodialysis", "esrd"],
        "anticoagulation": ["anticoagulation", "coumadin", "warfarin", "eliquis", "xarelto"],
    }
    
    # Check for each tag
    for tag, keywords in tag_keywords.items():
        if any(keyword in text_lower for keyword in keywords):
            tags.append(tag)
    
    return sorted(list(set(tags)))  # Remove duplicates and sort

# ==================== PVI Field Extraction ====================

def extract_pvi_fields(text: str) -> Dict[str, any]:
    """
    Extract structured PVI registry fields from free text
    Returns dictionary of fields that can be mapped to PVIProcedure model
    """
    text_lower = text.lower()
    extracted = {}
    
    # Smoking status
    if "never smoked" in text_lower or "non-smoker" in text_lower:
        extracted["smoking_history"] = "Never"
    elif "former smoker" in text_lower or "quit smoking" in text_lower:
        extracted["smoking_history"] = "Former"
    elif "current smoker" in text_lower or "active smoker" in text_lower:
        extracted["smoking_history"] = "Current"
    
    # Rutherford classification
    rutherford_match = re.search(r"rutherford\s+(?:class|category|stage)?\s*(\d+)", text_lower)
    if rutherford_match:
        extracted["rutherford_status"] = f"Rutherford {rutherford_match.group(1)}"
    
    # Extract numeric values
    abi_match = re.search(r"abi\s*[:=]?\s*(\d+\.?\d*)", text_lower)
    if abi_match:
        extracted["preop_abi"] = float(abi_match.group(1))
    
    tbi_match = re.search(r"tbi\s*[:=]?\s*(\d+\.?\d*)", text_lower)
    if tbi_match:
        extracted["preop_tbi"] = float(tbi_match.group(1))
    
    creatinine_match = re.search(r"creatinine\s*[:=]?\s*(\d+\.?\d*)", text_lower)
    if creatinine_match:
        extracted["creatinine"] = float(creatinine_match.group(1))
    
    contrast_match = re.search(r"contrast\s+(?:volume\s+)?(\d+)\s*(?:ml|cc)", text_lower)
    if contrast_match:
        extracted["contrast_volume"] = float(contrast_match.group(1))
    
    # Extract arteries treated
    arteries = []
    artery_patterns = [
        r"(?:right|left|bilateral)?\s*(?:common\s+)?femoral",
        r"(?:right|left|bilateral)?\s*sfa",
        r"(?:right|left|bilateral)?\s*popliteal",
        r"(?:right|left|bilateral)?\s*(?:anterior|posterior)\s+tibial",
        r"(?:right|left|bilateral)?\s*peroneal",
    ]
    for pattern in artery_patterns:
        matches = re.finditer(pattern, text_lower)
        for match in matches:
            arteries.append(match.group(0).strip())
    if arteries:
        extracted["arteries_treated"] = list(set(arteries))
    
    # Access site
    if "femoral access" in text_lower or "cfa access" in text_lower:
        extracted["access_site"] = "Common Femoral Artery"
    elif "radial access" in text_lower:
        extracted["access_site"] = "Radial Artery"
    elif "brachial access" in text_lower:
        extracted["access_site"] = "Brachial Artery"
    
    # TASC classification
    tasc_match = re.search(r"tasc\s+([a-d])", text_lower)
    if tasc_match:
        extracted["tasc_grade"] = f"TASC {tasc_match.group(1).upper()}"
    
    # Complications
    complications = []
    complication_keywords = {
        "dissection": ["dissection"],
        "perforation": ["perforation"],
        "thrombosis": ["thrombosis", "acute thrombus"],
        "hemorrhage": ["bleeding", "hemorrhage", "hematoma"],
        "pseudoaneurysm": ["pseudoaneurysm"],
    }
    for comp, keywords in complication_keywords.items():
        if any(kw in text_lower for kw in keywords):
            complications.append(comp)
    if complications:
        extracted["complications"] = complications
    
    return extracted

# ==================== Confidence Scoring ====================

def calculate_confidence_score(text: str, extracted_fields: Dict) -> float:
    """
    Calculate confidence score based on:
    - Text length
    - Number of extracted fields
    - Presence of key structured data
    """
    score = 0.0
    
    # Base score from text length (longer = more detailed)
    word_count = len(text.split())
    if word_count > 500:
        score += 0.3
    elif word_count > 200:
        score += 0.2
    elif word_count > 100:
        score += 0.1
    
    # Score from number of extracted fields
    field_count = len(extracted_fields)
    if field_count > 10:
        score += 0.4
    elif field_count > 5:
        score += 0.3
    elif field_count > 2:
        score += 0.2
    
    # Bonus for critical fields
    critical_fields = ["rutherford_status", "preop_abi", "arteries_treated", "access_site"]
    critical_present = sum(1 for field in critical_fields if field in extracted_fields)
    score += (critical_present / len(critical_fields)) * 0.3
    
    return min(score, 1.0)  # Cap at 1.0

# ==================== Main Processing Function ====================

def process_transcript(transcript_text: str) -> Tuple[Dict[str, str], List[str], Dict[str, any], float]:
    """
    Main processing pipeline for PlaudAI transcript
    
    Returns:
        - sections: Parsed markdown sections
        - tags: Generated medical tags
        - pvi_fields: Extracted PVI registry fields
        - confidence: Confidence score
    """
    sections = segment_summary(transcript_text)
    tags = generate_tags(transcript_text)
    pvi_fields = extract_pvi_fields(transcript_text)
    confidence = calculate_confidence_score(transcript_text, pvi_fields)
    
    logger.info(f"Processed transcript: {len(sections)} sections, {len(tags)} tags, "
                f"{len(pvi_fields)} PVI fields, confidence={confidence:.2f}")
    
    return sections, tags, pvi_fields, confidence