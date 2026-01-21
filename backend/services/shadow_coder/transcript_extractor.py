"""
Transcript Extractor Service
Uses Claude to extract structured clinical facts from voice transcripts

Migrated from SCC scc-shadow-coder/services/transcriptExtractor.js
"""
import os
import json
import logging
import re
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)

# Try to import anthropic - will fail gracefully if not installed
try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False
    logger.warning("anthropic package not installed - Shadow Coder extraction will be limited")


class TranscriptExtractor:
    """
    Extracts structured clinical facts from voice transcripts using Claude AI.
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        self.model = "claude-sonnet-4-20250514"
        self.client = None

        if ANTHROPIC_AVAILABLE and self.api_key:
            self.client = anthropic.Anthropic(api_key=self.api_key)
            logger.info("TranscriptExtractor initialized with Claude API")
        else:
            logger.warning("TranscriptExtractor running without Claude API - extraction disabled")

    @property
    def is_available(self) -> bool:
        """Check if extraction is available."""
        return self.client is not None

    async def extract_pad_facts(
        self,
        transcript: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Extract PAD-relevant clinical facts from a transcript.

        Args:
            transcript: The voice note transcript text
            context: Optional context with patient_name, mrn, procedure_type

        Returns:
            Dict with success, facts, summary, missing_for_coding
        """
        if not self.is_available:
            return {
                "success": False,
                "error": "Claude API not configured",
                "facts": [],
                "summary": "",
                "missing_for_coding": []
            }

        context = context or {}

        system_prompt = """You are a clinical documentation specialist extracting structured data from vascular surgery voice notes for coding compliance.

Extract ONLY facts that are explicitly stated or strongly implied. Do not infer or assume.

Return a JSON object with these possible fields (omit if not mentioned):

PATIENT INFO:
- "patient_name": string
- "mrn": string
- "encounter_date": string

SYMPTOM CLASSIFICATION:
- "pad_symptom_class": "asymptomatic" | "claudication" | "rest_pain" | "tissue_loss"
- "claudication_distance": { "value": number, "unit": "blocks" | "feet" | "meters" }
- "activity_limitation_documented": boolean (true if lifestyle-limiting symptoms described)
- "limb_threatening_documented": boolean (true if limb threat/amputation risk mentioned)

HEMODYNAMICS:
- "abi_value": { "left": number, "right": number }
- "tbi_value": { "left": number, "right": number }
- "toe_pressure": { "left": number, "right": number }
- "tcpo2": { "left": number, "right": number }

ANATOMY:
- "laterality": "left" | "right" | "bilateral"
- "target_territory": "iliac" | "femoral_popliteal" | "tibial_peroneal" | "inframalleolar" | "renal" | "carotid"
- "target_vessel": string[] (e.g., ["sfa", "popliteal", "anterior_tibial"])
- "lesion_complexity": "straightforward" | "complex" (complex = CTO, heavy calcification, long segment)

WOUND/TISSUE LOSS:
- "wound_present": boolean
- "wound_location": string
- "wound_stage": string (WIfI or Wagner if mentioned)
- "gangrene_present": boolean
- "infection_present": boolean

MEDICAL MANAGEMENT (for claudication):
- "antiplatelet_documented": boolean
- "statin_documented": boolean
- "exercise_program_documented": boolean
- "smoking_cessation_documented": boolean

PROCEDURE:
- "procedure_planned": "angioplasty" | "stent" | "atherectomy" | "bypass" | "angiogram"
- "procedure_technique": "pta_only" | "stent" | "atherectomy" | "atherectomy_stent" | "lithotripsy"
- "stent_justification": "calcified_lesion" | "total_occlusion" | "eccentric_lesion" | "high_embolization_risk"

COMORBIDITIES:
- "diabetes_status": boolean
- "smoking_status": "current" | "former" | "never"
- "renal_status": "normal" | "ckd" | "esrd_dialysis"
- "egfr": number
- "creatinine": number

PRIOR HISTORY:
- "prior_intervention_documented": boolean
- "prior_intervention": [{ "type": string, "date": string, "vessel": string }]

CAROTID-SPECIFIC (if carotid procedure):
- "carotid_stenosis_degree": number (percent)
- "carotid_symptom_status": "symptomatic" | "asymptomatic"
- "nihss_documented": boolean
- "shared_decision_documented": boolean

For each extracted fact, also provide a confidence score (0.0-1.0) and the relevant text snippet.

Respond ONLY with valid JSON in this format:
{
  "facts": [
    {
      "fact_type": "laterality",
      "value": "left",
      "confidence": 0.95,
      "source_snippet": "left leg claudication"
    }
  ],
  "summary": "Brief clinical summary",
  "missing_for_coding": ["list of important missing elements for PAD coding"]
}"""

        user_prompt = f"""Extract clinical facts from this vascular surgery voice note:

---
{transcript}
---

{f'Known patient: {context.get("patient_name")}' if context.get("patient_name") else ''}
{f'Known MRN: {context.get("mrn")}' if context.get("mrn") else ''}
{f'Procedure context: {context.get("procedure_type")}' if context.get("procedure_type") else ''}"""

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=2000,
                system=system_prompt,
                messages=[
                    {"role": "user", "content": user_prompt}
                ]
            )

            content = response.content[0].text

            # Parse JSON from response (handle potential markdown wrapping)
            json_str = content
            if "```json" in content:
                json_str = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                json_str = content.split("```")[1].split("```")[0]

            result = json.loads(json_str.strip())

            return {
                "success": True,
                "facts": result.get("facts", []),
                "summary": result.get("summary", ""),
                "missing_for_coding": result.get("missing_for_coding", []),
                "raw_response": content
            }

        except json.JSONDecodeError as e:
            logger.error(f"JSON parsing error in extraction: {e}")
            return {
                "success": False,
                "error": f"Failed to parse extraction result: {str(e)}",
                "facts": [],
                "summary": "",
                "missing_for_coding": []
            }
        except Exception as e:
            logger.error(f"Extraction error: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "facts": [],
                "summary": "",
                "missing_for_coding": []
            }

    async def classify_pad_symptoms(self, transcript: str) -> Optional[Dict[str, Any]]:
        """
        Quick symptom classification without full extraction.

        Returns:
            Dict with class, confidence, evidence or None on error
        """
        if not self.is_available:
            return None

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=500,
                messages=[
                    {
                        "role": "user",
                        "content": f"""Classify the PAD symptom severity in this note. Reply with JSON only:
{{"class": "asymptomatic|claudication|rest_pain|tissue_loss", "confidence": 0.0-1.0, "evidence": "brief quote"}}

Note: {transcript[:2000]}"""
                    }
                ]
            )

            text = response.content[0].text
            json_match = re.search(r'\{[\s\S]*\}', text)
            return json.loads(json_match.group()) if json_match else None

        except Exception as e:
            logger.error(f"Symptom classification error: {e}")
            return None

    async def extract_procedure_details(self, transcript: str) -> Optional[Dict[str, Any]]:
        """
        Extract CPT-relevant procedure details.

        Returns:
            Dict with procedures, modifiers_needed, bundling_concerns or None
        """
        if not self.is_available:
            return None

        system_prompt = """You are a vascular surgery coding specialist. Extract procedure details for CPT coding.

Return JSON:
{
  "procedures": [
    {
      "description": "procedure name",
      "vessel": "target vessel",
      "laterality": "left|right|bilateral",
      "approach": "percutaneous|open|hybrid",
      "techniques": ["angioplasty", "stent", "atherectomy", etc],
      "suggested_cpt": ["code1", "code2"],
      "confidence": 0.0-1.0
    }
  ],
  "modifiers_needed": ["59", "XE", etc],
  "bundling_concerns": ["potential bundling issues"]
}"""

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=1500,
                system=system_prompt,
                messages=[
                    {"role": "user", "content": f"Extract procedure coding details:\n\n{transcript}"}
                ]
            )

            text = response.content[0].text
            json_match = re.search(r'\{[\s\S]*\}', text)
            return json.loads(json_match.group()) if json_match else None

        except Exception as e:
            logger.error(f"Procedure extraction error: {e}")
            return None
