"""
OHE Schematic Editor — Parsing Backend
FastAPI application exposing:
  POST /parse          — sync parse, returns full ParsedDiagram JSON
  WS   /ws/parse       — streaming parse with live progress events
"""

import json
import tempfile
import shutil
from pathlib import Path

from fastapi import FastAPI, UploadFile, File, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware

# Add parent to path when running directly
import sys
sys.path.insert(0, str(Path(__file__).parent))

from models.schema import ParsedDiagram, ParseProgress
from services.pdf_parser import parse_pdf, parse_pdf_streaming

app = FastAPI(
    title="OHE Schematic Parser",
    description="PDF parsing backend for the OHE Schematic Editor",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],           # tighten in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok", "service": "ohe-parser"}


# ── Sync Parse Endpoint ───────────────────────────────────────────────────────

@app.post("/parse", response_model=ParsedDiagram, summary="Parse an OHE diagram PDF")
async def parse_endpoint(file: UploadFile = File(...)):
    """
    Upload a PDF and receive the complete parsed diagram as JSON.
    Suitable for smaller files or non-realtime contexts.
    """
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted.")

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir) / file.filename
        with tmp_path.open("wb") as f:
            shutil.copyfileobj(file.file, f)

        try:
            result = parse_pdf(tmp_path)
        except Exception as e:
            raise HTTPException(status_code=422, detail=f"Parse failed: {e}")

    return result


# ── WebSocket Streaming Parse ─────────────────────────────────────────────────

@app.websocket("/ws/parse")
async def ws_parse(websocket: WebSocket):
    """
    WebSocket endpoint for streaming parse progress.

    Protocol:
      Client → sends raw PDF bytes as binary message
      Server → emits ParseProgress JSON objects as text messages
      Final message has stage='done' or stage='error'
    """
    await websocket.accept()

    try:
        # Receive filename metadata first (as JSON text frame)
        meta_text = await websocket.receive_text()
        meta = json.loads(meta_text)
        filename = meta.get("filename", "upload.pdf")

        # Then receive the binary PDF data
        pdf_bytes = await websocket.receive_bytes()

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir) / filename
            tmp_path.write_bytes(pdf_bytes)

            async for progress in parse_pdf_streaming(tmp_path):
                await websocket.send_text(progress.model_dump_json())

                # If done or error, close cleanly
                if progress.stage in ("done", "error"):
                    break

    except WebSocketDisconnect:
        pass
    except Exception as e:
        error_msg = ParseProgress(
            stage="error",
            message="Unexpected server error",
            error=str(e),
        )
        try:
            await websocket.send_text(error_msg.model_dump_json())
        except Exception:
            pass
    finally:
        try:
            await websocket.close()
        except Exception:
            pass


# ── Dev runner ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
