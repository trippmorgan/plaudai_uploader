---
path: /home/server1/plaudai_uploader/backend/_legacy/pdf_generator.py
type: service
updated: 2026-01-21
status: active
---

# pdf_generator.py

## Purpose

Generates professional PDF medical documents from clinical data using FPDF library. Creates Albany Vascular Specialist Center branded reports for operative notes, imaging reports, lab results, office visits, and AI-generated clinical synopses. Handles Unicode-to-ASCII text sanitization to ensure PDF compatibility.

## Exports

- `MedicalRecordPDF` - Custom FPDF subclass with Albany Vascular letterhead and branded styling (header, footer, chapter formatting)
- `sanitize_text(text: str) -> str` - Converts Unicode characters (smart quotes, dashes, special symbols) to ASCII equivalents for PDF compatibility
- `generate_operative_note_pdf(patient_data, category_data, raw_transcript, output_folder) -> str` - Creates operative note PDF with procedure info, findings, devices, complications
- `generate_imaging_pdf(patient_data, category_data, raw_transcript, output_folder) -> str` - Creates imaging report PDF with study info, findings, measurements, impression
- `generate_lab_results_pdf(patient_data, category_data, raw_transcript, output_folder) -> str` - Creates lab results PDF with critical values highlighting and abnormal results table
- `generate_office_visit_pdf(patient_data, category_data, raw_transcript, output_folder) -> str` - Creates office visit PDF with vitals, medications, assessment, plan
- `generate_synopsis_pdf(patient_data, synopsis_text, synopsis_type, output_folder) -> str` - Creates clinical synopsis PDF from AI-generated content
- `generate_medical_record_pdf(patient_data, category, category_data, raw_transcript, output_folder) -> str` - Main dispatch function that routes to category-specific generators
- `parse_synopsis_sections(text: str) -> Dict[str, str]` - Parses section headers from synopsis text for structured display

## Dependencies

- fpdf - PDF generation library for creating documents
- datetime - Timestamp formatting for document headers
- os - Directory creation and file path handling
- logging - Error and success logging for PDF operations

## Used By

TBD

## Notes

All PDFs include Albany Vascular contact information (2300 Dawson Road, Albany GA) in the footer. The MedicalRecordPDF class uses brand colors: primary brown (#6B5D4F) and gold/tan (#C8A882). Lab results PDFs use color-coded flags (red for high, blue for low values). Each PDF includes both structured parsed data and the verbatim raw transcript for clinical reference.
