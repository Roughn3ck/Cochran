# AGENTS.md — Cochran Legal Council (CLC)

## Project

Real-time legal AI voice pipeline. Listen → Think → Speak. Not a chatbot, not an agent. A signal processing pipeline.

## Architecture — Two-Source Dual Capture

Voicemeeter Banana provides two virtual outputs (B1, B2). Each is a separate recording device that ffmpeg can capture independently:

```
B1 = Voicemeeter Out B1 = Webex audio (other party / phone)
B2 = Voicemeeter Out B2 = Yealink mic (client / headset) — also serves as Webex mic
```

```
CABLE-A (other party):
  Phone → Webex → VAIO → B1 → ffmpeg #1 → cochran_audio.raw
                          → A1 → Yealink (Kris hears)

CABLE-B (client):
  Yealink Mic → Input 1 → B2 → ffmpeg #2 → cochran_audio_client.raw
                             → Webex mic (call participants hear Kris)

TTS Output:
  Cochran TTS → PowerShell SoundPlayer → Windows Default (Voicemeeter AUX Input)
           → A1 (Kris hears) + B2 (Webex mic hears) + B1 (other party hears)
```

Two ffmpeg captures. Two audio files. Two transcription streams. Transcript labels by source:
```
[10:45:58] [CLIENT] Hi, my name is Kris Racette...
[10:46:10] [OTHER_PARTY] This is the other party source...
[10:46:25] [COCHRAN] Good morning. I am Cochran, legal representative...
```

B2 is already the Webex mic — adding ffmpeg capture doesn't change that. Multiple consumers can read from the same virtual output.

### ⚠️ VAIO3 Ghost Device

Voicemeeter Banana exposes `Voicemeeter VAIO3 Input` as a Windows playback device — it does NOT feed any Voicemeeter strip. Always use `Voicemeeter Input (VB-Audio Voicemeeter VAIO)` (without the 3).

### Verified Device Names

| Code Variable | Device Name |
|---------------|-------------|
| CABLE_A_OUTPUT | `Voicemeeter Out B1 (VB-Audio Voicemeeter VAIO)` |
| CABLE_B_OUTPUT | `Voicemeeter Out B2 (VB-Audio Voicemeeter VAIO)` |
| CABLE_B_INPUT | `Voicemeeter AUX Input (VB-Audio Voicemeeter VAIO)` |
| Webex speaker | `Voicemeeter Input (VB-Audio Voicemeeter VAIO)` |
| Webex mic | `Voicemeeter Out B2 (VB-Audio Voicemeeter VAIO)` |
| A1 hardware out | `Headset Earphone (Yealink UH36)` |
| Input 1 hardware | `Headset Microphone (Yealink UH36)` |

## Voicemeeter Banana Routing

| Strip | Device | Routing | Purpose |
|-------|--------|---------|---------|
| **Input 1** | Headset Microphone (Yealink UH36) | A1, B2, mono | Client mic → headset + Webex mic + ffmpeg #2 |
| **Voicemeeter Input** (VAIO) | Webex speaker | A1, B1 | Call audio → headset + ffmpeg #1 |
| **Voicemeeter AUX** | Cochran TTS | A1, B2 | TTS → headset + Webex mic |
| **A1** (Hardware Out) | Headset Earphone (Yealink UH36) | — | Kris hears call + TTS |

## Webex Settings

| Setting | Device |
|---------|--------|
| **Speaker** | `Voicemeeter Input (VB-Audio Voicemeeter VAIO)` Virtual |
| **Microphone** | `Voicemeeter Out B2 (VB-Audio Voicemeeter VAIO)` |

## Repository Structure

```
CLC/
├── windows/      # Windows-native pipeline
├── WSL/           # WSL-bridged pipeline (current working setup)
├── linux/         # Pure Linux pipeline
├── matters/       # Case context files (shared)
└── transcripts/   # Session transcripts (shared, gitignored)
```

Each environment folder contains its own `cochran_live.py` adapted for that OS. The `matters/` and `transcripts/` directories are shared — referenced via `../matters/` and `../transcripts/` from each environment folder.

## Matters System

Case contexts live in `matters/` (shared across environments):
- `matters/test_context.py` — testing/introduction flow (committed)
- `matters/case_context.example.py` — template for real matters (committed)
- Real matter files (e.g. `fwc_context.py`) are gitignored — never commit case details
- Each file provides prompts per mode: `DEFAULT_PROMPT`, `PRIVATE_PROMPT`, `COURT_PROMPT`, `COMMANDER_PROMPT`
- Load with `--matter <name>` flag

## Transcript Persistence

Sessions saved to `transcripts/` (shared across environments):
- `transcripts/test_call.txt`
- Format: `[timestamp] [SPEAKER] text`
- Speakers: `CLIENT` (headset/B2), `OTHER_PARTY` (Webex/B1), `COCHRAN` (TTS echo match)

## Pipeline Stages

1. **AudioCapture x2** — reads 6s PCM chunks from both audio files with 2s overlap. Skips to live on first read. Detects stalls. Silence check samples across entire chunk (8 points).
2. **Transcriber** — faster-whisper (large-v3-turbo, CUDA, float16). VAD filter, beam_size=5, English. Two streams, labeled by source.
3. **Thinker** — Ollama API (`/api/chat`) with DeepSeek V4 Flash. Mode-specific system prompts from active matter. 20-message rolling conversation. 60 max tokens, 0.7 temperature.
4. **Speaker** — Chatterbox (Cochran voice clone, primary) → Kokoro in-memory (am_michael, fallback) → Kokoro subprocess (last resort). Plays via PowerShell SoundPlayer to Windows default device (Voicemeeter AUX Input).

## Modes

| Mode | TTS | Prompt | Dashboard Button |
|------|-----|--------|------------------|
| private | ❌ | Full strategy, privileged | 🤐 Private |
| court | ✅ | Careful, on the record | ⚖️ Court |
| default | ✅ | No restrictions | 🎙️ Default |
| commander | ✅ | Professional business call | 📞 Commander |
| mute | ❌ | No LLM at all | 🔇 Mute |

Mode switching via `/tmp/cochran/mode.txt` — dashboard writes, pipeline reads each cycle.

## Echo Suppression

- `speaker.speaking` flag — if TTS is active, BOTH Whisper streams are discarded
- `ECHO_SUPPRESSION_COOLDOWN` = 45s after speaking — catches late results from Chatterbox's long generation time
- **TTS echo matching** — after TTS finishes, transcribed audio is compared against what Cochran said using word-overlap similarity. If match >= 60%, the entry is labeled `[COCHRAN]` in the transcript and not fed to the LLM. Match window: 60s.
- Pre-roll buffer: 1 silent chunk kept before speech for context (fixes word cutoff)

## Key Constants

| Constant | Value | Purpose |
|----------|-------|---------|
| `CHUNK_SECONDS` | 6 | Audio chunk size |
| `OVERLAP_SECONDS` | 2 | Overlap between chunks |
| `SILENCE_THRESHOLD` | 3 | % max amplitude for speech detection |
| `THINK_INTERVAL` | 4 | Seconds between LLM calls |
| `LLM_MAX_TOKENS` | 60 | Response length cap |
| `ECHO_SUPPRESSION_COOLDOWN` | 45 | Seconds to suppress after TTS |
| `KOKORO_SHORT_THRESHOLD` | 500 | Chars — Kokoro fast path (now unused since Chatterbox is primary) |
| `KOKORO_FALLBACK_VOICE` | am_michael | Male fallback voice |

## Conventions

- `matters/*.py` (except test and example) are gitignored — never commit case details
- `transcripts/*.txt` are gitignored — never commit call recordings
- All prompts are plain English, no markdown/asterisks (TTS compatibility)
- Name pronunciation fixes in `clean_for_speech()`: Kris→Chris, Muska→Mustka
- Logs use `[HH:MM:SS] [TAG] message` format, flushed immediately
- TTS playback: PowerShell `SoundPlayer.PlaySync()` to Windows default device (must be set to Voicemeeter AUX Input)

## Environment-Specific Notes

### WSL (current)
- Pipeline runs in WSL, reads audio from `/mnt/b/` mount
- TTS playback via WSL-launched PowerShell (has session isolation limitations)
- CUDA libraries must be in LD_LIBRARY_PATH before faster-whisper imports
- Ollama runs on Windows, accessed via localhost:11434

### Windows (planned)
- Pipeline runs natively on Windows Python
- Direct audio device access (no session isolation)
- Native SoundPlayer or pyaudio for playback
- No /mnt/b/ mount overhead

### Linux (future)
- PulseAudio/PipeWire instead of Voicemeeter
- Native ALSA or PulseAudio capture
- No Windows batch files needed

## Development

This project is developed by Slater (CTO) with direct code edits for pipeline infrastructure. Prompt engineering and case context owned by Cochran (Legal agent).

- LLM model: `deepseek-v4-flash:cloud` via Ollama
- Whisper: `large-v3-turbo` on CUDA
- TTS: Chatterbox (Cochran clone) primary, Kokoro (am_michael) fallback
- Cochran voice reference: `/home/krisr/.local/share/chatterbox/cochran-reference-24k.wav`