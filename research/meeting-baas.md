# Meeting BaaS — Speaking Bots API Research

**Date:** 2026-04-14
**Sources:** docs.meetingbaas.com, GitHub repo, OpenAPI spec, source code

---

## 1. Architecture

### How It Works

The Speaking Bots system is a **two-layer WebSocket bridge**:

1. **MeetingBaaS platform** joins a meeting (Google Meet, Zoom, Teams) as a participant via their proprietary bot infrastructure.
2. MeetingBaaS connects back to **your WebSocket server** at `/ws/{client_id}`, streaming raw meeting audio to you and accepting audio back.
3. Your server runs **Pipecat** as a subprocess, which connects to a second internal WebSocket at `/pipecat/{client_id}`.
4. A **message router** bridges between the two WebSockets — converting between MeetingBaaS's raw audio format and Pipecat's Protobuf frame format.

```
Meeting Platform (Zoom/Meet/Teams)
    ↕ (proprietary)
MeetingBaaS Cloud Bot
    ↕ WebSocket /ws/{client_id}  [raw PCM bytes]
Your Speaking Bot Server (FastAPI)
    ↕ WebSocket /pipecat/{client_id}  [Protobuf frames]
Pipecat Pipeline (subprocess)
    ↕
STT → LLM → TTS services
```

### Audio Format

- **Raw PCM**, 16-bit signed integers (paInt16), mono
- **Input sample rate:** 16kHz (hardcoded in routes.py: `streaming_audio_frequency = "16khz"`)
- **Output sample rate:** Pipecat typically uses 24kHz for TTS output; a converter bridges the rates
- Selectable quality noted in docs (16/24kHz) but current code hardcodes 16kHz for the MeetingBaaS ↔ server link
- Audio is serialized via **Protocol Buffers** (frames.proto defines `AudioRawFrame` with sample_rate and num_channels)

### Latency

Not explicitly documented. Depends on:
- MeetingBaaS → your server WebSocket hop
- STT latency (Deepgram/Gladia)
- LLM inference time (OpenAI GPT-4)
- TTS latency (Cartesia)
- Typical end-to-end for Pipecat voice pipelines: **~1-3 seconds** depending on LLM

---

## 2. API Surface

### Base URL
- **Production:** `https://speaking.meetingbaas.com`
- **Self-hosted:** `http://localhost:8766` (or your domain)

### Authentication
Header: `x-meeting-baas-api-key: <your-key>`

### Endpoints

#### POST /bots — Deploy a speaking bot

```json
// Request
{
  "meeting_url": "https://meet.google.com/abc-defg-hij",  // REQUIRED
  "bot_name": "Meeting Assistant",
  "personas": ["helpful_assistant", "meeting_facilitator"],
  "bot_image": "https://example.com/bot-avatar.png",
  "entry_message": "Hello! I'm here to assist with the meeting.",
  "enable_tools": true,
  "prompt": "You are a concise professional AI bot...",  // Custom prompt (overrides persona)
  "extra": {
    "company": "ACME Corp",
    "meeting_purpose": "Weekly sync"
  }
}

// Response (201)
{
  "bot_id": "abc123-meetingbaas-bot-id"
}
```

**Logic:** If `prompt` is provided, it dynamically creates a temporary persona (extracts name, description, gender, characteristics via LLM). Otherwise selects from `personas` list, falls back to `bot_name`, then random, then `baas_onboarder`.

#### DELETE /bots/{bot_id} — Remove bot from meeting

```bash
curl -X DELETE "https://speaking.meetingbaas.com/bots/{bot_id}" \
  -H "x-meeting-baas-api-key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{"bot_id": "optional-override"}'
```

Terminates MeetingBaaS bot, closes WebSocket, kills Pipecat subprocess.

#### POST /personas/generate-image — Generate persona avatar

```json
// Request
{
  "name": "Dr. Smith",
  "description": "A friendly quantum physicist",
  "gender": "female",
  "characteristics": ["glasses", "lab coat"]
}

// Response (201)
{
  "name": "Dr. Smith",
  "image_url": "https://...",
  "generated_at": "2026-04-14T12:00:00Z"
}
```

#### GET /health — Health check

#### WebSocket Endpoints (internal)
- `/ws/{client_id}` — MeetingBaaS connects here (raw audio bytes)
- `/pipecat/{client_id}` — Pipecat subprocess connects here (Protobuf frames)

---

## 3. Persona System

### Structure

Each persona is a directory under `config/personas/`:

```
config/personas/
├── helpful_assistant/
│   ├── README.md          # Main personality prompt + metadata
│   └── (additional .md)   # Extra knowledge, behavior rules
├── interviewer/
│   ├── README.md
│   └── ...
└── baas_onboarder/
    └── README.md
```

### What You Can Customize

| Feature | How |
|---------|-----|
| **System prompt** | `README.md` in persona directory (Markdown) |
| **Knowledge base** | Additional `.md` files in persona dir (websites scraped to MD, docs, etc.) |
| **Voice** | Cartesia voice ID (`cartesia_voice_id` in persona metadata). Auto-matched via LLM if not specified. |
| **Avatar image** | Pre-set or auto-generated via Replicate AI |
| **Entry message** | Set per-persona or per-request |
| **Language** | Configurable per persona |
| **Tools** | Enable/disable function calling (weather, time, etc.) per request |
| **Bot name** | Per-request override |

### Dynamic Personas via Prompt

If you pass `prompt` in the API request instead of selecting a predefined persona, the system:
1. Sends your prompt to OpenAI to extract: name, description, gender, characteristics
2. Auto-matches a Cartesia voice
3. Auto-generates an avatar via Replicate
4. Creates a temporary in-memory persona

### Built-in Personas (70+)

Everything from `interviewer`, `pair_programmer`, `level10_meeting_facilitator` to creative ones like `cyberpunk_grandma`, `kgb_ballerina`, `medieval_crypto_trader`. Full list at `config/personas/`.

### When to Speak

Controlled by Pipecat's **Voice Activity Detection (VAD)** with configurable parameters. The bot listens, detects when humans stop talking, then responds. No explicit "push to talk" — it's conversational.

---

## 4. Pipecat Integration

### How It Works

The speaking-meeting-bot is a **Pipecat application** running as a subprocess. The FastAPI server is just the orchestrator — Pipecat does all the AI work:

```python
# Pipeline: Transport → STT → LLM → TTS → Transport
Pipecat Pipeline:
  WebSocket Transport (receives audio)
  → Deepgram/Gladia STT
  → OpenAI GPT-4 LLM
  → Cartesia TTS
  → WebSocket Transport (sends audio back)
```

### Can You Bring Your Own LLM?

**Yes.** The README explicitly states:

> "For speech-related services (TTS/STT) and LLM choice (like Claude, GPT-4, etc), you can freely choose and swap between any of the integrations available in Pipecat's supported services."

Pipecat supports:
- **LLMs:** OpenAI, Anthropic (Claude), Google Gemini, Azure OpenAI, Fireworks, Together, Groq, NVIDIA NIM, Cerebras, and more
- **TTS:** Cartesia, ElevenLabs, PlayHT, Deepgram, Azure, Google, LMNT, XTTS, and more
- **STT:** Deepgram, Gladia, Whisper, Azure, Google, AssemblyAI, and more

**Caveat:** OpenAI GPT-4 is currently hardcoded for the **CLI-based persona generation** features (matching voices, generating avatars, creating descriptions). But for in-meeting conversation, you can swap the LLM by modifying the Pipecat pipeline config. This requires code changes to the pipeline setup — it's not a runtime API parameter.

### What Pipecat Provides

- Real-time audio processing pipeline
- WebSocket communication (FastAPIWebsocketTransport)
- Voice Activity Detection (VAD)
- Message context management
- Frame-based architecture (AudioRawFrame, TextFrame, TranscriptionFrame via Protobuf)
- Interrupt handling (bot stops talking when human starts)

---

## 5. Pricing

### MeetingBaaS Platform (Token-Based)

The Speaking Bots API uses MeetingBaaS's standard token system. Tokens are consumed for the meeting bot infrastructure (joining, recording, streaming).

| Token Pack | Price/Token | Tokens |
|------------|-------------|--------|
| Starter (Boost) | $0.50 | 100 ($50) |
| Pro (Growth) | $0.45 | — |
| Business (Power) | $0.40 | — |
| Enterprise (Infinity) | $0.35 | 4,250 ($1,500) |

**Usage costs:**
- Recording: 1 token/hour
- Transcription (Gladia): +0.25 token/hour
- Streaming (audio in/out): +0.10 token/hour per stream

**Effective cost:** ~$0.44–0.63/hour ($0.007–0.011/minute) depending on tier.

### Subscription Tiers

| Tier | Monthly | Bots/Day | Concurrent |
|------|---------|----------|------------|
| Pay as You Go | $0 | 75 | 5 |
| Pro | $99 | 300 | — |
| Scale | $199 | 1,000 | 20 |
| Enterprise | $299 | 3,000 | 200 |

### Additional Costs (External Services)

On top of MeetingBaaS tokens, you pay separately for:
- **OpenAI API** (GPT-4 for conversation)
- **Cartesia** (TTS)
- **Deepgram or Gladia** (STT)
- **Replicate** (avatar generation, optional)
- **UploadThing** (image hosting, optional)

---

## 6. Open Source Analysis

### Repository: [Meeting-Baas/speaking-meeting-bot](https://github.com/Meeting-Baas/speaking-meeting-bot)

**License:** Open source (appears to be MIT based on repo description "open source API")

### What's in the Repo

```
speaking-meeting-bot/
├── app/
│   ├── main.py           # FastAPI app setup
│   ├── routes.py         # /bots POST/DELETE, /personas/generate-image
│   ├── websockets.py     # WebSocket bridge (/ws/{id}, /pipecat/{id})
│   ├── models.py         # Pydantic request/response models
│   └── services/         # Image generation, persona detail extraction
├── config/
│   ├── personas/         # 70+ persona definitions (Markdown)
│   ├── persona_utils.py  # Persona loading/management
│   ├── voice_utils.py    # Cartesia voice matching
│   └── prompts.py        # System prompts, interaction instructions
├── core/
│   ├── connection.py     # Registry, in-memory state
│   ├── process.py        # Pipecat subprocess management
│   ├── router.py         # Message routing between WebSockets
│   └── converter.py      # Audio sample rate conversion
├── scripts/
│   ├── meetingbaas_api.py  # MeetingBaaS REST API client
│   └── batch.py            # CLI for batch bot deployment
├── protobufs/
│   └── frames.proto      # Protobuf definitions for audio/text frames
├── meetingbaas_pipecat/  # Pipecat pipeline configuration
├── Dockerfile
└── fly.toml              # fly.io deployment config
```

### What's Reusable vs. Platform-Locked

| Component | Reusable? | Notes |
|-----------|-----------|-------|
| Pipecat pipeline setup | ✅ Fully | Standard Pipecat — works without MeetingBaaS |
| Persona system (Markdown-based) | ✅ Fully | Just a directory of .md files |
| WebSocket bridge architecture | ✅ Mostly | Pattern is reusable; specifics tied to MeetingBaaS protocol |
| Voice matching (Cartesia) | ✅ Fully | Independent utility |
| Audio converter | ✅ Fully | PCM sample rate conversion |
| Protobuf frame definitions | ✅ Fully | Standard Pipecat frames |
| `scripts/meetingbaas_api.py` | ❌ Locked | MeetingBaaS REST API client |
| Bot join/leave via MeetingBaaS | ❌ Locked | Core dependency on MeetingBaaS for meeting connectivity |
| Image generation (Replicate) | ✅ Fully | Optional, independent service |

**Bottom line:** The **meeting connectivity** (actually joining Zoom/Meet/Teams as a participant) is the part locked to MeetingBaaS. Everything else — the AI pipeline, persona system, audio processing — is standard Pipecat and fully portable.

---

## 7. Limitations & Gotchas

### Platform Restrictions
- **Supported platforms:** Google Meet, Zoom, Microsoft Teams only
- **Bot admission:** Bot joins as a participant — requires being "let in" by a host in platforms with waiting rooms
- **Rate limits:** 75 bots/day on free tier, 5 concurrent max
- **Local dev:** Limited to 2 concurrent bots (ngrok free tier constraint)

### Technical Gotchas
- **Audio frequency hardcoded:** Current code forces `streaming_audio_frequency = "16khz"` despite docs suggesting 16/24kHz selectability
- **LLM locked to OpenAI for persona generation:** CLI persona creation, voice matching, and avatar generation all hardcoded to OpenAI. In-meeting LLM is swappable but requires code changes.
- **WebSocket race condition:** MeetingBaaS bots may join meeting before your local Pipecat process connects, causing missed initial audio. Workaround: respawn the bot.
- **No transcript API on speaking bots:** The speaking bot server doesn't expose transcripts via API — transcripts flow through the Pipecat pipeline internally but aren't persisted/returned by default.
- **No real-time control API:** Once a bot joins, you can't change its behavior (e.g., update prompt, mute, change persona) without removing and re-creating it.
- **Subprocess model:** Each bot spawns a separate Pipecat Python subprocess. Memory/CPU scales linearly per bot.
- **ngrok dependency for local dev:** Required for MeetingBaaS to reach your WebSocket server.

### Missing Features (Noted as "Planned" in Repo)
- Authentication/authorization
- Rate limiting (server-side)
- Billing integration
- Real-time bot control
- Live transcription streaming (external)
- Meeting recording/analytics
- Dynamic persona updates via API

---

## 8. Self-Hosting

### Can You Self-Host?

**Yes — the speaking bot server is fully self-hostable.** The repo includes:
- `Dockerfile` for containerized deployment
- `fly.toml` for [fly.io](https://fly.io) deployment
- Poetry-based local development

### What You Self-Host vs. What's SaaS

| Layer | Self-Hosted? | Notes |
|-------|-------------|-------|
| Speaking Bot Server (FastAPI + Pipecat) | ✅ Yes | Your code, your infra |
| MeetingBaaS Meeting Connectivity | ❌ No | SaaS-only — this is their core product |
| OpenAI / Cartesia / Deepgram / Gladia | ❌ No | Third-party SaaS APIs |

### Self-Hosting Setup

```bash
# Clone
git clone https://github.com/Meeting-Baas/speaking-meeting-bot.git
cd speaking-meeting-bot

# Install
poetry env use python3.11
poetry install

# Configure
cp env.example .env
# Set: MEETING_BAAS_API_KEY, OPENAI_API_KEY, CARTESIA_API_KEY, DEEPGRAM_API_KEY
# Set: BASE_URL=https://your-public-domain.com

# Run
poetry run uvicorn app:app --host 0.0.0.0 --port 8766
```

**Requirements:**
- Public URL reachable by MeetingBaaS (they connect TO your WebSocket)
- Python 3.11+
- LLVM, grpc_tools, Cython (for scientific libs and protobuf)

### Can You Skip MeetingBaaS Entirely?

**Theoretically possible but impractical.** MeetingBaaS handles the hard part — being a virtual meeting participant with audio I/O on Zoom/Meet/Teams. To replicate this you'd need:
- Browser automation (headless Chrome joining meetings)
- Platform-specific audio capture/injection
- Handling meeting admission, participant management, etc.

This is exactly what MeetingBaaS (and competitors like Recall.ai) sell. The speaking bot repo is just the AI layer on top.

---

## Summary Assessment

| Aspect | Rating | Notes |
|--------|--------|-------|
| **API simplicity** | ⭐⭐⭐⭐ | Dead simple — one POST to deploy a bot |
| **Customizability** | ⭐⭐⭐⭐ | Persona system is flexible; LLM/TTS/STT swappable with code changes |
| **Documentation** | ⭐⭐⭐ | Decent but gaps (latency numbers, advanced config, transcript access) |
| **Open source quality** | ⭐⭐⭐⭐ | Clean FastAPI code, well-structured, Pydantic models |
| **Vendor lock-in** | ⭐⭐ | Meeting connectivity locked to MeetingBaaS; AI layer is portable |
| **Cost** | ⭐⭐⭐ | MeetingBaaS tokens + subscription + 3-4 external API costs adds up |
| **Production readiness** | ⭐⭐ | Missing auth, rate limiting, persistence, monitoring |
| **Scalability** | ⭐⭐ | Subprocess-per-bot model; no shared inference or connection pooling |
