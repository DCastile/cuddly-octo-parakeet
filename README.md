# Clawdius Voice

AI voice agent that joins Zoom meetings via [Recall.ai](https://recall.ai) to answer technical questions about the Minerva platform.

## Architecture

```
Recall.ai bot joins Zoom as "Clawdius"
    ↓ renders
Static agent page (page/ — hosted on GitHub Pages)
    ↕ WebSocket
Backend server (server/)
    ├── OpenAI Whisper (STT)
    ├── Claude (reasoning + Minerva context)
    └── OpenAI TTS (voice response)
```

## How it works

1. You send a meeting URL → backend tells Recall.ai to join
2. Recall bot joins Zoom, loads the static agent page
3. Page captures meeting audio via getUserMedia, forwards to backend over WebSocket
4. Backend transcribes (Whisper), detects activation ("Clawdius, how does X work?")
5. Claude generates answer with Minerva codebase context
6. OpenAI TTS converts answer to speech
7. Audio sent back to page → plays through bot into the meeting

## Project structure

```
page/           Static agent page (deployed to GitHub Pages)
server/         Python backend (FastAPI + WebSocket)
personas/       Bot persona definitions
research/       Architecture research notes
```

## Setup

### Prerequisites

- Python 3.11+
- Recall.ai API key
- OpenAI API key (Whisper STT + TTS)
- Anthropic API key (Claude reasoning)

### Environment

```bash
cp .env.example .env
# RECALL_API_KEY=...
# OPENAI_API_KEY=...
# ANTHROPIC_API_KEY=...
```

### Run the backend

```bash
cd server
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python main.py
```

### Deploy the agent page

The page is static HTML/JS. Push to GitHub Pages, Cloudflare Pages, or any static host. For dev, use ngrok:

```bash
cd page
npx serve .    # or python -m http.server 5173
ngrok http 5173
```

### Join a meeting

```bash
curl -X POST http://localhost:8000/api/join \
  -H "Content-Type: application/json" \
  -d '{"meeting_url": "https://zoom.us/j/123456789"}'
```

## License

MIT
