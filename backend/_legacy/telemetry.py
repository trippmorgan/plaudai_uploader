"""
=============================================================================
MEDICAL MIRROR OBSERVER TELEMETRY SERVICE
=============================================================================

ARCHITECTURAL ROLE:
    This module is the TELEMETRY BRIDGE - it sends application events to
    the Medical Mirror Observer system for AI-powered analysis and
    pattern detection. The Observer analyzes telemetry data to generate
    recommendations for improving application quality and reliability.

DATA FLOW POSITION:
    ┌────────────────────────────────────────────────────────────────────┐
    │                    APPLICATION ENDPOINTS                           │
    │   /upload, /patients, /clinical/query, /ingest/athena             │
    └────────────────────────────┬───────────────────────────────────────┘
                                 │ emit() calls
                                 ▼
    ┌────────────────────────────────────────────────────────────────────┐
    │                 telemetry.py (THIS FILE)                           │
    │                                                                    │
    │  emit(stage, action, data, success)                               │
    │    - Constructs event payload                                     │
    │    - Sends async HTTP POST to Observer                            │
    │    - Non-blocking (fire-and-forget)                               │
    │    - Graceful degradation if Observer unreachable                 │
    └────────────────────────────┬───────────────────────────────────────┘
                                 │ POST /api/events
                                 ▼
    ┌────────────────────────────────────────────────────────────────────┐
    │               Medical Mirror Observer                              │
    │               http://localhost:54112                               │
    │                                                                    │
    │   - Collects telemetry from multiple sources                      │
    │   - AI-powered pattern analysis                                   │
    │   - Generates improvement recommendations                         │
    └────────────────────────────────────────────────────────────────────┘

TELEMETRY STAGES:
    - upload: Transcript submission and processing
    - query: Patient/record lookup operations
    - ai-query: Clinical AI question answering
    - ingest: Athena EMR data ingestion
    - synopsis: AI synopsis generation

EVENT STRUCTURE (Observer's expected format):
    {
        "type": "OBSERVER_TELEMETRY",
        "source": "plaud-ai-uploader",
        "event": {
            "stage": "upload",
            "action": "TRANSCRIPT_RECEIVED",
            "success": true,
            "timestamp": "2025-01-05T10:30:00.000Z",
            "correlationId": "plaud_1735123456789",
            "data": {
                "hasPatientInfo": true,
                "recordType": "operative_note",
                ...
            }
        }
    }

DESIGN PRINCIPLES:

    1. NON-BLOCKING:
       Telemetry calls are fire-and-forget. Application flow is
       never blocked waiting for Observer response.

    2. GRACEFUL DEGRADATION:
       If Observer is unreachable, warnings are logged but
       application continues normally. No exceptions raised.

    3. CORRELATION IDS:
       Each operation gets a unique ID for tracing related events
       (e.g., TRANSCRIPT_RECEIVED → TRANSCRIPT_PROCESSED).

    4. MINIMAL OVERHEAD:
       Events are sent asynchronously with short timeouts.
       No PHI is included in telemetry data.

SECURITY MODEL:
    - No PHI sent to Observer (only counts, types, IDs)
    - Patient names, MRNs, clinical content excluded
    - Only operational metadata transmitted

USAGE:
    from backend.services.telemetry import emit

    # At start of operation
    correlation_id = await emit('upload', 'TRANSCRIPT_RECEIVED', {
        'hasPatientInfo': True,
        'recordType': 'operative_note'
    })

    # After success
    await emit('upload', 'TRANSCRIPT_PROCESSED', {
        'correlationId': correlation_id,
        'confidence': 0.95
    })

    # On error
    await emit('upload', 'TRANSCRIPT_FAILED', {
        'correlationId': correlation_id,
        'error': 'Parse error'
    }, success=False)

VERSION: 1.0.0
LAST UPDATED: 2025-01
=============================================================================
"""

import asyncio
import logging
import time
from typing import Any, Dict, Optional
from datetime import datetime

import httpx

from ..config import OBSERVER_URL

logger = logging.getLogger(__name__)

# Source identifier for this application
SOURCE_NAME = "plaud-ai-uploader"

# HTTP client timeout (short to avoid blocking)
TIMEOUT_SECONDS = 2.0


async def emit(
    stage: str,
    action: str,
    data: Optional[Dict[str, Any]] = None,
    success: bool = True,
    correlation_id: Optional[str] = None
) -> str:
    """
    Emit a telemetry event to the Medical Mirror Observer.

    Args:
        stage: Event category (upload, query, ai-query, ingest, synopsis)
        action: Specific action name (TRANSCRIPT_RECEIVED, PATIENTS_QUERIED, etc.)
        data: Optional dictionary of event-specific data
        success: Whether the operation succeeded
        correlation_id: Optional ID to link related events

    Returns:
        The correlation ID used for this event (for linking follow-up events)

    Note:
        This function is fire-and-forget. It will never raise exceptions
        or block the calling code for more than TIMEOUT_SECONDS.
    """
    # Generate correlation ID if not provided
    if correlation_id is None:
        correlation_id = data.get('correlationId') if data else None
    if correlation_id is None:
        correlation_id = f"plaud_{int(time.time() * 1000)}"

    # Construct event payload in Observer's expected format
    # Observer expects: { type: "OBSERVER_TELEMETRY", source: "...", event: {...} }
    event_data = {
        "stage": stage,
        "action": action,
        "success": success,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "correlationId": correlation_id,
        "data": data or {}
    }

    # Ensure correlation ID is in data for response
    if 'correlationId' not in event_data['data']:
        event_data['data']['correlationId'] = correlation_id

    # Wrap in Observer's expected envelope
    payload = {
        "type": "OBSERVER_TELEMETRY",
        "source": SOURCE_NAME,
        "event": event_data
    }

    # Send asynchronously (fire-and-forget)
    asyncio.create_task(_send_event(payload))

    return correlation_id


async def _send_event(payload: Dict[str, Any]) -> None:
    """
    Internal function to send event to Observer.
    Handles all errors gracefully - never raises.

    Args:
        payload: The complete payload with type, source, and event envelope
    """
    if not OBSERVER_URL:
        logger.debug("[Telemetry] Observer URL not configured, skipping")
        return

    try:
        async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS) as client:
            response = await client.post(
                f"{OBSERVER_URL}/api/events",
                json=payload,
                headers={"Content-Type": "application/json"}
            )

            # Extract event details for logging
            event = payload.get('event', {})
            stage = event.get('stage', 'unknown')
            action = event.get('action', 'unknown')

            if response.status_code == 200:
                logger.debug(f"[Telemetry] Event sent: {stage}/{action}")
            else:
                logger.warning(
                    f"[Telemetry] Observer returned {response.status_code}: "
                    f"{response.text[:100]}"
                )

    except httpx.ConnectError:
        logger.debug(
            f"[Telemetry] Observer unreachable at {OBSERVER_URL} - "
            "telemetry disabled"
        )
    except httpx.TimeoutException:
        logger.debug("[Telemetry] Observer request timed out")
    except Exception as e:
        logger.warning(f"[Telemetry] Failed to send event: {e}")


def emit_sync(
    stage: str,
    action: str,
    data: Optional[Dict[str, Any]] = None,
    success: bool = True,
    correlation_id: Optional[str] = None
) -> str:
    """
    Synchronous wrapper for emit() - use when async is not available.

    Note: Creates a new event loop if needed. Prefer emit() in async contexts.
    """
    try:
        loop = asyncio.get_running_loop()
        # We're in an async context, use asyncio.create_task
        if correlation_id is None:
            correlation_id = data.get('correlationId') if data else None
        if correlation_id is None:
            correlation_id = f"plaud_{int(time.time() * 1000)}"

        asyncio.create_task(emit(stage, action, data, success, correlation_id))
        return correlation_id
    except RuntimeError:
        # No event loop running, create one
        if correlation_id is None:
            correlation_id = data.get('correlationId') if data else None
        if correlation_id is None:
            correlation_id = f"plaud_{int(time.time() * 1000)}"

        try:
            asyncio.run(_send_event_sync(stage, action, data, success, correlation_id))
        except Exception as e:
            logger.debug(f"[Telemetry] Sync emit failed: {e}")

        return correlation_id


async def _send_event_sync(
    stage: str,
    action: str,
    data: Optional[Dict[str, Any]],
    success: bool,
    correlation_id: str
) -> None:
    """Helper for sync wrapper."""
    await emit(stage, action, data, success, correlation_id)


# Convenience functions for common telemetry patterns

async def emit_upload_received(
    has_patient_info: bool,
    record_type: str,
    mrn: Optional[str] = None
) -> str:
    """Emit event when transcript upload is received."""
    return await emit('upload', 'TRANSCRIPT_RECEIVED', {
        'hasPatientInfo': has_patient_info,
        'recordType': record_type,
        'hasMrn': mrn is not None
    })


async def emit_upload_processed(
    correlation_id: str,
    patient_id: int,
    transcript_id: int,
    confidence: float,
    category: str,
    tags_count: int
) -> str:
    """Emit event when transcript processing completes."""
    return await emit('upload', 'TRANSCRIPT_PROCESSED', {
        'correlationId': correlation_id,
        'patientId': patient_id,
        'transcriptId': transcript_id,
        'confidence': confidence,
        'category': category,
        'tagsCount': tags_count
    })


async def emit_upload_failed(
    correlation_id: str,
    error: str
) -> str:
    """Emit event when transcript processing fails."""
    return await emit('upload', 'TRANSCRIPT_FAILED', {
        'correlationId': correlation_id,
        'error': error
    }, success=False)


async def emit_patients_queried(
    result_count: int,
    query_type: str
) -> str:
    """Emit event when patients are queried."""
    return await emit('query', 'PATIENTS_QUERIED', {
        'resultCount': result_count,
        'queryType': query_type
    })


async def emit_clinical_query(
    query_length: int,
    patient_found: bool
) -> str:
    """Emit event when clinical AI query is submitted."""
    return await emit('ai-query', 'QUERY_SUBMITTED', {
        'queryLength': query_length,
        'patientFound': patient_found
    })


async def emit_clinical_response(
    correlation_id: str,
    response_length: int,
    data_sources: Optional[Dict[str, int]] = None
) -> str:
    """Emit event when clinical AI response is generated."""
    return await emit('ai-query', 'RESPONSE_GENERATED', {
        'correlationId': correlation_id,
        'responseLength': response_length,
        'dataSources': data_sources or {}
    })


async def emit_ingest_received(
    event_type: str,
    has_patient_link: bool
) -> str:
    """Emit event when Athena data is received."""
    return await emit('ingest', 'ATHENA_EVENT_RECEIVED', {
        'eventType': event_type,
        'hasPatientLink': has_patient_link
    })


async def emit_ingest_processed(
    correlation_id: str,
    event_type: str,
    status: str
) -> str:
    """Emit event when Athena data processing completes."""
    return await emit('ingest', 'ATHENA_EVENT_PROCESSED', {
        'correlationId': correlation_id,
        'eventType': event_type,
        'status': status
    })


# ============================================================
# PLAUD-FETCH TELEMETRY (Bidirectional Integration)
# ============================================================

async def emit_clinical_fetch(athena_mrn: str) -> str:
    """Emit event when clinical data fetch is requested."""
    return await emit('plaud-fetch', 'FETCH_PATIENT', {
        'athena_mrn': athena_mrn
    })


async def emit_clinical_fetch_success(
    correlation_id: str,
    patient_id: int,
    event_count: int,
    duration_ms: int
) -> str:
    """Emit event when clinical data fetch succeeds."""
    return await emit('plaud-fetch', 'FETCH_SUCCESS', {
        'correlationId': correlation_id,
        'patientId': patient_id,
        'eventCount': event_count,
        'durationMs': duration_ms
    })
