"""Core agent: activation detection, Minerva RAG, Claude reasoning, TTS."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

from anthropic import AsyncAnthropic
from openai import AsyncOpenAI

from config import settings

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Transcript state
# ---------------------------------------------------------------------------


@dataclass
class TranscriptEntry:
    speaker: str
    text: str
    ts: float


@dataclass
class MeetingState:
    transcript: list[TranscriptEntry] = field(default_factory=list)
    is_responding: bool = False

    def add(self, speaker: str, text: str, ts: float) -> None:
        self.transcript.append(TranscriptEntry(speaker, text, ts))

    def recent(self, n: int = 30) -> str:
        return "\n".join(f"[{e.speaker}]: {e.text}" for e in self.transcript[-n:])


# ---------------------------------------------------------------------------
# Activation detection
# ---------------------------------------------------------------------------


def is_addressed(text: str) -> bool:
    """Check if someone is talking to Clawdius."""
    lower = text.lower()
    return any(kw in lower for kw in settings.activation_words)


# ---------------------------------------------------------------------------
# Minerva RAG
# ---------------------------------------------------------------------------

_PERSONA_DIR = Path(__file__).resolve().parent.parent / "personas" / "clawdius"


def _load_persona() -> str:
    """Load the Clawdius persona prompt from personas/clawdius/."""
    readme = _PERSONA_DIR / "README.md"
    if readme.exists():
        return readme.read_text()
    return _DEFAULT_PERSONA


_DEFAULT_PERSONA = """\
You are Clawdius, a senior backend engineer who built the Minerva platform.
Minerva is a data enrichment and entity resolution API built with Python/FastAPI.

Key components:
- Resolver: entity resolution pipeline
- Enrichment: data enrichment from multiple sources
- API layer: FastAPI endpoints
- Infrastructure: GCP, OpenSearch, Terraform-managed

Answer technical questions precisely. Reference specific modules and patterns.
You're speaking in a meeting — be concise (2-4 sentences). Technical accuracy
matters more than politeness."""


async def get_system_prompt() -> str:
    """Build the full system prompt with persona + any knowledge files."""
    persona = _load_persona()

    # Append any extra knowledge files in the persona directory
    knowledge_parts = [persona]
    if _PERSONA_DIR.exists():
        for f in sorted(_PERSONA_DIR.glob("*.md")):
            if f.name == "README.md":
                continue
            knowledge_parts.append(f"\n---\n# {f.stem}\n{f.read_text()}")

    return "\n".join(knowledge_parts)


# ---------------------------------------------------------------------------
# LLM clients
# ---------------------------------------------------------------------------

_anthropic: AsyncAnthropic | None = None
_openai: AsyncOpenAI | None = None


def _get_anthropic() -> AsyncAnthropic:
    global _anthropic
    if _anthropic is None:
        _anthropic = AsyncAnthropic(api_key=settings.anthropic_api_key)
    return _anthropic


def _get_openai() -> AsyncOpenAI:
    global _openai
    if _openai is None:
        _openai = AsyncOpenAI(api_key=settings.openai_api_key)
    return _openai


# ---------------------------------------------------------------------------
# Generate response
# ---------------------------------------------------------------------------


async def generate_response(state: MeetingState, trigger_text: str) -> str:
    """Ask Claude to answer a meeting question with Minerva context."""
    system = await get_system_prompt()
    transcript = state.recent()

    msg = await _get_anthropic().messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=400,
        system=system,
        messages=[
            {
                "role": "user",
                "content": (
                    f"Meeting transcript (recent):\n{transcript}\n\n"
                    f"Someone just said: {trigger_text}\n\n"
                    "Respond as if speaking in the meeting. 2-4 sentences max. "
                    "Be direct and technical."
                ),
            }
        ],
    )
    return msg.content[0].text


# ---------------------------------------------------------------------------
# TTS
# ---------------------------------------------------------------------------


async def text_to_speech(text: str) -> bytes:
    """Convert text → MP3 audio bytes via OpenAI TTS."""
    resp = await _get_openai().audio.speech.create(
        model="tts-1",
        voice="onyx",
        input=text,
        response_format="mp3",
    )
    return resp.content
