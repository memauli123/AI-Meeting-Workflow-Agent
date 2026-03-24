"""
API Server — Meeting Agent Pipeline
FastAPI REST interface for the pipeline.

Start with:
    uvicorn api.server:app --reload --port 8000

Endpoints:
    POST /pipeline          Run pipeline on a transcript string
    POST /pipeline/upload   Run pipeline on an uploaded .txt file
    GET  /health            Health check
    GET  /schema            Returns the output schema
"""

from fastapi import FastAPI, HTTPException, UploadFile, File, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import time

from src.pipeline import run_pipeline

app = FastAPI(
    title="Meeting Agent Pipeline API",
    description="Enterprise-grade multi-agent system that converts meeting transcripts into structured, secure workflow JSON.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Request / Response models ─────────────────────────────────────────────────

class PipelineRequest(BaseModel):
    transcript: str
    meeting_date: Optional[str] = None  # YYYY-MM-DD

    model_config = {
        "json_schema_extra": {
            "example": {
                "transcript": "Sarah: We need to finalize the client proposal by Friday.\nJames: I'll handle the backend. Done by July 22nd.\nPriya: Salary bands are approved — keep that confidential.",
                "meeting_date": "2025-07-14",
            }
        }
    }


class PipelineResponse(BaseModel):
    success: bool
    duration_seconds: float
    output: dict


class HealthResponse(BaseModel):
    status: str
    version: str


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/health", response_model=HealthResponse, tags=["System"])
def health():
    """Simple health check endpoint."""
    return {"status": "ok", "version": "1.0.0"}


@app.get("/schema", tags=["System"])
def schema():
    """Returns the expected output schema field list."""
    return {
        "required_fields": [
            "meeting_summary",
            "decisions",
            "tasks",
            "unassigned_tasks",
            "risks_or_blockers",
            "monitoring_insights",
        ],
        "task_fields": [
            "task_id", "task_title", "description", "owner",
            "deadline", "priority", "status", "dependencies",
            "sensitivity", "allowed_roles", "risk_flags", "masked_preview",
        ],
        "sensitivity_levels": ["PUBLIC", "INTERNAL", "CONFIDENTIAL", "RESTRICTED"],
        "priority_levels": ["HIGH", "MEDIUM", "LOW"],
        "action_types": ["REMINDER", "ESCALATION", "REASSIGN"],
    }


@app.post("/pipeline", response_model=PipelineResponse, tags=["Pipeline"])
def run(request: PipelineRequest):
    """
    Run the full multi-agent pipeline on a transcript string.

    - **transcript**: Raw meeting transcript text
    - **meeting_date**: Optional ISO date (YYYY-MM-DD) to resolve relative deadlines
    """
    if not request.transcript.strip():
        raise HTTPException(status_code=400, detail="Transcript cannot be empty.")

    start = time.time()
    try:
        result = run_pipeline(request.transcript, request.meeting_date)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Pipeline error: {str(e)}")

    return {
        "success": True,
        "duration_seconds": round(time.time() - start, 2),
        "output": result,
    }


@app.post("/pipeline/upload", response_model=PipelineResponse, tags=["Pipeline"])
async def run_from_upload(
    file: UploadFile = File(...),
    meeting_date: Optional[str] = Query(None, description="Meeting date YYYY-MM-DD"),
):
    """
    Run the pipeline on an uploaded .txt transcript file.

    - **file**: .txt file containing the meeting transcript
    - **meeting_date**: Optional ISO date to resolve relative deadlines
    """
    if not file.filename.endswith(".txt"):
        raise HTTPException(status_code=400, detail="Only .txt files are supported.")

    content = await file.read()
    try:
        transcript = content.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="File must be UTF-8 encoded text.")

    if not transcript.strip():
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    start = time.time()
    try:
        result = run_pipeline(transcript, meeting_date)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Pipeline error: {str(e)}")

    return {
        "success": True,
        "duration_seconds": round(time.time() - start, 2),
        "output": result,
    }
