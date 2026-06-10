# 🧤 Cochran — Listen → Think → Speak

Real-time legal AI for phone calls. Listens to the call, thinks strategically, speaks back.

Built for FWC conciliation: Kris Racette v Fun Crew Pty Ltd (iPlay), C2026/1071.

## Architecture

```
Webex Call Audio
       ↓
VB-Cable Input (Windows playback device for Webex)
       ↓
VB-Cable Output (Windows recording device)
       ↓ (ffmpeg captures to raw file)
       ↓
cochran_audio.raw (16kHz mono 16-bit PCM)
       ↓
Whisper (faster-whisper, CUDA RTX 5080) → transcript
       ↓
DeepSeek V3.2 (Ollama cloud) → strategic response
       ↓
Kokoro TTS (in-memory) → WAV audio
       ↓
PowerShell SoundPlayer → VB-Cable Input → Webex mic
```

## Prerequisites

### Windows
- **VB-Audio Virtual Cable** (free): https://vb-audio.com/Cable/
- **ffmpeg** for Windows: https://ffmpeg.org/download.html
- **nircmd** (for audio device switching): included or download from https://www.nirsoft.net/utils/nircmd.html
- Place `ffmpeg.exe` and `nircmd.exe` in `C:\Users\krisr\Documents\ffmpeg\`

### WSL (Ubuntu)
```bash
# Python venv with faster-whisper
/home/krisr/.local/share/whisper-venv/bin/python3

# Ollama with DeepSeek V3.2
ollama pull deepseek-v3.2:cloud

# Kokoro TTS
/home/krisr/.local/share/kokoro-venv/bin/python3
```

## Audio Setup (Windows)

This is the #1 source of bugs. Follow exactly:

### Step 1: Windows Sound Settings
- **Default playback** = Your normal speakers/headset (NOT CABLE Input)
- **Default recording** = Your normal microphone (NOT CABLE Output)

### Step 2: Webex Audio Settings (in the Webex app)
- **Speaker** = `CABLE Input (VB-Audio Virtual Cable)`
- **Microphone** = `CABLE Output (VB-Audio Virtual Cable)`

### Step 3: VB-Cable Output Properties
- Right-click speaker icon → Sounds → Recording tab
- Double-click `CABLE Output` → Listen tab
- ✅ Check "Listen to this device"
- Playback through: Your speakers/headset
- This lets YOU hear the call while Cochran captures it

### Step 4: Start audio capture
Double-click `stream_to_file.bat` — this starts ffmpeg capturing from CABLE Output.

## Running the Pipeline

### Terminal 1 (WSL): Dashboard
```bash
cd /mnt/b/Github/Cochran
python3 dashboard_server.py
# Dashboard: http://localhost:8765
```

### Terminal 2 (WSL): Pipeline
```bash
export XDG_CACHE_HOME="/home/krisr/.local/share/whisper"
export HF_HUB_DISABLE_TELEMETRY=1
export LD_LIBRARY_PATH="/home/krisr/.local/share/whisper-venv/lib/python3.12/site-packages/nvidia/cublas/lib:/home/krisr/.local/share/whisper-venv/lib/python3.12/site-packages/nvidia/cudnn/lib:/home/krisr/.local/share/whisper-venv/lib/python3.12/site-packages/nvidia/cuda_nvrtc/lib"

cd /mnt/b/Github/Cochran
/home/krisr/.local/share/whisper-venv/bin/python3 cochran_live.py --private
```

### Modes
- `--private` — Text only. Strategic advice for Kris. No voice output. **Start here.**
- `--court` — Voice enabled. Careful statements suitable for open court. Everyone can hear.
- `--default` — Voice enabled. No restrictions.
- `--no-think` — Transcription only. No LLM.
- `--no-speak` — Listen and think only. No TTS.

### Dashboard (http://localhost:8765)
- 🤐 **Private Counsel** — Text only, not spoken aloud
- ⚖️ **Court Open** — Voice enabled, careful on-record statements
- 🎙️ **Default** — Voice enabled, no restrictions
- 🔇 **Mute** — Listening only

Switching modes changes:
- The LLM system prompt (what advice to give)
- Whether TTS is enabled
- **Future:** Windows default audio device (auto-switch between speakers and CABLE Input)

## Key Files

| File | Purpose |
|------|---------|
| `cochran_live.py` | Main pipeline (Listen → Think → Speak) |
| `dashboard_server.py` | HTTP server for live dashboard |
| `dashboard.html` | Web dashboard with mode switching |
| `stream_to_file.bat` | Windows ffmpeg audio capture |
| `setup_audio.bat` | Audio routing instructions |
| `README.md` | This file |

## Latency Budget

| Step | Time |
|------|------|
| Whisper (4s chunk) | ~0.1s |
| DeepSeek V3.2 Cloud | ~2.7s |
| Kokoro TTS (in-memory) | ~1.1s |
| PowerShell Play() | ~0.5s |
| **Total** | **~4.5s** |

## Known Issues

1. **Old audio buffer** — Pipeline now skips to end of existing file on startup (`_caught_up` flag)
2. **"Thank you" spam** — Webex hold music/greetings get transcribed. Not a bug — it's real audio
3. **Audio volume** — VB-Cable at 98% amplitude causes clipping. Need to adjust CABLE Output gain in Windows
4. **nircmd auto-switch** — Works but caused chaos when it changed Windows default playback. DON'T auto-switch. Manual only.
5. **"Kris" mispronounced as "Crease"** — `clean_for_speech()` maps both to "Chris" for Kokoro
6. **Asterisks in TTS** — `clean_for_speech()` strips all markdown before speech output

## Case Context

Kris Racette v Fun Crew Pty Ltd (iPlay), FWC C2026/1071
- s351 General Protections — no minimum employment period
- iPlay terminated same day they received Westpac letter about Kris's conviction
- No inherent requirements assessment was done
- s351 has NO cap
- Probation is irrelevant to s351
- AHRC criminal record discrimination is the strategic reserve

## License

Private — Executive Mind Pty Ltd