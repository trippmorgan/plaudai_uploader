"""
PlaudAI Uploader - PDF Generator for Medical Records
Generates professional PDFs from clinical synopses and categorized records
"""
from fpdf import FPDF
from datetime import datetime
from typing import Dict, Optional
import os
import logging

logger = logging.getLogger(__name__)


def sanitize_text(text: str) -> str:
    """
    Replace Unicode characters with ASCII equivalents for PDF compatibility.
    Fixes the 'Character outside the range' error with smart quotes etc.
    """
    if text is None:
        return ""
    
    if not isinstance(text, str):
        text = str(text)
    
    # Common Unicode replacements
    replacements = {
        '\u2019': "'",   # Right single quote → apostrophe
        '\u2018': "'",   # Left single quote → apostrophe
        '\u201c': '"',   # Left double quote → straight quote
        '\u201d': '"',   # Right double quote → straight quote
        '\u2013': '-',   # En dash → hyphen
        '\u2014': '--',  # Em dash → double hyphen
        '\u2026': '...', # Ellipsis → three dots
        '\u00a0': ' ',   # Non-breaking space → space
        '\u00b0': ' degrees',  # Degree symbol
        '\u00b1': '+/-', # Plus-minus
        '\u00d7': 'x',   # Multiplication sign
        '\u2022': '*',   # Bullet point
        '\u2192': '->',  # Right arrow
        '\u2190': '<-',  # Left arrow
        '\u2032': "'",   # Prime → apostrophe
        '\u2033': '"',   # Double prime → quote
        '\u00ae': '(R)', # Registered trademark
        '\u2122': '(TM)', # Trademark
        '\u00a9': '(C)', # Copyright
        '\u00bd': '1/2', # One half
        '\u00bc': '1/4', # One quarter
        '\u00be': '3/4', # Three quarters
        '\u2020': '+',   # Dagger
        '\u2021': '++',  # Double dagger
        '\u00b7': '*',   # Middle dot
        '\u2010': '-',   # Hyphen
        '\u2011': '-',   # Non-breaking hyphen
        '\u2012': '-',   # Figure dash
        '\u00ad': '-',   # Soft hyphen
        '\ufeff': '',    # Zero-width no-break space (BOM)
        '\u200b': '',    # Zero-width space
        '\u200c': '',    # Zero-width non-joiner
        '\u200d': '',    # Zero-width joiner
    }
    
    for unicode_char, ascii_char in replacements.items():
        text = text.replace(unicode_char, ascii_char)
    
    # Remove any remaining non-latin1 characters
    text = text.encode('latin-1', errors='replace').decode('latin-1')
    
    return text


class MedicalRecordPDF(FPDF):
    """Custom PDF class with Albany Vascular Specialist Center letterhead"""

    def __init__(self, record_type="Medical Record"):
        super().__init__()
        self.record_type = record_type

    def header(self):
        """PDF Header with Albany Vascular Letterhead"""
        # Albany Vascular Specialist Center Header
        self.set_font('Arial', 'B', 18)
        self.set_text_color(107, 93, 79)  # Primary brown #6B5D4F
        self.cell(0, 10, sanitize_text('ALBANY VASCULAR SPECIALIST CENTER'), 0, 1, 'C')

        # Record Type
        self.set_font('Arial', 'B', 14)
        self.set_text_color(200, 168, 130)  # Gold/tan #C8A882
        self.cell(0, 8, sanitize_text(self.record_type), 0, 1, 'C')

        # Generation timestamp
        self.set_font('Arial', 'I', 9)
        self.set_text_color(100, 100, 100)
        self.cell(0, 5, f'Generated: {datetime.now().strftime("%B %d, %Y at %I:%M %p")}', 0, 1, 'C')

        # Separator line
        self.set_draw_color(200, 168, 130)  # Gold line
        self.set_line_width(0.5)
        self.line(10, self.get_y() + 2, 200, self.get_y() + 2)
        self.ln(5)

        # Reset text color
        self.set_text_color(0, 0, 0)

    def footer(self):
        """PDF Footer with Albany Vascular contact information"""
        self.set_y(-20)

        # Separator line
        self.set_draw_color(200, 168, 130)
        self.set_line_width(0.5)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(2)

        # Contact information
        self.set_font('Arial', '', 8)
        self.set_text_color(107, 93, 79)
        footer_text = '2300 DAWSON ROAD, SUITE 101 | ALBANY, GA 31707 | OFFICE (229) 436-8535 | FAX (229) 432-1904'
        self.cell(0, 5, sanitize_text(footer_text), 0, 1, 'C')

        # Page number
        self.set_font('Arial', 'I', 8)
        self.set_text_color(100, 100, 100)
        self.cell(0, 5, f'Page {self.page_no()}/{{nb}}', 0, 0, 'C')

        # Reset text color
        self.set_text_color(0, 0, 0)
        
    def chapter_title(self, title: str):
        """Add a section title with Albany Vascular styling"""
        self.set_font('Arial', 'B', 14)
        self.set_text_color(107, 93, 79)  # Primary brown
        self.set_fill_color(245, 241, 232)  # Cream background
        self.cell(0, 10, sanitize_text(title), 0, 1, 'L', True)
        self.set_text_color(0, 0, 0)  # Reset to black
        self.ln(2)
        
    def chapter_body(self, body: str):
        """Add section body text"""
        self.set_font('Arial', '', 11)
        self.multi_cell(0, 6, sanitize_text(body))
        self.ln(3)
    
    def add_field(self, label, value):
        """
        Adds a labeled field (e.g., "DOB: 01/01/1980") with proper spacing checks.
        """
        self.set_font("Arial", 'B', 10)
        
        # Sanitize label
        label = sanitize_text(label)
        
        # Calculate width of the label
        label_width = self.get_string_width(f"{label}: ")
        
        # Check if we are too close to the right margin
        if self.get_x() + label_width > self.w - self.r_margin:
            self.ln(6)
            
        self.cell(label_width, 6, f"{label}: ", ln=0)
        
        self.set_font("Arial", '', 10)
        
        # Sanitize value
        val_str = sanitize_text(str(value)) if value is not None else ""
        
        effective_width = (self.w - self.r_margin) - self.get_x()
        
        if effective_width < 5:
            self.ln(6)
            effective_width = 0
            
        self.multi_cell(effective_width, 6, val_str)


# ==================== Category-Specific PDF Generators ====================

def generate_operative_note_pdf(
    patient_data: Dict,
    category_data: Dict,
    raw_transcript: str,
    output_folder: str = "clinical_pdfs"
) -> str:
    """
    Generate PDF for Operative Note
    """
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)
    
    pdf = MedicalRecordPDF("Operative Note")
    pdf.alias_nb_pages()
    pdf.add_page()
    
    # Patient Header
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 8, sanitize_text(f"Patient: {patient_data['name']}"), 0, 1)
    pdf.add_field("MRN", patient_data['mrn'])
    pdf.add_field("DOB", patient_data.get('dob', 'N/A'))
    pdf.add_field("Age", f"{patient_data.get('age', 'N/A')} years")
    pdf.ln(5)
    
    # Structured Data
    if 'error' not in category_data:
        pdf.chapter_title("Procedure Information")
        pdf.add_field("Procedure", category_data.get('procedure_name', 'N/A'))
        pdf.add_field("Surgeon", category_data.get('surgeon', 'N/A'))
        pdf.add_field("Date", category_data.get('date', 'N/A'))
        pdf.ln(3)
        
        pdf.chapter_title("Diagnosis")
        pdf.add_field("Pre-operative", category_data.get('preop_diagnosis', 'N/A'))
        pdf.add_field("Post-operative", category_data.get('postop_diagnosis', 'N/A'))
        pdf.ln(3)
        
        pdf.chapter_title("Procedure Details")
        pdf.chapter_body(category_data.get('procedure_details', 'Not documented'))
        
        findings = category_data.get('findings', [])
        if findings:
            pdf.chapter_title("Findings")
            for i, finding in enumerate(findings, 1):
                pdf.chapter_body(f"{i}. {finding}")
        
        devices = category_data.get('devices_used', [])
        if devices:
            pdf.chapter_title("Devices Used")
            for device in devices:
                pdf.chapter_body(f"* {device}")
        
        pdf.chapter_title("Blood Loss & Complications")
        pdf.add_field("Estimated Blood Loss", category_data.get('estimated_blood_loss', 'N/A'))
        complications = category_data.get('complications', [])
        comp_text = ', '.join(complications) if complications else 'None'
        pdf.add_field("Complications", comp_text)
        pdf.ln(3)
        
        pdf.chapter_title("Disposition")
        pdf.chapter_body(category_data.get('disposition', 'Not documented'))
    
    # Verbatim Transcript
    pdf.add_page()
    pdf.chapter_title("Verbatim Operative Note")
    pdf.set_font('Courier', '', 9)
    pdf.multi_cell(0, 5, sanitize_text(raw_transcript))
    
    # Save
    filename = f"OpNote_{patient_data['mrn']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    filepath = os.path.join(output_folder, filename)
    pdf.output(filepath)
    
    logger.info(f"PDF generated: {filepath}")
    return filepath


def generate_imaging_pdf(
    patient_data: Dict,
    category_data: Dict,
    raw_transcript: str,
    output_folder: str = "clinical_pdfs"
) -> str:
    """
    Generate PDF for Imaging Report
    """
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)
    
    pdf = MedicalRecordPDF("Imaging Report")
    pdf.alias_nb_pages()
    pdf.add_page()
    
    # Patient Header
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 8, sanitize_text(f"Patient: {patient_data['name']}"), 0, 1)
    pdf.add_field("MRN", patient_data['mrn'])
    pdf.add_field("DOB", patient_data.get('dob', 'N/A'))
    pdf.ln(5)
    
    # Structured Data
    if 'error' not in category_data:
        pdf.chapter_title("Study Information")
        pdf.add_field("Study Type", category_data.get('study_type', 'N/A'))
        pdf.add_field("Study Name", category_data.get('study_name', 'N/A'))
        pdf.add_field("Study Date", category_data.get('study_date', 'N/A'))
        pdf.add_field("Indication", category_data.get('indication', 'N/A'))
        pdf.ln(3)
        
        pdf.chapter_title("Technique")
        pdf.chapter_body(category_data.get('technique', 'Not documented'))
        
        findings = category_data.get('findings', {})
        if findings and 'key_findings' in findings:
            pdf.chapter_title("Key Findings")
            for i, finding in enumerate(findings['key_findings'], 1):
                pdf.chapter_body(f"{i}. {finding}")
        
        measurements = category_data.get('measurements', [])
        if measurements:
            pdf.chapter_title("Measurements")
            for measure in measurements:
                pdf.add_field(measure.get('structure', 'Unknown'), measure.get('value', 'N/A'))
            pdf.ln(3)
        
        pdf.chapter_title("Impression")
        pdf.chapter_body(category_data.get('impression', 'Not documented'))
        
        recommendations = category_data.get('recommendations', [])
        if recommendations:
            pdf.chapter_title("Recommendations")
            for rec in recommendations:
                pdf.chapter_body(f"* {rec}")
    
    # Verbatim Report
    pdf.add_page()
    pdf.chapter_title("Complete Report")
    pdf.set_font('Courier', '', 9)
    pdf.multi_cell(0, 5, sanitize_text(raw_transcript))
    
    # Save
    filename = f"Imaging_{patient_data['mrn']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    filepath = os.path.join(output_folder, filename)
    pdf.output(filepath)
    
    logger.info(f"PDF generated: {filepath}")
    return filepath


def generate_lab_results_pdf(
    patient_data: Dict,
    category_data: Dict,
    raw_transcript: str,
    output_folder: str = "clinical_pdfs"
) -> str:
    """
    Generate PDF for Lab Results
    """
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)
    
    pdf = MedicalRecordPDF("Laboratory Results")
    pdf.alias_nb_pages()
    pdf.add_page()
    
    # Patient Header
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 8, sanitize_text(f"Patient: {patient_data['name']}"), 0, 1)
    pdf.add_field("MRN", patient_data['mrn'])
    pdf.add_field("DOB", patient_data.get('dob', 'N/A'))
    pdf.ln(5)
    
    # Structured Data
    if 'error' not in category_data:
        pdf.chapter_title("Lab Information")
        pdf.add_field("Lab Panel", category_data.get('lab_panel', 'N/A'))
        pdf.add_field("Collection Date", category_data.get('collection_date', 'N/A'))
        pdf.ln(3)
        
        # Critical Values Warning
        critical = category_data.get('critical_values', [])
        if critical:
            pdf.set_fill_color(255, 200, 200)
            pdf.set_font('Arial', 'B', 12)
            pdf.cell(0, 10, "!! CRITICAL VALUES !!", 0, 1, 'C', True)
            pdf.set_font('Arial', 'B', 11)
            for crit in critical:
                pdf.cell(0, 6, sanitize_text(f"  * {crit}"), 0, 1)
            pdf.ln(3)
        
        # Abnormal Results
        abnormal = category_data.get('abnormal_values', [])
        if abnormal:
            pdf.chapter_title("Abnormal Results")
            pdf.set_font('Arial', 'B', 10)
            pdf.cell(60, 6, "Test", 1, 0, 'C')
            pdf.cell(40, 6, "Value", 1, 0, 'C')
            pdf.cell(30, 6, "Flag", 1, 0, 'C')
            pdf.cell(60, 6, "Reference Range", 1, 1, 'C')
            
            pdf.set_font('Arial', '', 9)
            for result in abnormal:
                pdf.cell(60, 6, sanitize_text(result.get('test', 'N/A')), 1, 0)
                pdf.cell(40, 6, sanitize_text(result.get('value', 'N/A')), 1, 0)
                
                flag = result.get('flag', 'N/A')
                if flag == 'High':
                    pdf.set_text_color(255, 0, 0)
                elif flag == 'Low':
                    pdf.set_text_color(0, 0, 255)
                pdf.cell(30, 6, sanitize_text(flag), 1, 0, 'C')
                pdf.set_text_color(0, 0, 0)
                
                pdf.cell(60, 6, sanitize_text(result.get('reference', 'N/A')), 1, 1)
            pdf.ln(3)
        
        # Key Labs
        pdf.chapter_title("Key Laboratory Values")
        pdf.add_field("Creatinine", category_data.get('creatinine', 'N/A'))
        pdf.add_field("GFR", category_data.get('gfr', 'N/A'))
        pdf.add_field("INR", category_data.get('inr', 'N/A'))
        pdf.add_field("Hemoglobin", category_data.get('hemoglobin', 'N/A'))
        pdf.add_field("WBC", category_data.get('wbc', 'N/A'))
        pdf.ln(3)
        
        interpretation = category_data.get('interpretation', '')
        if interpretation:
            pdf.chapter_title("Interpretation")
            pdf.chapter_body(interpretation)
    
    # Complete Results
    pdf.add_page()
    pdf.chapter_title("Complete Lab Report")
    pdf.set_font('Courier', '', 9)
    pdf.multi_cell(0, 5, sanitize_text(raw_transcript))
    
    # Save
    filename = f"Labs_{patient_data['mrn']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    filepath = os.path.join(output_folder, filename)
    pdf.output(filepath)
    
    logger.info(f"PDF generated: {filepath}")
    return filepath


def generate_office_visit_pdf(
    patient_data: Dict,
    category_data: Dict,
    raw_transcript: str,
    output_folder: str = "clinical_pdfs"
) -> str:
    """
    Generate PDF for Office Visit Note
    """
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)
    
    pdf = MedicalRecordPDF("Office Visit Note")
    pdf.alias_nb_pages()
    pdf.add_page()
    
    # Patient Header
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 8, sanitize_text(f"Patient: {patient_data['name']}"), 0, 1)
    pdf.add_field("MRN", patient_data['mrn'])
    pdf.add_field("DOB", patient_data.get('dob', 'N/A'))
    pdf.ln(5)
    
    # Structured Data
    if 'error' not in category_data:
        pdf.chapter_title("Visit Information")
        pdf.add_field("Visit Type", category_data.get('visit_type', 'N/A'))
        pdf.add_field("Visit Date", category_data.get('visit_date', 'N/A'))
        pdf.ln(3)
        
        pdf.chapter_title("Chief Complaint")
        pdf.chapter_body(category_data.get('chief_complaint', 'Not documented'))
        
        pdf.chapter_title("History of Present Illness")
        pdf.chapter_body(category_data.get('hpi', 'Not documented'))
        
        medications = category_data.get('medications', [])
        if medications:
            pdf.chapter_title("Current Medications")
            for med in medications:
                pdf.chapter_body(f"* {med}")
        
        allergies = category_data.get('allergies', [])
        if allergies:
            pdf.chapter_title("Allergies")
            for allergy in allergies:
                pdf.chapter_body(f"* {allergy}")
        
        vitals = category_data.get('vitals', {})
        if vitals:
            pdf.chapter_title("Vital Signs")
            pdf.add_field("Blood Pressure", vitals.get('bp', 'N/A'))
            pdf.add_field("Heart Rate", vitals.get('hr', 'N/A'))
            pdf.add_field("Temperature", vitals.get('temp', 'N/A'))
            pdf.add_field("Weight", vitals.get('weight', 'N/A'))
            pdf.ln(3)
        
        exam = category_data.get('physical_exam', '')
        if exam:
            pdf.chapter_title("Physical Examination")
            pdf.chapter_body(exam)
        
        pdf.chapter_title("Assessment")
        pdf.chapter_body(category_data.get('assessment', 'Not documented'))
        
        pdf.chapter_title("Plan")
        pdf.chapter_body(category_data.get('plan', 'Not documented'))
    
    # Verbatim Note
    pdf.add_page()
    pdf.chapter_title("Complete Visit Note")
    pdf.set_font('Courier', '', 9)
    pdf.multi_cell(0, 5, sanitize_text(raw_transcript))
    
    # Save
    filename = f"Visit_{patient_data['mrn']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    filepath = os.path.join(output_folder, filename)
    pdf.output(filepath)
    
    logger.info(f"PDF generated: {filepath}")
    return filepath


# ==================== Clinical Synopsis PDF ====================

def generate_synopsis_pdf(
    patient_data: Dict,
    synopsis_text: str,
    synopsis_type: str = "comprehensive",
    output_folder: str = "clinical_pdfs"
) -> str:
    """
    Generate PDF from AI Clinical Synopsis
    """
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)
    
    pdf = MedicalRecordPDF(f"Clinical Synopsis - {synopsis_type.title()}")
    pdf.alias_nb_pages()
    pdf.add_page()
    
    # Patient Header
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 8, sanitize_text(f"Patient: {patient_data['name']}"), 0, 1)
    pdf.add_field("MRN", patient_data['mrn'])
    pdf.add_field("Age", f"{patient_data.get('age', 'N/A')} years")
    pdf.add_field("Synopsis Type", synopsis_type.replace('_', ' ').title())
    pdf.ln(5)
    
    # Parse and format synopsis sections
    sections = parse_synopsis_sections(synopsis_text)
    
    if sections:
        for section_name, content in sections.items():
            pdf.chapter_title(section_name.upper())
            pdf.chapter_body(content)
    else:
        # If no sections parsed, output as-is
        pdf.set_font('Arial', '', 11)
        pdf.multi_cell(0, 6, sanitize_text(synopsis_text))
    
    # Save
    filename = f"Synopsis_{synopsis_type}_{patient_data['mrn']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    filepath = os.path.join(output_folder, filename)
    pdf.output(filepath)
    
    logger.info(f"PDF generated: {filepath}")
    return filepath


def parse_synopsis_sections(text: str) -> Dict[str, str]:
    """Parse structured sections from synopsis text"""
    sections = {}
    current_section = None
    current_content = []
    
    section_headers = [
        'CHIEF COMPLAINT', 'HISTORY OF PRESENT ILLNESS', 'HPI',
        'PAST MEDICAL HISTORY', 'PMH', 'MEDICATIONS', 'ALLERGIES',
        'SOCIAL HISTORY', 'PHYSICAL EXAMINATION', 'PHYSICAL EXAM',
        'ASSESSMENT', 'PLAN', 'ASSESSMENT AND PLAN'
    ]
    
    for line in text.split('\n'):
        line_upper = line.strip().upper()
        
        # Check if line is a section header
        if any(header in line_upper for header in section_headers):
            # Save previous section
            if current_section and current_content:
                sections[current_section] = '\n'.join(current_content).strip()
            
            current_section = line.strip().rstrip(':')
            current_content = []
        elif current_section and line.strip():
            current_content.append(line.strip())
    
    # Save last section
    if current_section and current_content:
        sections[current_section] = '\n'.join(current_content).strip()
    
    return sections


# ==================== Main PDF Generator ====================

def generate_medical_record_pdf(
    patient_data: Dict,
    category: str,
    category_data: Dict,
    raw_transcript: str,
    output_folder: str = "clinical_pdfs"
) -> str:
    """
    Main function to generate PDF based on category
    
    Args:
        patient_data: Dict with name, mrn, dob, age
        category: operative_note, imaging, lab_result, office_visit
        category_data: Parsed structured data from Gemini
        raw_transcript: Original transcript text
        output_folder: Where to save PDFs
    
    Returns:
        File path of generated PDF
    """
    logger.info(f"Generating {category} PDF for patient {patient_data['mrn']}")
    
    try:
        if category == "operative_note":
            return generate_operative_note_pdf(patient_data, category_data, raw_transcript, output_folder)
        elif category == "imaging":
            return generate_imaging_pdf(patient_data, category_data, raw_transcript, output_folder)
        elif category == "lab_result":
            return generate_lab_results_pdf(patient_data, category_data, raw_transcript, output_folder)
        elif category == "office_visit":
            return generate_office_visit_pdf(patient_data, category_data, raw_transcript, output_folder)
        else:
            # Fallback to office visit format
            return generate_office_visit_pdf(patient_data, category_data, raw_transcript, output_folder)
    
    except Exception as e:
        logger.error(f"PDF generation failed: {e}", exc_info=True)
        raise