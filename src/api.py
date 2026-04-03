"""FastAPI application entry point."""

import asyncio
import logging
import os
import tempfile

import uvicorn
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.deps import get_auditor, get_manager
from src.models import (
    EventSearchRequest,
    EventResponse,
    SearchResponse,
    TranscribeFileRequest,
    VerifyEventRequest,
    VerifyEventResponse,
)
from src.observability.middleware import setup_observability
from src.transcription import convert_to_wav, transcribe_file

logger = logging.getLogger(__name__)

app = FastAPI(
    title="EventFinder AI",
    description="Multi-agent event discovery system",
    version="0.1.0",
)

setup_observability(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok"}


@app.post("/search", response_model=SearchResponse)
async def search_events(request: EventSearchRequest):
    """Search for free events."""
    try:
        preferences = request.preferences.model_dump() if request.preferences else None
        manager = get_manager()
        result = manager.execute_workflow(request.query, preferences)

        event_responses = [
            EventResponse(
                id=event.id,
                title=event.title,
                location=event.location,
                date=event.date,
                time=event.time,
                description=event.description,
                url=event.url,
                price=event.price,
                category=event.category,
            )
            for event in (result.get("events") or [])
        ]
        logger.info("event_responses: %s", event_responses)
        return SearchResponse(
            success=result.get("success", False),
            events=event_responses,
            message="Search completed successfully"
            if result.get("success")
            else "No events found",
            query_used=result.get("query_used"),
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/verify", response_model=VerifyEventResponse)
async def verify_event(request: VerifyEventRequest):
    """Verify if an event is free."""
    try:
        auditor = get_auditor()
        status = auditor.verify_event_free(request.description)
        warnings = auditor.get_warnings(request.description)
        return VerifyEventResponse(status=status.value, warnings=warnings)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/transcribe")
async def transcribe(file: UploadFile = File(...)):
    """Accept an uploaded audio file and return transcription text."""
    try:
        suffix = os.path.splitext(file.filename)[1] or ".webm"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as in_f:
            tmp_in = in_f.name
            in_f.write(await file.read())

        tmp_wav = tempfile.NamedTemporaryFile(delete=False, suffix=".wav").name
        try:
            convert_to_wav(tmp_in, tmp_wav)
        except Exception:
            os.unlink(tmp_in)
            return JSONResponse(
                status_code=400, content={"error": "ffmpeg conversion failed"}
            )

        loop = asyncio.get_running_loop()
        text = await loop.run_in_executor(None, transcribe_file, tmp_wav)

        for path in (tmp_in, tmp_wav):
            try:
                os.unlink(path)
            except Exception:
                pass

        return {"text": text}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.post("/transcribe-file")
async def transcribe_file_endpoint(request: TranscribeFileRequest):
    """Transcribe an audio file by path (used by Tauri mic-recorder plugin)."""
    try:
        file_path = request.file_path

        if not os.path.exists(file_path):
            return JSONResponse(
                status_code=400, content={"error": f"File not found: {file_path}"}
            )

        tmp_wav = tempfile.NamedTemporaryFile(delete=False, suffix=".wav").name
        try:
            convert_to_wav(file_path, tmp_wav)
        except Exception:
            return JSONResponse(
                status_code=400, content={"error": "ffmpeg conversion failed"}
            )

        loop = asyncio.get_running_loop()
        text = await loop.run_in_executor(None, transcribe_file, tmp_wav)

        try:
            os.unlink(tmp_wav)
        except Exception:
            pass

        return {"text": text}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
