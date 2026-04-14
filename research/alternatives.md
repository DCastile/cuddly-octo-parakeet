# Alternative Approaches: AI Voice Agent in Zoom Meetings

Research compiled 2026-04-14.

---

## Summary Matrix

| Approach | Maturity | Listen + Speak | Self-Hostable | Effort | Best For |
|---|---|---|---|---|---|
| **Zoom Meeting SDK** | Production | ✅ Both | ✅ (Linux/Docker) | High (weeks+) | Full native control, no intermediary |
| **Pipecat Standalone** | N/A | ❌ No Zoom transport | ✅ | N/A | Not viable alone for Zoom |
| **Daily.co + Pipecat** | Production | ✅ Both (via SIP) | Partial (bot self-hosted, Daily is SaaS) | Medium | Fastest path to bidirectional audio in Zoom |
| **Bland AI** | Production (phone only) | ❌ Phone only | Partial (enterprise self-host) | N/A | Not viable for Zoom meetings |
| **Ultravox** | Production (phone only) | ❌ Phone only | ❌ SaaS | N/A | Not viable for Zoom meetings |
| **Vapi** | Production (phone only) | ❌ Phone only | ❌ SaaS | N/A | Not viable for Zoom meetings |
| **ScreenApp OSS Bot** | Alpha | ❌ Record only | ✅ | N/A | Recording/transcription only |
| **Zoom AI Companion + A2A** | Early (2025) | ⚠️ Workflow only | ❌ Zoom-controlled | Low (if it fits) | Scheduling/task automation, not real-time voice |

---

## 1. Zoom Meeting SDK (Direct)

**What it is:** Zoom's official SDK for building bots that programmatically join Zoom meetings, with raw audio/video stream access. Runs headless on Linux/Docker.

**SDK Options:**
- **Meeting SDK** — Primary. Bot joins standard Zoom meetings. Raw PCM audio in/out per participant. Python bindings via [`py-zoom-meeting-sdk`](https://github.com/noah-duncan/py-zoom-meeting-sdk) (beta, actively maintained). Node.js via RTMS SDK (v1.0, launched 2024).
- **Video SDK** — For custom video experiences (not standard Zoom meetings). Has `sendAudioRawData()` for TTS output. Better documented for voice agent patterns.
- **RTMS SDK** — Lighter-weight: live audio/video/transcript callbacks. Official Node/Python. Good for listen-only or transcript-based bots.

**Voice Agent Flow:**
1. Create "General App" on Zoom Developer Platform → get Client ID/Secret
2. Bot joins meeting via meeting ID/password (headless, Linux/Docker)
3. Raw PCM audio piped to STT (e.g., Deepgram)
4. LLM processes transcript → generates response
5. TTS → PCM injected back via SDK audio send methods

**Approval Process:**
- Apps joining meetings on **external accounts** (outside your own Zoom org) require **Zoom Marketplace review**
- No fixed timeline — reports of weeks-long iterative review cycles with incremental feedback
- As of March 2026, On Behalf Of (OBF) tokens required for cross-account access
- Internal-only bots (same Zoom account) can skip marketplace review
- Common pain point: requirements revealed incrementally, causing resubmissions

**Assessment:**
- **Maturity:** Production. Powers Gong, Otter.ai, etc.
- **Listen + Speak:** ✅ Full bidirectional raw audio
- **Self-hostable:** ✅ Linux/Docker, your infrastructure
- **Effort:** **High.** Python bindings are beta. Approval process is slow and opaque for cross-account use. You own all the infra: audio pipeline, STT/TTS integration, participant management, error handling.
- **Key risk:** Marketplace approval can block you for weeks. The Python SDK is community-maintained.

---

## 2. Pipecat Standalone (No Meeting BaaS)

**What it is:** Open-source Python framework by Daily for building real-time voice/video AI agents. Modular pipeline: VAD → STT → LLM → TTS → transport.

**Supported Transports:**
- `DailyTransport` (primary, WebRTC via Daily.co)
- `SmallWebRTCTransport` (generic WebRTC)
- `FastAPIWebSocketTransport`
- `LiveKitTransport`
- `HeyGenTransport`
- Twilio (telephony)

**Zoom Support: ❌ None.** No Zoom transport exists. No plans mentioned in docs or GitHub issues as of early 2026. You cannot point Pipecat at a Zoom meeting URL and have it join.

**Could you build one?** Theoretically you could write a custom Pipecat transport wrapping the Zoom Meeting SDK, but that's essentially doing Option 1 with extra abstraction. The SDK's raw audio API doesn't map cleanly to Pipecat's WebRTC-oriented transport interface.

**Assessment:**
- Not viable as a standalone path to Zoom
- Excellent framework if paired with a bridge (see Option 3)

---

## 3. Daily.co + Pipecat (SIP Bridge into Zoom)

**What it is:** Use Daily as the WebRTC room where your Pipecat bot runs, then bridge into Zoom via SIP dial-out. The bot "lives" in a Daily room and Daily handles the Zoom connection.

**How it works:**
1. Create a Daily room with SIP enabled (`sip_mode: "dial-in"`)
2. Pipecat bot joins Daily room via `DailyTransport`
3. Use `startDialOut()` to SIP dial-out to Zoom's meeting SIP URI: `[MeetingID].[Password]@zoomcrc.com`
4. Bot appears as a phone participant in the Zoom meeting
5. Full bidirectional audio: bot hears meeting audio, meeting hears bot's TTS output

**Pipecat + Daily SIP example flow:**
```python
from pipecat.transports.daily import DailyTransport, DailyParams

transport = DailyTransport(room_url, token, "Voice Bot", DailyParams(
    audio_in_enabled=True,
    audio_out_enabled=True,
    video_out_enabled=False
))

# On ready, dial out to Zoom via SIP
await transport.start_dialout({"sipUri": "sip:12345678.abc123@zoomcrc.com"})
```

**Requirements:**
- Daily paid account (credit card on file)
- SIP features enabled on the Daily room
- Default 5 SIP sessions per room (can request increase)
- Zoom meeting must allow SIP/H.323 dial-in (most Zoom accounts support this)
- Supported codecs: PCMU/PCMA, G722, Opus

**Limitations:**
- Bot joins as a **phone participant** (audio only, no video, no screen share)
- No per-participant audio separation (you get mixed audio)
- Depends on Daily.co SaaS for the SIP bridge — not fully self-hostable
- Small latency overhead from the SIP bridge

**Assessment:**
- **Maturity:** Production. Daily's SIP infra is battle-tested. Pipecat is actively maintained.
- **Listen + Speak:** ✅ Full bidirectional
- **Self-hostable:** Partial. Bot code is yours, but Daily.co is the SIP/WebRTC layer (SaaS).
- **Effort:** **Medium.** ~1-2 weeks for a working prototype. Well-documented. No Zoom marketplace approval needed (you're dialing in as a phone participant, not using the SDK).
- **Key advantage:** Bypasses Zoom's SDK approval entirely. You just SIP-dial into the meeting like a conference phone.

---

## 4. Bland AI

**What it is:** Conversational AI platform for automating phone calls (inbound/outbound).

**Zoom Support: ❌ None.** Bland AI is exclusively telephony-based. No Zoom meeting integration, no video platform support, no SIP dial-out to meetings. They optimize for PSTN voice calls with features like voice cloning, conversational pathways, CRM integration.

**Could you hack it?** You could theoretically have Bland call the Zoom meeting's phone dial-in number, but you'd have no control over the bot's behavior in the meeting context, and Bland doesn't expose the raw audio pipeline needed for custom agent logic.

**Assessment:** Not viable for Zoom meetings.

---

## 5. Ultravox / Vapi

### Ultravox
- Real-time voice AI infrastructure with Twilio/Plivo telephony support
- **No Zoom meeting support.** Focus is entirely on phone-based voice experiences.
- SaaS-only, no self-hosting option

### Vapi
- Voice AI agent platform, primarily phone operations
- **No Zoom meeting support.** Users have attempted Zoom Phone integration via SIP trunks but found no straightforward path (per Zoom dev forum posts).
- SaaS-only

**Assessment:** Neither is viable for Zoom meetings. Both are phone-call-only platforms.

---

## 6. ScreenApp Open Source Meeting Bot

**Repo:** [github.com/screenappai/meeting-bot](https://github.com/screenappai/meeting-bot)

**What it is:** TypeScript/Node.js bot using Playwright (headless browser) to join and record meetings on Zoom, Google Meet, and Teams.

**Capabilities:**
- Joins meetings via browser automation
- Records audio/video with configurable duration
- REST API and Redis queue integration
- Multi-platform support

**Two-Way Audio: ❌ No.** This is a **recording bot only**. It silently joins and captures. There is no mechanism for:
- Injecting audio (speaking)
- Processing audio in real-time
- Interacting with participants

**Could you extend it?** The Playwright approach means you could theoretically inject audio via browser APIs, but this would be fragile, ToS-violating hack territory. Browser-based bots are inherently limited for real-time bidirectional audio.

**Assessment:**
- **Maturity:** Alpha/early. Limited community.
- **Listen + Speak:** ❌ Record only
- **Self-hostable:** ✅ Fully
- **Effort:** N/A — wrong tool for the job
- Useful for recording/transcription, not for interactive voice agents

---

## 7. Zoom AI Companion + A2A Protocol

**What it is:** Zoom's native AI assistant with support for Google's Agent2Agent (A2A) protocol, enabling external AI agents to collaborate with Zoom AI Companion.

**Current State (as of late 2025):**
- A2A integration announced at Google I/O 2025
- Partners: Google Cloud, ServiceNow
- **AI Companion 3.0** (Zoomtopia Sept 2025): Custom AI Companion add-on, low-code builder in Zoom AI Studio
- Supports MCP (Model Context Protocol) for connecting org data sources

**What it actually does:**
- Meeting scheduling automation (detect context in Gmail → schedule Zoom meeting → update calendar)
- Cross-platform agent collaboration (ServiceNow NowAssist running inside Zoom AI Companion)
- Task automation and workflow orchestration

**What it does NOT do:**
- ❌ Real-time voice participation in meetings
- ❌ Custom STT/TTS pipeline control
- ❌ Arbitrary agent joining meetings as a participant
- ❌ Raw audio stream access

**Assessment:**
- **Maturity:** Early. Announced mid-2025, still rolling out.
- **Listen + Speak:** ❌ Not for real-time meeting audio. This is workflow/task automation, not voice agent participation.
- **Self-hostable:** ❌ Zoom-controlled infrastructure
- **Effort:** Low if your use case is scheduling/task automation. Not applicable for a voice agent that joins and talks in meetings.
- **Key insight:** A2A is about agents coordinating tasks (schedule this, create that ticket), not about an AI agent sitting in a Zoom call listening and speaking.

---

## Recommendation

**For an AI voice agent that joins Zoom meetings and both listens and speaks:**

### Best Path: Daily.co + Pipecat (Option 3)
- Fastest to prototype (~1-2 weeks)
- No Zoom marketplace approval needed
- Pipecat handles the full voice pipeline (VAD/STT/LLM/TTS)
- Daily handles the Zoom SIP bridge
- Tradeoff: audio-only (no video), SaaS dependency on Daily

### If you need native Zoom integration: Zoom Meeting SDK (Option 1)
- Full control, native participant experience
- Significant upfront investment: Python SDK is beta, marketplace approval is slow
- Best for production at scale where you need video, per-participant audio, or full meeting control

### Not viable for this use case:
- Pipecat alone (no Zoom transport)
- Bland AI, Ultravox, Vapi (phone-only)
- ScreenApp bot (recording only)
- Zoom A2A (workflow automation, not voice participation)
