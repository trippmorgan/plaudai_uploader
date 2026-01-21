"""
=============================================================================
PLAUDAI PROCESSOR - STATELESS AI PROCESSING SERVICE
=============================================================================

VERSION: 2.0.0 - Refactored for SCC Integration
PURPOSE: Pure AI processing service - SCC owns all data storage

ARCHITECTURAL ROLE:
    PlaudAI is now a stateless processing service that:
    1. Parses transcripts into structured clinical data
    2. Generates AI synopses using Google Gemini
    3. Extracts PVI registry fields from text

    SCC (Surgical Command Center) is the sole data owner:
    - All patient data stored in SCC database
    - SCC calls PlaudAI for AI processing
    - PlaudAI returns results, SCC stores them

ENDPOINTS:
    GET  /health         - Health check (no database)
    POST /api/parse      - Parse transcript → sections, tags, PVI fields
    POST /api/synopsis   - Generate AI clinical synopsis
    POST /api/extract    - Extract SVS VQI registry fields

REMOVED (now handled by SCC):
    - All /patients/* endpoints
    - All /upload endpoints
    - All /synopsis/* database endpoints
    - All /clinical/* database endpoints
    - Static file serving
    - Database initialization

DATA FLOW:
    ┌─────────────────────────────────────────────────────────────────────┐
    │  SCC Backend (localhost:3001) - Data Owner                          │
    │  ┌───────────────────────────────────────────────────────────────┐  │
    │  │  • Stores patients, transcripts, synopses                     │  │
    │  │  • Calls PlaudAI for AI processing                            │  │
    │  │  • Returns results to frontend                                │  │
    │  └───────────────────────────────────────────────────────────────┘  │
    └────────────────────────────────┬────────────────────────────────────┘
                                     │ HTTP (localhost:8001)
                                     ▼
    ┌─────────────────────────────────────────────────────────────────────┐
    │  PlaudAI Processor (THIS SERVICE) - Stateless AI                    │
    │  ┌───────────────────────────────────────────────────────────────┐  │
    │  │  /api/parse    - Regex-based field extraction                 │  │
    │  │  /api/synopsis - Gemini AI generation                         │  │
    │  │  /api/extract  - PVI registry fields                          │  │
    │  └───────────────────────────────────────────────────────────────┘  │
    └─────────────────────────────────────────────────────────────────────┘

MIGRATION FROM v1:
    - main_legacy.py contains full database-integrated version
    - This version has zero database dependencies
    - All SQLAlchemy imports removed
    - CORS restricted to SCC origins only

=============================================================================
"""
import os
import logging
from datetime import datetime
from typing import Optional, List, Dict

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Stateless services only
from .services.parser import (
    segment_summary,
    generate_tags,
    extract_pvi_fields,
    calculate_confidence_score,
    process_transcript
)
from .services.gemini_synopsis_stateless import (
    generate_synopsis_stateless,
    calculate_age
)

# ORCC Integration Router (database-backed endpoints)
from .routes.orcc import router as orcc_router

# Shadow Coder Router (migrated from SCC)
from .routes.shadow_coder import router as shadow_coder_router

# Tasks Router (new for ORCC)
from .routes.tasks import router as tasks_router

# WebSocket Server
from .websocket_server import websocket_endpoint, manager as ws_manager

# ==================== Logging Setup ====================
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# ==================== App Initialization ====================
app = FastAPI(
    title="PlaudAI Processor",
    description="Stateless AI processing service for SCC integration. Handles transcript parsing, AI synopsis generation, and PVI field extraction.",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# ==================== CORS Configuration ====================
# Allow SCC, ORCC, and local development
ALLOWED_ORIGINS = [
    "http://localhost:3001",           # SCC development
    "http://127.0.0.1:3001",           # SCC local
    "http://100.75.237.36:3001",       # SCC on Server1 (Tailscale)
    "http://localhost:5173",           # ORCC Vite dev server
    "http://127.0.0.1:5173",           # ORCC Vite local
    "http://100.104.39.64:5173",       # ORCC on Workstation (Tailscale)
    "http://100.104.39.64:3000",       # ORCC production build
    "*",                               # Allow all for development - restrict in production
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE"],  # Extended for ORCC
    allow_headers=["*"],
)

# ==================== Register ORCC Router ====================
app.include_router(orcc_router)  # ORCC Integration: /api/procedures, /api/patients

# ==================== Register Shadow Coder Router ====================
app.include_router(shadow_coder_router)  # Shadow Coder: /api/shadow-coder/*

# ==================== Register Tasks Router ====================
app.include_router(tasks_router)  # Tasks: /api/tasks/*

# ==================== WebSocket Endpoint ====================
from fastapi import WebSocket, Query as WSQuery

@app.websocket("/ws")
async def ws_endpoint(websocket: WebSocket, client_id: str = WSQuery(None)):
    """WebSocket endpoint for real-time updates."""
    await websocket_endpoint(websocket, client_id)

@app.get("/ws/stats")
async def ws_stats():
    """Get WebSocket connection statistics."""
    return ws_manager.get_stats()

# ==================== Request/Response Models ====================

class ParseRequest(BaseModel):
    """Request for transcript parsing"""
    transcript_text: str
    include_pvi_fields: bool = True

    class Config:
        json_schema_extra = {
            "example": {
                "transcript_text": "## Chief Complaint\nPatient presents with claudication...",
                "include_pvi_fields": True
            }
        }


class ParseResponse(BaseModel):
    """Response from transcript parsing"""
    sections: Dict[str, str]
    tags: List[str]
    pvi_fields: Optional[Dict] = None
    confidence_score: float
    processing_time_ms: int


class SynopsisRequest(BaseModel):
    """Request for AI synopsis generation"""
    transcript_text: str
    patient_context: Optional[Dict] = None
    style: str = "comprehensive"

    class Config:
        json_schema_extra = {
            "example": {
                "transcript_text": "Patient with PAD presenting for follow-up...",
                "patient_context": {
                    "name": "John Smith",
                    "mrn": "12345",
                    "age": 65,
                    "dob": "1960-01-15"
                },
                "style": "comprehensive"
            }
        }


class SynopsisResponse(BaseModel):
    """Response from AI synopsis generation"""
    synopsis: str
    sections: Dict[str, str]
    model_used: str
    tokens_used: int
    processing_time_ms: int


class ExtractRequest(BaseModel):
    """Request for PVI field extraction"""
    transcript_text: str

    class Config:
        json_schema_extra = {
            "example": {
                "transcript_text": "ABI: 0.6, Rutherford 4, SFA stent placed..."
            }
        }


class ExtractResponse(BaseModel):
    """Response from PVI field extraction"""
    pvi_fields: Dict
    confidence_score: float
    tags: List[str]


# ==================== Health Check ====================

@app.get("/health")
async def health():
    """
    Health check endpoint - no database dependency

    Returns service status and configuration state.
    """
    google_api_key = os.getenv("GOOGLE_API_KEY", "")
    gemini_model = os.getenv("GEMINI_MODEL", "gemini-2.0-flash-exp")

    return {
        "status": "healthy",
        "service": "plaudai-processor",
        "version": "2.0.0",
        "mode": "stateless",
        "gemini_configured": bool(google_api_key),
        "gemini_model": gemini_model if google_api_key else None,
        "timestamp": datetime.now().isoformat()
    }


# ==================== Parsing Endpoint ====================

@app.post("/api/parse", response_model=ParseResponse)
async def parse_transcript(request: ParseRequest):
    """
    Parse transcript into structured clinical data

    - Segments markdown sections (## headers)
    - Generates medical tags (PAD, claudication, etc.)
    - Extracts PVI registry fields (ABI, Rutherford, etc.)
    - Calculates confidence score

    No AI/external API calls - pure regex-based extraction.
    """
    if not request.transcript_text or not request.transcript_text.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="transcript_text cannot be empty"
        )

    logger.info(f"Parsing transcript ({len(request.transcript_text)} chars)")
    start = datetime.utcnow()

    try:
        sections, tags, pvi_fields, confidence = process_transcript(request.transcript_text)
        elapsed = int((datetime.utcnow() - start).total_seconds() * 1000)

        logger.info(f"Parse complete: {len(sections)} sections, {len(tags)} tags, "
                    f"{len(pvi_fields)} PVI fields, confidence={confidence:.2f}")

        return ParseResponse(
            sections=sections,
            tags=tags,
            pvi_fields=pvi_fields if request.include_pvi_fields else None,
            confidence_score=confidence,
            processing_time_ms=elapsed
        )

    except Exception as e:
        logger.error(f"Parse failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Parsing failed: {str(e)}"
        )


# ==================== Synopsis Endpoint ====================

@app.post("/api/synopsis", response_model=SynopsisResponse)
async def generate_synopsis(request: SynopsisRequest):
    """
    Generate AI-powered clinical synopsis using Google Gemini

    Styles:
    - comprehensive: Full H&P with 10 sections
    - visit_summary: Concise single-encounter summary
    - problem_list: Active medical problems
    - procedure_summary: Surgical history focus

    Requires GOOGLE_API_KEY environment variable.
    """
    if not request.transcript_text or not request.transcript_text.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="transcript_text cannot be empty"
        )

    valid_styles = ["comprehensive", "visit_summary", "problem_list", "procedure_summary"]
    if request.style not in valid_styles:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid style. Must be one of: {valid_styles}"
        )

    logger.info(f"Generating {request.style} synopsis ({len(request.transcript_text)} chars)")

    try:
        result = await generate_synopsis_stateless(
            transcript_text=request.transcript_text,
            patient_context=request.patient_context,
            style=request.style
        )

        return SynopsisResponse(
            synopsis=result["synopsis"],
            sections=result["sections"],
            model_used=result["model_used"],
            tokens_used=result["tokens_used"],
            processing_time_ms=result["processing_time_ms"]
        )

    except ValueError as e:
        logger.warning(f"Synopsis generation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Synopsis generation failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Synopsis generation failed: {str(e)}"
        )


# ==================== Extract Endpoint ====================

@app.post("/api/extract", response_model=ExtractResponse)
async def extract_pvi(request: ExtractRequest):
    """
    Extract PVI (Peripheral Vascular Intervention) registry fields

    Fields extracted:
    - smoking_history (Never/Former/Current)
    - rutherford_status (Classification 0-6)
    - preop_abi, preop_tbi (Ankle-Brachial Index)
    - creatinine, contrast_volume
    - arteries_treated (list)
    - access_site
    - tasc_grade (A-D)
    - complications (list)

    Also returns tags and confidence score.
    No AI calls - pure regex extraction.
    """
    if not request.transcript_text or not request.transcript_text.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="transcript_text cannot be empty"
        )

    logger.info(f"Extracting PVI fields ({len(request.transcript_text)} chars)")

    try:
        pvi_fields = extract_pvi_fields(request.transcript_text)
        tags = generate_tags(request.transcript_text)
        confidence = calculate_confidence_score(request.transcript_text, pvi_fields)

        logger.info(f"Extracted {len(pvi_fields)} PVI fields, {len(tags)} tags")

        return ExtractResponse(
            pvi_fields=pvi_fields,
            confidence_score=confidence,
            tags=tags
        )

    except Exception as e:
        logger.error(f"Extraction failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Extraction failed: {str(e)}"
        )


# ==================== Run Server ====================

if __name__ == "__main__":
    import uvicorn

    host = os.getenv("API_HOST", "0.0.0.0")
    port = int(os.getenv("API_PORT", "8001"))

    logger.info(f"Starting PlaudAI Processor on {host}:{port}")
    uvicorn.run(app, host=host, port=port)
