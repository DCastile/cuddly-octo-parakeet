# LiveKit Agents Framework — Research Notes

**Date:** 2026-04-14
**Purpose:** Evaluate LiveKit Agents as a platform for building a voice bot that joins Zoom meetings.

---

## 1. Zoom Integration

### ginjaninja78/agents-zoom-integration

- **It's a stale fork.** Forked from `livekit/agents` on 2024-09-17, never updated since (last push same day as creation). Zero stars, zero meaningful Zoom-specific code — the README is just the stock LiveKit agents README with no Zoom additions. The repo name is aspirational, not functional.
- **Verdict:** Dead end. Not a working Zoom integration.

### Official LiveKit Zoom Support

- **No official Zoom integration exists.** LiveKit has no Zoom-specific plugin, connector, or documentation.
- **SIP dial-in is the workaround.** LiveKit has a SIP server (`livekit/sip`) that can dial into Zoom meetings via Zoom's phone dial-in numbers. A GitHub issue (#2897 on livekit/livekit) documents someone successfully connecting by:
  1. Dialing Zoom's phone number via LiveKit SIP trunk
  2. Sending DTMF tones (`wwww<meetingId>#wwwww*<password>#`) to enter the meeting
- **Limitations of SIP approach:**
  - Audio only (no video, no screen share, no chat)
  - Dependent on Zoom enabling phone dial-in for the meeting
  - DTMF timing can be finicky
  - The agent appears as a phone participant, not a named bot
  - No access to Zoom's participant list, transcription, or metadata

**This is fundamentally different from Meeting BaaS approaches that join as a native Zoom client.**

---

## 2. Agent Framework Architecture

### Core Concepts

| Concept | Description |
|---------|-------------|
| **Agent** | Python/Node.js class with instructions, tools, and behavior |
| **AgentSession** | Container that manages the interaction — holds VAD, STT, LLM, TTS |
| **AgentServer** | Main process that coordinates job scheduling and agent lifecycle |
| **entrypoint** | The handler function invoked when a user connects (like a request handler) |
| **Job** | A dispatched unit of work — one agent instance serving one room |

### STT → LLM → TTS Pipeline

The framework provides a built-in voice pipeline:

1. **VAD (Voice Activity Detection):** Silero VAD detects when the user is speaking
2. **STT:** Converts speech to text (Deepgram, AssemblyAI, Google, etc.)
3. **LLM:** Processes text, generates response (OpenAI, Anthropic, Google, etc.)
4. **TTS:** Converts response text to speech (Cartesia, ElevenLabs, etc.)

Additionally supports **Realtime API** models (OpenAI Realtime, Gemini Live) for direct speech-to-speech without the STT→LLM→TTS decomposition.

### Key Features

- **Semantic turn detection:** Transformer model to detect when user is done speaking (reduces interruptions)
- **Tool/function calling:** Define tools as decorated Python functions, compatible with any LLM
- **Multi-agent handoff:** Chain agents for complex workflows (e.g., triage → specialist)
- **MCP support:** Native Model Context Protocol integration
- **Built-in test framework:** Pytest integration with LLM judges for agent behavior validation

### Code Structure (minimal example)

```python
from livekit.agents import Agent, AgentServer, AgentSession, JobContext, cli, function_tool
from livekit.plugins import silero, deepgram, openai, cartesia

server = AgentServer()

@server.rtc_session()
async def entrypoint(ctx: JobContext):
    session = AgentSession(
        vad=silero.VAD.load(),
        stt=deepgram.STT(model="nova-3"),
        llm=openai.LLM(model="gpt-4.1-mini"),
        tts=cartesia.TTS(model="sonic-3"),
    )
    agent = Agent(
        instructions="You are a helpful assistant.",
        tools=[my_tool],
    )
    await session.start(agent=agent, room=ctx.room)

if __name__ == "__main__":
    cli.run_app(server)
```

---

## 3. Server-Side Audio Model

**Yes, it's pure server-side. No browser needed.**

- The agent runs as a server process that connects to a LiveKit room via WebRTC
- Audio flows: User → LiveKit SFU → Agent process (server-side) → AI pipeline → back through LiveKit SFU → User
- The agent is a "participant" in the LiveKit room, same as any client, but running on a server
- For Zoom specifically via SIP: Zoom ↔ SIP trunk ↔ LiveKit SFU ↔ Agent process
- No headless browser, no webpage rendering — it's a native WebRTC participant
- Has telephony integration for PSTN calls (inbound/outbound via SIP)

---

## 4. LLM Flexibility — Anthropic/Claude Support

**Yes, Claude is officially supported.**

- Plugin: `livekit-plugins-anthropic` (available on PyPI)
- Supports Claude models as the LLM in the voice pipeline
- Usage: `from livekit.plugins.anthropic import LLM; llm = LLM(model="claude-sonnet-4-20250514")`
- Supports: tool calling, parallel tool calls, temperature control
- Also supports Anthropic's Computer Use provider tool
- Requires `ANTHROPIC_API_KEY` environment variable

### Other LLM options via plugins

- OpenAI (GPT-4o, GPT-4.1, Realtime API)
- Google (Gemini, Gemini Live)
- Azure OpenAI
- Cerebras, Fireworks, Groq, Together, Perplexity (via OpenAI-compatible plugin)
- Ollama (local models via OpenAI-compatible API)

**You can mix and match** — e.g., Deepgram STT + Claude LLM + ElevenLabs TTS.

---

## 5. Self-Hosting

**Yes, the entire stack is open source (Apache 2.0).**

| Component | Repo | Purpose |
|-----------|------|---------|
| LiveKit Server | `livekit/livekit` | WebRTC SFU (Go) |
| SIP Server | `livekit/sip` | Telephony gateway |
| Agents SDK | `livekit/agents` | Agent framework (Python) |
| Agents JS | `livekit/agents-js` | Agent framework (Node.js) |
| Egress | `livekit/egress` | Recording/streaming |
| Ingress | `livekit/ingress` | Ingest external streams |

- LiveKit server is "one of the most widely used WebRTC media servers"
- Can run on bare metal, VMs, Docker, Kubernetes
- Agent server has built-in load balancing, graceful shutdown, auto-scaling support
- Self-hosting means you bring your own AI provider API keys (no LiveKit Inference)
- No licensing fees for self-hosted — just your infra + AI API costs

---

## 6. Pricing (LiveKit Cloud)

### Agent Session Minutes

| Plan | Monthly Fee | Included Minutes | Overage |
|------|-------------|-----------------|---------|
| Build (Free) | $0 | 1,000 | $0.01/min |
| Ship | $50 | 5,000 | $0.01/min |
| Scale | $500 | 50,000 | $0.01/min |
| Enterprise | Custom | Custom | Custom |

### Additional Costs (LiveKit Inference — optional managed AI)

- **LLM inference:** $0.0008–$0.019/min depending on model
- **STT:** $0.0023–$0.0075/min (Deepgram, AssemblyAI)
- **TTS:** $0.016–$0.072/min (Cartesia, ElevenLabs)
- **Session recordings:** $0.005/min

### Cost Estimate for Voice Bot (per meeting hour)

Using LiveKit Cloud Ship plan + LiveKit Inference:
- Agent session: $0.60/hr
- STT (Deepgram nova-3): ~$0.14–$0.45/hr
- LLM (GPT-4.1-mini): ~$0.05–$1.13/hr
- TTS (Cartesia): ~$0.97–$1.80/hr
- **Rough total: $1.76–$3.98/hr per active agent session**

Self-hosted eliminates the $0.01/min agent session fee; you only pay AI API costs directly.

---

## 7. Maturity & Production Readiness

### Current State

- **Version:** 1.4.x (Python SDK) — past 1.0, actively maintained
- **Stars:** 5k+ on GitHub
- **Activity:** Very active — regular releases, responsive maintainers
- **Community:** Active Slack community, good docs
- **License:** Apache 2.0

### Production Features

- ✅ Agent server orchestration with job scheduling
- ✅ Load balancing across multiple workers
- ✅ Graceful shutdown (SIGTERM handling)
- ✅ Hot code reloading (dev mode)
- ✅ Kubernetes compatibility
- ✅ Built-in test framework
- ✅ SOC 2 Type II, GDPR, CCPA, HIPAA compliant (Cloud)
- ✅ Managed deployments on LiveKit Cloud

### Caveats

- The framework evolves fast — breaking changes between minor versions have happened (e.g., 0.7→0.8)
- Zoom integration via SIP is a workaround, not a first-class feature
- Node.js SDK is newer/less mature than Python
- Real-world voice quality depends heavily on STT/TTS provider choices and network conditions

---

## 8. LiveKit Agents vs. Meeting BaaS — Key Tradeoffs

| Dimension | LiveKit Agents (via SIP) | Meeting BaaS (Recall.ai, etc.) |
|-----------|-------------------------|-------------------------------|
| **Zoom join method** | SIP dial-in (phone participant) | Native client (named bot participant) |
| **Audio access** | ✅ Full duplex audio | ✅ Full audio streams per speaker |
| **Video/screen share** | ❌ Not via SIP | ✅ Full video and screen capture |
| **Chat/metadata** | ❌ Not via SIP | ✅ Meeting chat, participants, etc. |
| **Bot identity** | Shows as phone number | Shows as named participant |
| **Real-time voice interaction** | ✅ Built-in STT→LLM→TTS pipeline | ❌ Primarily listen-only (transcription) |
| **Multi-platform** | ✅ Any platform with SIP/phone dial-in | ✅ Zoom, Teams, Meet, Webex |
| **Self-hostable** | ✅ Fully open source | ❌ Typically SaaS only |
| **AI pipeline built-in** | ✅ Full voice AI framework | ❌ Raw audio/transcript — BYO pipeline |
| **Latency** | Low (WebRTC optimized) | Varies (depends on BaaS architecture) |
| **Vendor lock-in** | Low (open source, plugin-based) | High (proprietary APIs) |
| **Cost model** | Infra + AI APIs (or LiveKit Cloud) | Per-bot-hour SaaS pricing |
| **Production maturity for meetings** | Medium (SIP workaround) | High (purpose-built for meetings) |

### Bottom Line

- **LiveKit Agents excels** as a voice AI framework — if you're building a conversational agent that needs to talk and listen in real time, the framework is excellent.
- **For Zoom meetings specifically**, LiveKit is a square peg in a round hole. The SIP dial-in approach gives you audio-only access as a phone participant. No video, no screen share, no meeting metadata.
- **Meeting BaaS** gives you native meeting integration (join as a real participant, see everything) but typically no real-time voice interaction capability — it's designed for passive recording/transcription.
- **The gap:** Neither solution natively gives you a bot that joins Zoom as a named participant AND has a full real-time conversational AI pipeline. You'd need to combine approaches (e.g., BaaS for meeting context + your own voice pipeline) or build custom Zoom SDK integration.

---

## Key Sources

- https://docs.livekit.io/agents/
- https://github.com/livekit/agents (v1.4.x, Apache 2.0)
- https://livekit.com/products/agent-platform
- https://livekit.com/pricing
- https://docs.livekit.io/agents/models/llm/anthropic/
- https://github.com/livekit/livekit/issues/2897 (Zoom via SIP discussion)
- https://github.com/ginjaninja78/agents-zoom-integration (stale fork, no actual Zoom code)
