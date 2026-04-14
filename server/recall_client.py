"""Recall.ai API client — bot lifecycle management."""

from __future__ import annotations

import logging

import httpx

from config import settings

log = logging.getLogger(__name__)


class RecallClient:
    """Thin wrapper around Recall.ai's REST API."""

    def __init__(self) -> None:
        self.base = settings.recall_base_url
        self.headers = {
            "Authorization": f"Token {settings.recall_api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    # ------------------------------------------------------------------
    # Bot lifecycle
    # ------------------------------------------------------------------

    async def create_bot(self, meeting_url: str, ws_backend_url: str) -> dict:
        """Send a bot to join a meeting.

        The bot loads the agent page, which connects back to *ws_backend_url*
        for audio streaming and transcript forwarding.
        """
        # Agent page URL with the backend WS address baked in
        page_url = f"{settings.agent_page_url}?ws={ws_backend_url}"

        payload = {
            "meeting_url": meeting_url,
            "bot_name": settings.bot_name,
            "output_media": {
                "camera": {
                    "kind": "webpage",
                    "config": {"url": page_url},
                }
            },
            "variant": {
                "zoom": "web_4_core",
                "google_meet": "web_4_core",
                "microsoft_teams": "web_4_core",
            },
            "transcription_options": {"provider": "default"},
        }

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.base}/api/v1/bot/",
                headers=self.headers,
                json=payload,
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
            log.info("Bot created: %s", data.get("id"))
            return data

    async def get_bot(self, bot_id: str) -> dict:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self.base}/api/v1/bot/{bot_id}/",
                headers=self.headers,
                timeout=15,
            )
            resp.raise_for_status()
            return resp.json()

    async def remove_bot(self, bot_id: str) -> None:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.base}/api/v1/bot/{bot_id}/leave_call/",
                headers=self.headers,
                timeout=15,
            )
            resp.raise_for_status()
            log.info("Bot %s leaving", bot_id)


recall = RecallClient()
