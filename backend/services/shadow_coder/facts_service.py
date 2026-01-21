"""
Facts Service
Manages the "Clinical Truth Map" for each case
Provides the fact state that drives the rules engine

Migrated from SCC scc-shadow-coder/services/factsService.js
"""
import logging
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime
from uuid import UUID
from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class FactsService:
    """
    Manages clinical facts extracted from voice notes.
    Facts drive the rules engine for coding compliance.
    """

    def __init__(self, db: Session):
        self.db = db

    async def get_fact_map(self, case_id: str) -> Dict[str, Any]:
        """
        Get the current fact map for a case.
        Uses DISTINCT ON to get the latest fact of each type.
        Respects superseded facts (soft deletes).

        Args:
            case_id: The case/procedure UUID

        Returns:
            Dict mapping fact_type to fact data
        """
        sql = text("""
            SELECT DISTINCT ON (fact_type)
                id,
                fact_type,
                value_json,
                confidence,
                source_type,
                verified,
                "createdAt"
            FROM scc_case_facts
            WHERE case_id = :case_id
              AND superseded_at IS NULL
            ORDER BY fact_type, "createdAt" DESC, confidence DESC NULLS LAST
        """)

        result = self.db.execute(sql, {"case_id": case_id})
        rows = result.fetchall()

        fact_map = {}
        for row in rows:
            fact_map[row[1]] = {  # fact_type
                "value": row[2],  # value_json
                "confidence": row[3],
                "verified": row[5],
                "fact_id": str(row[0]),
                "recorded_at": row[6].isoformat() if row[6] else None
            }

        return fact_map

    async def get_fact_values(self, case_id: str) -> Dict[str, Any]:
        """
        Get just the values (simplified map for rule evaluation).

        Args:
            case_id: The case/procedure UUID

        Returns:
            Dict mapping fact_type to value only
        """
        fact_map = await self.get_fact_map(case_id)
        return {key: data["value"] for key, data in fact_map.items()}

    async def add_fact(
        self,
        case_id: str,
        fact_type: str,
        value: Any,
        confidence: float = 1.0,
        source_type: str = "manual",
        voice_note_id: Optional[str] = None,
        source_ref: Optional[Dict] = None,
        patient_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Add a new fact to a case.

        Args:
            case_id: The case/procedure UUID
            fact_type: Category of fact (e.g., 'laterality', 'abi_value')
            value: The fact value (will be stored as JSONB)
            confidence: AI confidence score 0.0-1.0
            source_type: How the fact was determined
            voice_note_id: Reference to source voice note
            source_ref: Additional source metadata
            patient_id: Optional patient reference

        Returns:
            The created fact record
        """
        sql = text("""
            INSERT INTO scc_case_facts (
                id, case_id, patient_id, fact_type, value_json,
                confidence, source_type, voice_note_id, source_ref,
                "createdAt", "updatedAt"
            ) VALUES (
                gen_random_uuid(), :case_id, :patient_id, :fact_type, :value_json::jsonb,
                :confidence, :source_type::enum_source_type, :voice_note_id, :source_ref::jsonb,
                NOW(), NOW()
            )
            RETURNING id::text, fact_type, value_json, confidence, "createdAt"
        """)

        try:
            result = self.db.execute(sql, {
                "case_id": case_id,
                "patient_id": patient_id,
                "fact_type": fact_type,
                "value_json": str(value) if not isinstance(value, str) else value,
                "confidence": confidence,
                "source_type": source_type,
                "voice_note_id": voice_note_id,
                "source_ref": str(source_ref) if source_ref else None
            })
            self.db.commit()
            row = result.fetchone()

            return {
                "id": row[0],
                "fact_type": row[1],
                "value": row[2],
                "confidence": row[3],
                "created_at": row[4].isoformat() if row[4] else None
            }
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to add fact: {e}")
            raise

    async def add_facts_batch(
        self,
        case_id: str,
        facts: List[Dict[str, Any]],
        voice_note_id: Optional[str] = None,
        patient_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Add multiple facts from an extraction result.

        Args:
            case_id: The case/procedure UUID
            facts: List of fact dicts with fact_type, value, confidence, source_ref
            voice_note_id: Reference to source voice note
            patient_id: Optional patient reference

        Returns:
            List of created fact records
        """
        created = []
        for fact in facts:
            try:
                result = await self.add_fact(
                    case_id=case_id,
                    fact_type=fact.get("fact_type"),
                    value=fact.get("value"),
                    confidence=fact.get("confidence", 1.0),
                    source_type="voice_note",
                    voice_note_id=voice_note_id,
                    source_ref=fact.get("source_ref"),
                    patient_id=patient_id
                )
                created.append(result)
            except Exception as e:
                logger.error(f"Failed to add fact {fact.get('fact_type')}: {e}")

        return created

    async def supersede_fact(self, fact_id: str, new_fact_id: Optional[str] = None) -> bool:
        """
        Supersede (soft-delete) a fact.

        Args:
            fact_id: The fact to supersede
            new_fact_id: Optional reference to replacement fact

        Returns:
            True if successful
        """
        sql = text("""
            UPDATE scc_case_facts
            SET superseded_by = :new_fact_id,
                superseded_at = NOW(),
                "updatedAt" = NOW()
            WHERE id = :fact_id::uuid
        """)

        try:
            self.db.execute(sql, {"fact_id": fact_id, "new_fact_id": new_fact_id})
            self.db.commit()
            return True
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to supersede fact: {e}")
            return False

    async def verify_fact(self, fact_id: str, verified_by: str) -> bool:
        """
        Verify a fact (physician attestation).

        Args:
            fact_id: The fact to verify
            verified_by: Who verified it

        Returns:
            True if successful
        """
        sql = text("""
            UPDATE scc_case_facts
            SET verified = TRUE,
                verified_by = :verified_by,
                verified_at = NOW(),
                "updatedAt" = NOW()
            WHERE id = :fact_id::uuid
        """)

        try:
            self.db.execute(sql, {"fact_id": fact_id, "verified_by": verified_by})
            self.db.commit()
            return True
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to verify fact: {e}")
            return False

    async def get_fact_history(
        self,
        case_id: str,
        fact_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get all facts for a case (full history including superseded).

        Args:
            case_id: The case/procedure UUID
            fact_type: Optional filter by fact type

        Returns:
            List of all facts
        """
        sql = """
            SELECT
                id::text, case_id::text, patient_id::text, fact_type,
                value_json, confidence, source_type::text, voice_note_id::text,
                source_ref, verified, verified_by, verified_at,
                superseded_by::text, superseded_at, "createdAt", "updatedAt"
            FROM scc_case_facts
            WHERE case_id = :case_id
        """
        params = {"case_id": case_id}

        if fact_type:
            sql += " AND fact_type = :fact_type"
            params["fact_type"] = fact_type

        sql += ' ORDER BY "createdAt" DESC'

        result = self.db.execute(text(sql), params)
        rows = result.fetchall()

        return [
            {
                "id": row[0],
                "case_id": row[1],
                "patient_id": row[2],
                "fact_type": row[3],
                "value": row[4],
                "confidence": row[5],
                "source_type": row[6],
                "voice_note_id": row[7],
                "source_ref": row[8],
                "verified": row[9],
                "verified_by": row[10],
                "verified_at": row[11].isoformat() if row[11] else None,
                "superseded_by": row[12],
                "superseded_at": row[13].isoformat() if row[13] else None,
                "created_at": row[14].isoformat() if row[14] else None,
                "updated_at": row[15].isoformat() if row[15] else None
            }
            for row in rows
        ]

    async def has_fact(
        self,
        case_id: str,
        fact_type: str,
        validator: Optional[Callable[[Any], bool]] = None
    ) -> bool:
        """
        Check if a specific fact exists and meets criteria.

        Args:
            case_id: The case/procedure UUID
            fact_type: The fact type to check
            validator: Optional function to validate the value

        Returns:
            True if fact exists and passes validation
        """
        facts = await self.get_fact_values(case_id)
        if fact_type not in facts:
            return False
        if validator and callable(validator):
            return validator(facts[fact_type])
        return True
