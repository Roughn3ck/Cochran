# ⚖️ Cochran — Real-Time Legal AI for Live Calls

**Listen → Think → Speak.** Cochran sits in on phone calls — mediation, conciliation, disputes, negotiations — and provides real-time strategic counsel.

Works for:
- **FWC conciliation** (unfair dismissal, general protections)
- **Family law mediation** (property settlements, parenting)
- **Tenancy disputes** (VCAT, NCAT, QCAT)
- **Neighbour disputes** (fences, noise, trees)
- **Insurance claims** (denial, underpayment)
- **Employment negotiations** (contracts, severance)
- **Any adversarial call where you need a second brain**

## Architecture

```
Call Audio (Webex/Zoom/Phone)
       ↓
VB-Cable (virtual audio cable)
       ↓
ffmpeg → cochran_audio.raw (16kHz mono PCM)
       ↓
Whisper (faster-whisper, CUDA) → transcript
       ↓
LLM (DeepSeek V3.2 via Ollama) → strategic response
       ↓
Kokoro TTS → WAV audio
       ↓
VB-Cable → back into the call

Browser Dashboard (localhost:8765)
  → 🤐 Private Counsel (text only, your eyes only)
  → ⚖️ Court Open (speaks aloud, on the record)
  → 🎙️ Default (speaks aloud, unrestricted)
  → 🔇 Mute (listening only)
```

## Prerequisites

### Windows
- **VB-Audio Virtual Cable** (free): https://vb-audio.com/Cable/
- **ffmpeg** for Windows: https://ffmpeg.org/download.html
- Place `ffmpeg.exe` in `C:\Users\<you>\Documents\ffmpeg\`

### WSL/Linux
```bash
# faster-whisper with CUDA
pip install faster-whisper torch  # in a venv

# Ollama with DeepSeek
ollama pull deepseek-v3.2:cloud

# Kokoro TTS
pip install kokoro  # in a venv
```

## Audio Setup (Windows)

**⚠️ This is the #1 source of bugs. Follow exactly.**

### Step 1: Windows Sound Settings
- **Default playback** = Your normal speakers/headphones (NOT CABLE Input)
- **Default recording** = Your normal microphone (NOT CABLE Output)

### Step 2: Call App Audio Settings (Webex/Zoom/Teams)
- **Speaker** = `CABLE Input (VB-Audio Virtual Cable)`
- **Microphone** = `CABLE Output (VB-Audio Virtual Cable)`

### Step 3: VB-Cable Output Properties
- Right-click speaker → Sounds → Recording → CABLE Output → Listen tab
- ✅ Check "Listen to this device"
- Playback through: Your speakers/headphones
- This lets YOU hear the call while Cochran captures it

### Step 4: Start audio capture
```
stream_to_file.bat
```

## Running the Pipeline

### Terminal 1: Dashboard
```bash
cd /path/to/Cochran
python3 dashboard_server.py
# → http://localhost:8765
```

### Terminal 2: Pipeline
```bash
# Set environment variables for CUDA/CUDA libs
export XDG_CACHE_HOME="$HOME/.local/share/whisper"
export HF_HUB_DISABLE_TELEMETRY=1
export LD_LIBRARY_PATH="$HOME/.local/share/whisper-venv/lib/python3.12/site-packages/nvidia/cublas/lib:$HOME/.local/share/whisper-venv/lib/python3.12/site-packages/nvidia/cudnn/lib:$HOME/.local/share/whisper-venv/lib/python3.12/site-packages/nvidia/cuda_nvrtc/lib"

python3 cochran_live.py --private
```

### Modes
| Flag | Mode | Voice | Prompt Style |
|------|------|-------|-------------|
| `--private` | Private Counsel | ❌ Text only | Full strategy, no holds barred |
| `--court` | Court Open | ✅ Speaks aloud | Careful, on the record |
| `--default` | Default | ✅ Speaks aloud | No restrictions |
| `--no-think` | Transcribe only | ❌ | No LLM, just transcript |
| `--no-speak` | Listen + Think | ❌ | No voice output |

### Dashboard (http://localhost:8765)
Click buttons to switch modes in real-time. No restart needed.

## Case Context

Create `case_context.py` (not in repo — see `.gitignore`) with your specific case details:

```python
PRIVATE_PROMPT = """You are Cochran - Kris's private legal counsel.
Case: [Your case details here]
Be ice cold. Measured. Strategic. Say as much as needed, as few words as possible. Plain English only."""

COURT_PROMPT = """You are Cochran - speaking in open court.
Case: [Your case details here]
CRITICAL: No strategy leaks. Say as much as needed, as few words as possible. Plain English only."""
```

See `case_context.example.py` for the template.

## Latency Budget

| Step | Time |
|------|------|
| Whisper (4s chunk) | ~0.1s |
| DeepSeek V3.2 Cloud | ~2.7s |
| Kokoro TTS (in-memory) | ~1.1s |
| Audio playback | ~0.5s |
| **Total** | **~4.5s** |

## Key Files

| File | Purpose |
|------|---------|
| `cochran_live.py` | Main pipeline (Listen → Think → Speak) |
| `dashboard_server.py` | HTTP server for live dashboard |
| `dashboard.html` | Web dashboard with mode switching |
| `stream_to_file.bat` | Windows ffmpeg audio capture |
| `setup_audio.bat` | Audio routing instructions |
| `case_context.example.py` | Template for case-specific prompts |
| `.env.example` | Environment variables template |

## Known Issues

1. **Old audio buffer** — Pipeline skips to end of file on startup. Always restart `stream_to_file.bat` before a call.
2. **Audio volume** — If VB-Cable is at 98%+, adjust CABLE Output gain in Windows Sound settings.
3. **"Kris" → "Crease"** — Whisper mispronounces some names. `clean_for_speech()` remaps known ones.
4. **Asterisks in TTS** — `clean_for_speech()` strips markdown before speech output.
5. **nircmd auto-switch** — DON'T auto-switch Windows audio devices. It causes chaos. Set them manually.

## Use Cases

- 🏛️ **FWC Conciliation** — Unfair dismissal, general protections, enterprise agreements
- 👨‍👩‍👧 **Family Law Mediation** — Property, parenting, spousal maintenance
- 🏠 **Tenancy Disputes** — VCAT/NCAT/QCAT hearings, bond claims, eviction defence
- 🏡 **Neighbour Disputes** — Fences, noise, trees, easements
- 🛡️ **Insurance Claims** — Denial, underpayment, bad faith
- 💼 **Employment Negotiations** — Contracts, severance, workplace rights
- 📞 **Any call where you need a second brain**

## License

Private — Executive Mind Pty Ltd