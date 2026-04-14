"""WebSocket server — bridges the agent page ↔ backend agent logic."""

from __future__ import annotations

import asyncio
import base64
import json
import logging

import websockets
from websockets.asyncio.server import ServerConnection

from agent import MeetingState, generate_response, is_addressed, text_to_speech
from config import settings

log = logging.getLogger(__name__)

# Active sessions keyed by connection
sessions: dict[int, MeetingState] = {}


async def handle_connection(ws: ServerConnection) -> None:
    """Handle one agent-page WebSocket connection.

    Protocol:
        Page → Server:
            {"type": "init"}
            {"type": "transcript", "speaker": "...", "text": "...", "ts": 0.0}
            <binary>  — raw 16 kHz int16 PCM audio chunks

        Server → Page:
            {"type": "status", "state": "listening|thinking|speaking"}
            {"type": "audio", "data": "<base64 MP3>", "text": "..."}
    """
    conn_id = id(ws)
    state = MeetingState()
    sessions[conn_id] = state
    log.info("Agent page connected (%s)", conn_id)

    try:
        async for raw in ws:
            # Binary frames = raw PCM audio (for future streaming STT)
            if isinstance(raw, bytes):
                # TODO: accumulate and send to Whisper for real-time transcription
                # For MVP we rely on Recall's transcript WebSocket
                continue

            msg = json.loads(raw)
            msg_type = msg.get("type")

            if msg_type == "init":
                await ws.send(json.dumps({"type": "status", "state": "listening"}))

            elif msg_type == "transcript":
                speaker = msg.get("speaker", "Unknown")
                text = msg.get("text", "")
                ts = msg.get("ts", 0.0)

                state.add(speaker, text, ts)
                log.info("[%s]: %s", speaker, text)

                if is_addressed(text) and not state.is_responding:
                    state.is_responding = True
                    try:
                        await _respond(ws, state, text)
                    finally:
                        state.is_responding = False

    except websockets.exceptions.ConnectionClosed:
        log.info("Agent page disconnected (%s)", conn_id)
    finally:
        sessions.pop(conn_id, None)


async def _respond(ws: ServerConnection, state: MeetingState, question: str) -> None:
    """Generate and send a spoken response."""
    try:
        await ws.send(json.dumps({"type": "status", "state": "thinking"}))

        response_text = await generate_response(state, question)
        log.info("Response: %s", response_text)

        await ws.send(json.dumps({"type": "status", "state": "speaking"}))

        audio_bytes = await text_to_speech(response_text)

        await ws.send(json.dumps({
            "type": "audio",
            "data": base64.b64encode(audio_bytes).decode(),
            "text": response_text,
        }))

        # Log our own response in the transcript
        state.add(settings.bot_name, response_text, 0.0)

    except Exception:
        log.exception("Error generating response")
        await ws.send(json.dumps({"type": "status", "state": "listening"}))


async def start_ws_server() -> None:
    """Start the WebSocket server for agent page connections."""
    log.info("WebSocket server on port %s", settings.ws_port)
    async with websockets.serve(handle_connection, "0.0.0.0", settings.ws_port):
        await asyncio.Future()
