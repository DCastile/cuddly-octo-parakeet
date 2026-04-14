"""Clawdius Voice — FastAPI server + WebSocket agent bridge."""

from __future__ import annotations

import asyncio
import logging

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from config import settings
from recall_client import recall
from ws_handler import start_ws_server

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
log = logging.getLogger(__name__)

app = FastAPI(title="Clawdius Voice", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---- In-memory bot registry ----
active_bots: dict[str, dict] = {}


# ---- Models ----


class JoinRequest(BaseModel):
    meeting_url: str
    bot_name: str | None = None
    ws_backend_url: str | None = None  # Override for dev (e.g. ngrok wss URL)


class JoinResponse(BaseModel):
    bot_id: str
    status: str


class LeaveRequest(BaseModel):
    bot_id: str


# ---- Endpoints ----


@app.post("/api/join", response_model=JoinResponse)
async def join_meeting(req: JoinRequest):
    """Send Clawdius to join a meeting."""
    ws_url = req.ws_backend_url or f"ws://localhost:{settings.ws_port}"

    try:
        bot = await recall.create_bot(req.meeting_url, ws_url)
    except Exception as e:
        log.exception("Recall API error")
        raise HTTPException(502, detail=f"Recall.ai error: {e}")

    bot_id = bot["id"]
    active_bots[bot_id] = bot
    return JoinResponse(bot_id=bot_id, status="joining")


@app.post("/api/leave")
async def leave_meeting(req: LeaveRequest):
    """Remove Clawdius from a meeting."""
    try:
        await recall.remove_bot(req.bot_id)
    except Exception as e:
        raise HTTPException(502, detail=str(e))
    active_bots.pop(req.bot_id, None)
    return {"status": "leaving"}


@app.get("/api/status/{bot_id}")
async def bot_status(bot_id: str):
    try:
        return await recall.get_bot(bot_id)
    except Exception as e:
        raise HTTPException(404, detail=str(e))


@app.get("/api/bots")
async def list_bots():
    return {"bots": list(active_bots.values())}


@app.get("/health")
async def health():
    return {"status": "ok"}


# ---- Entrypoint ----


async def main() -> None:
    ws_task = asyncio.create_task(start_ws_server())
    config = uvicorn.Config(app, host="0.0.0.0", port=settings.port, log_level="info")
    server = uvicorn.Server(config)
    await asyncio.gather(server.serve(), ws_task)


if __name__ == "__main__":
    asyncio.run(main())
