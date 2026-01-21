"""
Rules Engine
Evaluates PAD coding compliance rules against case facts
Generates prompts for missing documentation

Migrated from SCC scc-shadow-coder/services/rulesEngine.js
"""
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
from sqlalchemy import text
from sqlalchemy.orm import Session

from .facts_service import FactsService

logger = logging.getLogger(__name__)


# PAD Coding Rules - defines what documentation is needed
PAD_RULES = [
    {
        "id": "PAD_001_SYMPTOM_CLASS",
        "name": "PAD Symptom Classification Required",
        "description": "Must document symptom classification for PAD procedures",
        "severity": "block",
        "required_facts": ["pad_symptom_class"],
        "message": "PAD symptom classification not documented. Must specify: asymptomatic, claudication, rest pain, or tissue loss.",
        "guideline_ref": "AUC for PAD Revascularization"
    },
    {
        "id": "PAD_002_LATERALITY",
        "name": "Laterality Required",
        "description": "Must document which leg (left, right, bilateral)",
        "severity": "block",
        "required_facts": ["laterality"],
        "message": "Laterality not documented. Specify left, right, or bilateral.",
        "guideline_ref": "CPT Coding Guidelines"
    },
    {
        "id": "PAD_003_ABI_FOR_CLAUDICATION",
        "name": "ABI Required for Claudication",
        "description": "ABI/TBI needed to document objective ischemia for claudication",
        "severity": "warn",
        "condition": lambda facts: facts.get("pad_symptom_class") == "claudication",
        "required_facts": ["abi_value"],
        "alternative_facts": ["tbi_value", "toe_pressure"],
        "message": "ABI/TBI not documented. Objective ischemia should be documented for claudication intervention.",
        "guideline_ref": "TASC II, SVS Guidelines"
    },
    {
        "id": "PAD_004_MEDICAL_MGMT_CLAUDICATION",
        "name": "Medical Management for Claudication",
        "description": "Must document trial of medical management before intervention for claudication",
        "severity": "warn",
        "condition": lambda facts: facts.get("pad_symptom_class") == "claudication",
        "required_facts": ["antiplatelet_documented", "statin_documented"],
        "message": "Medical management trial not documented. Document antiplatelet and statin therapy for claudication.",
        "guideline_ref": "AUC for PAD Revascularization"
    },
    {
        "id": "PAD_005_CLI_WOUND",
        "name": "Wound Documentation for CLI",
        "description": "Wound details needed for tissue loss classification",
        "severity": "warn",
        "condition": lambda facts: facts.get("pad_symptom_class") == "tissue_loss",
        "required_facts": ["wound_present"],
        "message": "Wound documentation incomplete. Document wound location and staging for tissue loss.",
        "guideline_ref": "WIfI Classification"
    },
    {
        "id": "PAD_006_TARGET_VESSEL",
        "name": "Target Vessel Required",
        "description": "Must document target vessel for procedure coding",
        "severity": "block",
        "required_facts": ["target_vessel"],
        "message": "Target vessel not documented. Specify which vessels will be treated.",
        "guideline_ref": "CPT Vascular Coding"
    },
    {
        "id": "PAD_007_STENT_JUSTIFICATION",
        "name": "Stent Justification",
        "description": "Stent use should be justified when performed",
        "severity": "info",
        "condition": lambda facts: facts.get("procedure_technique") in ["stent", "atherectomy_stent"],
        "required_facts": ["stent_justification"],
        "message": "Stent justification not documented. Consider documenting reason for stent vs PTA alone.",
        "guideline_ref": "Medically Necessity Documentation"
    },
    {
        "id": "CAROTID_001_STENOSIS",
        "name": "Carotid Stenosis Degree",
        "description": "Must document stenosis percentage for carotid procedures",
        "severity": "block",
        "condition": lambda facts: facts.get("target_territory") == "carotid",
        "required_facts": ["carotid_stenosis_degree"],
        "message": "Carotid stenosis degree not documented. Specify percent stenosis.",
        "guideline_ref": "SVS Carotid Guidelines"
    },
    {
        "id": "CAROTID_002_SYMPTOM_STATUS",
        "name": "Carotid Symptom Status",
        "description": "Must document symptomatic vs asymptomatic for carotid",
        "severity": "block",
        "condition": lambda facts: facts.get("target_territory") == "carotid",
        "required_facts": ["carotid_symptom_status"],
        "message": "Carotid symptom status not documented. Specify symptomatic or asymptomatic.",
        "guideline_ref": "CMS LCD for Carotid Stenting"
    }
]


class RulesEngine:
    """
    Evaluates coding compliance rules against case facts.
    Generates prompts for missing documentation.
    """

    def __init__(self, db: Session, facts_service: FactsService):
        self.db = db
        self.facts_service = facts_service
        self.rules = PAD_RULES

    async def evaluate_pad_rules(self, case_id: str) -> Dict[str, Any]:
        """
        Evaluate all PAD rules for a case.

        Args:
            case_id: The case/procedure UUID

        Returns:
            Dict with rules_evaluated, prompts_created, prompts_resolved
        """
        facts = await self.facts_service.get_fact_values(case_id)

        results = {
            "rules_evaluated": 0,
            "prompts_created": 0,
            "prompts_resolved": 0,
            "violations": [],
            "passed": []
        }

        for rule in self.rules:
            results["rules_evaluated"] += 1

            # Check if rule applies (condition check)
            if "condition" in rule:
                try:
                    if not rule["condition"](facts):
                        results["passed"].append(rule["id"])
                        continue
                except Exception:
                    # Condition error - skip rule
                    continue

            # Check required facts
            missing_facts = []
            for required in rule.get("required_facts", []):
                if required not in facts or facts[required] is None:
                    missing_facts.append(required)

            # Check alternative facts
            if missing_facts and "alternative_facts" in rule:
                for alt in rule["alternative_facts"]:
                    if alt in facts and facts[alt] is not None:
                        missing_facts = []  # Alternative satisfied
                        break

            if missing_facts:
                # Rule violated - create/update prompt
                results["violations"].append({
                    "rule_id": rule["id"],
                    "severity": rule["severity"],
                    "message": rule["message"],
                    "missing_facts": missing_facts
                })

                # Create prompt if not exists
                prompt_created = await self._create_or_update_prompt(case_id, rule, missing_facts)
                if prompt_created:
                    results["prompts_created"] += 1
            else:
                results["passed"].append(rule["id"])

                # Resolve any existing prompt for this rule
                resolved = await self._resolve_prompt(case_id, rule["id"])
                if resolved:
                    results["prompts_resolved"] += 1

        return results

    async def _create_or_update_prompt(
        self,
        case_id: str,
        rule: Dict,
        missing_facts: List[str]
    ) -> bool:
        """
        Create a prompt instance if one doesn't exist for this rule.

        Returns:
            True if new prompt was created
        """
        # Check if active prompt already exists
        check_sql = text("""
            SELECT id FROM scc_prompt_instances
            WHERE case_id = :case_id
              AND rule_id = :rule_id
              AND status = 'active'
        """)

        result = self.db.execute(check_sql, {
            "case_id": case_id,
            "rule_id": rule["id"]
        })
        existing = result.fetchone()

        if existing:
            return False  # Prompt already exists

        # Create new prompt
        action_choices = [
            {"action_id": "DOCUMENT", "label": "Document Now", "type": "note"},
            {"action_id": "SNOOZE_24H", "label": "Remind Tomorrow", "type": "snooze", "duration_hours": 24},
            {"action_id": "DISMISS", "label": "Not Applicable", "type": "dismiss"}
        ]

        insert_sql = text("""
            INSERT INTO scc_prompt_instances (
                id, case_id, rule_id, status, severity,
                message, details, guideline_ref, action_choices,
                first_surfaced_at, "createdAt", "updatedAt"
            ) VALUES (
                gen_random_uuid(), :case_id, :rule_id, 'active', :severity::enum_severity,
                :message, :details, :guideline_ref, :action_choices::jsonb,
                NOW(), NOW(), NOW()
            )
            ON CONFLICT (case_id, rule_id) WHERE status = 'active'
            DO NOTHING
            RETURNING id
        """)

        try:
            result = self.db.execute(insert_sql, {
                "case_id": case_id,
                "rule_id": rule["id"],
                "severity": rule["severity"],
                "message": rule["message"],
                "details": f"Missing documentation: {', '.join(missing_facts)}",
                "guideline_ref": rule.get("guideline_ref"),
                "action_choices": str(action_choices)
            })
            self.db.commit()
            return result.fetchone() is not None
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to create prompt: {e}")
            return False

    async def _resolve_prompt(self, case_id: str, rule_id: str) -> bool:
        """
        Resolve an active prompt when facts are now satisfied.

        Returns:
            True if a prompt was resolved
        """
        sql = text("""
            UPDATE scc_prompt_instances
            SET status = 'resolved',
                resolution_type = 'fact_added',
                resolved_at = NOW(),
                "updatedAt" = NOW()
            WHERE case_id = :case_id
              AND rule_id = :rule_id
              AND status = 'active'
            RETURNING id
        """)

        try:
            result = self.db.execute(sql, {
                "case_id": case_id,
                "rule_id": rule_id
            })
            self.db.commit()
            return result.fetchone() is not None
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to resolve prompt: {e}")
            return False

    async def get_active_prompts(self, case_id: str) -> List[Dict[str, Any]]:
        """
        Get all active prompts for a case.

        Args:
            case_id: The case/procedure UUID

        Returns:
            List of active prompt instances
        """
        sql = text("""
            SELECT
                id::text, case_id::text, rule_id, status::text, severity::text,
                message, details, guideline_ref, action_choices,
                snoozed_until, first_surfaced_at, view_count, snooze_count,
                "createdAt", "updatedAt"
            FROM scc_prompt_instances
            WHERE case_id = :case_id
              AND status = 'active'
            ORDER BY
                CASE severity
                    WHEN 'block' THEN 1
                    WHEN 'warn' THEN 2
                    WHEN 'info' THEN 3
                END,
                first_surfaced_at ASC
        """)

        result = self.db.execute(sql, {"case_id": case_id})
        rows = result.fetchall()

        return [
            {
                "id": row[0],
                "case_id": row[1],
                "rule_id": row[2],
                "status": row[3],
                "severity": row[4],
                "message": row[5],
                "details": row[6],
                "guideline_ref": row[7],
                "action_choices": row[8],
                "snoozed_until": row[9].isoformat() if row[9] else None,
                "first_surfaced_at": row[10].isoformat() if row[10] else None,
                "view_count": row[11],
                "snooze_count": row[12],
                "created_at": row[13].isoformat() if row[13] else None,
                "updated_at": row[14].isoformat() if row[14] else None
            }
            for row in rows
        ]

    async def get_prompt_summary(self, case_id: str) -> Dict[str, int]:
        """
        Get counts of prompts by severity.

        Args:
            case_id: The case/procedure UUID

        Returns:
            Dict with counts by severity
        """
        sql = text("""
            SELECT severity::text, COUNT(*)
            FROM scc_prompt_instances
            WHERE case_id = :case_id
              AND status = 'active'
            GROUP BY severity
        """)

        result = self.db.execute(sql, {"case_id": case_id})
        rows = result.fetchall()

        summary = {"block": 0, "warn": 0, "info": 0, "total": 0}
        for row in rows:
            summary[row[0]] = row[1]
            summary["total"] += row[1]

        return summary
