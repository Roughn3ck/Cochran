# CLC — Cochran Legal Council

**If the glove don't fit, you must acquit.** ⚖️

Real-time legal AI voice pipeline for live phone calls. Listen → Think → Speak. Cochran sits in on live calls — mediation, conciliation, disputes, negotiations — and provides real-time strategic counsel in your ear.

Part of [The Pack](https://github.com/Roughn3ck/ExecutiveMind) at [Executive Mind](https://executivemind.io).

---

## What This Is

A dual-source signal processing pipeline that listens to both sides of a live call, transcribes them with speaker differentiation, generates strategic legal counsel via LLM, and optionally speaks that counsel back into the call.

```
CABLE-A (other party):
  Phone → Webex → Voicemeeter VAIO → B1 → ffmpeg #1 → Whisper → transcript

CABLE-B (client):
  Yealink Mic → Voicemeeter Input 1 → B2 → ffmpeg #2 → Whisper → transcript
                                    → Webex mic (call participants hear client)

Cochran TTS → Voicemeeter AUX → B2 → Webex mic (speaks into call)
```

Two separate audio streams. Two transcription feeds. Speaker-labeled transcripts. The pipeline knows who is speaking.

## Repository Structure

```
CLC/
├── AGENTS.md                  # Architecture, routing, conventions
├── README.md                  # This file
├── STATUS.md                  # Current build status
├── VB-AUDIO-SETUP.md          # Voicemeeter Banana routing guide
├── .gitignore
├── .env.example               # Environment variable template
│
├── windows/                   # Windows-native pipeline
│   ├── cochran_live.py        # Main pipeline (Windows paths, native audio)
│   ├── dashboard_server.py    # HTTP dashboard server (:8765)
│   ├── dashboard.html         # Web dashboard with mode switching
│   ├── stream_to_file.bat     # ffmpeg capture — B1 (other party)
│   ├── stream_to_file_client.bat  # ffmpeg capture — B2 (client)
│   ├── play_to_vbcable.bat    # Play WAV through Voicemeeter AUX Input
│   ├── setup_audio.bat        # Audio routing setup and test
│   ├── case_context.example.py    # Template for case-specific prompts
│   ├── cochran_avatar.jpg
│   ├── cochran_logo.png
│   ├── AGENTS.md
│   ├── README.md
│   ├── STATUS.md
│   └── VB-AUDIO-SETUP.md
│
├── WSL/                       # WSL-bridged pipeline (current working setup)
│   └── (same structure as windows/)
│
├── linux/                     # Pure Linux pipeline (no Windows dependencies)
│   └── (same structure, minus batch files)
│
├── matters/                   # Case context files (shared across environments)
│   ├── test_context.py        # Test/introduction flow (committed)
│   └── case_context.example.py    # Template for real matters (committed)
│
└── transcripts/               # Session transcripts (shared, gitignored)
```

### Environment Folders

Each environment folder contains a copy of the pipeline adapted for that OS:

| Folder | Status | Description |
|--------|--------|-------------|
| `windows/` | 🔧 Planned | Full Windows-native — no WSL bridge, direct audio device access |
| `WSL/` | ✅ Active | Current working setup — WSL pipeline bridging to Windows for audio |
| `linux/` | 🔜 Future | Pure Linux deployment (PulseAudio/PipeWire, no Voicemeeter) |

### Shared Resources

- `matters/` — Case context files referenced by all environments via relative path `../matters/`
- `transcripts/` — Session transcripts written by all environments via relative path `../transcripts/`

### Modes

| Mode | Voice | Description |
|------|-------|-------------|
| `private` | 🤐 Text only | Full strategy, no holds barred |
| `court` | ⚖️ Speaks via CABLE-B | Careful, on the record |
| `default` | 🎙️ Speaks via CABLE-B | No restrictions |
| `commander` | 📞 Speaks via CABLE-B | Professional business calls |
| `mute` | 🔇 No LLM | Transcription only |

Mode switching is live via the dashboard — no restart needed.

### TTS Voices

| Engine | Voice | Latency | Use Case |
|--------|-------|---------|----------|
| **Chatterbox** | Cochran voice clone | ~10-30s | Primary — authentic Cochran voice |
| **Kokoro** | am_michael (male) | ~1s | Fallback — fast, generic male voice |

## Quick Start (WSL)

```bash
# 1. Windows: Configure Voicemeeter Banana (see VB-AUDIO-SETUP.md)
# 2. Windows: Set default playback to Voicemeeter AUX Input
# 3. Windows: Start both audio captures
stream_to_file.bat           # B1 — other party
stream_to_file_client.bat    # B2 — client

# 4. WSL: Start dashboard server
cd CLC/WSL
python3 dashboard_server.py

# 5. WSL: Start pipeline
python3 cochran_live.py --matter test

# 6. Browser: Open dashboard
http://localhost:8765
```

## Dependencies

- **faster-whisper** (CUDA, large-v3-turbo) — speech to text
- **Ollama** (localhost:11434) — LLM inference (deepseek-v4-flash:cloud)
- **Kokoro TTS** — fast fallback voice (in-memory KPipeline)
- **Chatterbox TTS** — voice cloning with Cochran reference WAV
- **VB-Audio Voicemeeter Banana** — two virtual outputs (B1, B2)
- **ffmpeg** (Windows) — dual audio capture via DirectShow

## Architecture

See `AGENTS.md` for detailed architecture, routing, and conventions.

## License

MIT

---

*If the glove don't fit, you must acquit.* ⚖️