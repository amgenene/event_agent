"""FastAPI application entry point."""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List

from src.input_parser.parser import InputParser
from src.discovery_agent.searcher import DiscoveryAgent
from src.calendar_agent.scheduler import CalendarAgent
from src.auditor.verifier import Auditor
from src.resilience.edge_case_handler import EdgeCaseHandler
from src.orchestration.manager import Manager


# Initialize FastAPI app
app = FastAPI(
    title="EventFinder AI",
    description="Multi-agent event discovery system",
    version="0.1.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for dev; restrict in prod
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request/Response models
class UserPreferences(BaseModel):
    """User preferences for event discovery."""
    
    home_city: Optional[str] = None
    favorite_genres: Optional[List[str]] = None
    radius_miles: Optional[int] = 5
    max_transit_minutes: Optional[int] = 30
    time_window_days: Optional[int] = 7
    country: Optional[str] = None
    search_lang: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class EventSearchRequest(BaseModel):
    """Request model for event search."""
    
    query: str
    preferences: Optional[UserPreferences] = None


class EventResponse(BaseModel):
    """Response model for discovered event."""
    
    id: str
    title: str
    location: str
    date: str
    time: str
    description: str
    url: str
    price: str = "Free"
    category: Optional[str] = None


class SearchResponse(BaseModel):
    """Response model for search results."""
    
    success: bool
    events: List[EventResponse]
    message: str


class VerifyEventRequest(BaseModel):
    """Request model for event verification."""
    
    description: str


class VerifyEventResponse(BaseModel):
    """Response model for event verification."""
    
    status: str
    warnings: List[str]


# Initialize components (in production, use dependency injection)
input_parser = InputParser()
calendar_agent = CalendarAgent(participants=["alazar.genene@gmail.com"])
discovery_agent = DiscoveryAgent()
auditor = Auditor()
edge_case_handler = EdgeCaseHandler()

manager = Manager(
    input_parser=input_parser,
    calendar_agent=calendar_agent,
    discovery_agent=discovery_agent,
    auditor=auditor,
    edge_case_handler=edge_case_handler
)


# API Endpoints
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok"}


@app.post("/search", response_model=SearchResponse)
async def search_events(request: EventSearchRequest):
    """
    Search for free events.
    
    Args:
        request: Event search request with query and optional preferences
    
    Returns:
        SearchResponse with discovered events
    """
    try:
        preferences = request.preferences.model_dump() if request.preferences else None
        
        result = manager.execute_workflow(request.query, preferences)
        
        # Convert events to response format
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
                category=event.category
            )
            for event in (result.get("events") or [])
        ]
        
        return SearchResponse(
            success=result.get("success", False),
            events=event_responses,
            message="Search completed successfully" if result.get("success") else "No events found"
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/verify", response_model=VerifyEventResponse)
async def verify_event(request: VerifyEventRequest):
    """
    Verify if an event is free.
    
    Args:
        request: Event description to verify
    
    Returns:
        VerifyEventResponse with status and warnings
    """
    try:
        status = auditor.verify_event_free(request.description)
        warnings = auditor.get_warnings(request.description)
        
        return VerifyEventResponse(
            status=status.value,
            warnings=warnings
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)


# --- audio transcription endpoint using faster-whisper ---
import os
import tempfile
import subprocess
import asyncio
from fastapi import UploadFile, File
from fastapi.responses import JSONResponse
from concurrent.futures import ThreadPoolExecutor

try:
    from faster_whisper import WhisperModel
except Exception:
    WhisperModel = None

MODEL_NAME = os.environ.get("WHISPER_MODEL", "small")
_executor = ThreadPoolExecutor(max_workers=1)
_model = None

def get_model():
    global _model
    if _model is None:
        if WhisperModel is None:
            raise RuntimeError("faster-whisper not installed")
        # Use int8 for CPU compatibility as int8_float16 is not supported on all architectures
        _model = WhisperModel(MODEL_NAME, device="cpu", compute_type="int8")
    return _model

def convert_to_wav(input_path: str, out_path: str):
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        input_path,
        "-ar",
        "16000",
        "-ac",
        "1",
        out_path,
    ]
    subprocess.check_call(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return out_path

def _transcribe_file(wav_path: str):
    model = get_model()
    segments, _ = model.transcribe(wav_path, beam_size=5)
    text = "".join([s.text for s in segments])
    return text

@app.post("/transcribe")
async def transcribe(file: UploadFile = File(...)):
    """
    Accepts an uploaded audio file (e.g., webm) and returns the transcription text.
    """
    try:
        suffix = os.path.splitext(file.filename)[1] or ".webm"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as in_f:
            tmp_in = in_f.name
            in_f.write(await file.read())

        tmp_wav = tempfile.NamedTemporaryFile(delete=False, suffix=".wav").name
        try:
            convert_to_wav(tmp_in, tmp_wav)
        except subprocess.CalledProcessError:
            os.unlink(tmp_in)
            return JSONResponse(status_code=400, content={"error": "ffmpeg conversion failed"})

        loop = asyncio.get_running_loop()
        text = await loop.run_in_executor(_executor, _transcribe_file, tmp_wav)

        try:
            os.unlink(tmp_in)
        except Exception:
            pass
        try:
            os.unlink(tmp_wav)
        except Exception:
            pass

        return {"text": text}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})


class TranscribeFileRequest(BaseModel):
    """Request model for transcribing a file by path."""
    file_path: str


@app.post("/transcribe-file")
async def transcribe_file(request: TranscribeFileRequest):
    """
    Accepts a file path to an audio file and returns the transcription text.
    Used by native Tauri mic-recorder plugin which saves recordings to disk.
    """
    try:
        file_path = request.file_path
        
        if not os.path.exists(file_path):
            return JSONResponse(status_code=400, content={"error": f"File not found: {file_path}"})
        
        # Check if it's already a WAV file or needs conversion
        suffix = os.path.splitext(file_path)[1].lower()
        
        if suffix == ".wav":
            # Convert to proper format for Whisper (16kHz mono)
            tmp_wav = tempfile.NamedTemporaryFile(delete=False, suffix=".wav").name
            try:
                convert_to_wav(file_path, tmp_wav)
            except subprocess.CalledProcessError:
                return JSONResponse(status_code=400, content={"error": "ffmpeg conversion failed"})
            
            wav_to_transcribe = tmp_wav
        else:
            # Convert from other format
            tmp_wav = tempfile.NamedTemporaryFile(delete=False, suffix=".wav").name
            try:
                convert_to_wav(file_path, tmp_wav)
            except subprocess.CalledProcessError:
                return JSONResponse(status_code=400, content={"error": "ffmpeg conversion failed"})
            
            wav_to_transcribe = tmp_wav
        
        loop = asyncio.get_running_loop()
        text = await loop.run_in_executor(_executor, _transcribe_file, wav_to_transcribe)
        
        # Cleanup
        try:
            os.unlink(wav_to_transcribe)
        except Exception:
            pass
        
        return {"text": text}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})
