# CLC Voicemeeter Banana Setup — VERIFIED 24 Jul 2026

## Software
- Voicemeeter Banana (A1-A3, B1-B2)
- ffmpeg at C:\Users\krisr\Documents\ffmpeg\ffmpeg.exe

## Voicemeeter Banana

| Strip | Device | Routing | Purpose |
|-------|--------|---------|---------|
| **Input 1** | Headset Microphone (Yealink UH36) | A1, B2, mono | Client mic → headset + Webex mic + ffmpeg #2 (B2) |
| **Input 2** | (none) | — | Unused |
| **Input 3** | (none) | — | Unused |
| **Voicemeeter Input** | Webex speaker | A1, B1 | Call audio → headset (A1) + ffmpeg #1 (B1) |
| **Voicemeeter AUX** | Cochran TTS | A1, B2 | TTS → headset (A1) + Webex mic (B2) |
| **A1** (Hardware Out) | Headset Earphone (Yealink UH36) | — | Kris hears call + TTS |

### ⚠️ Critical: AUX Input Routing

The Voicemeeter AUX Input column must have **both A1 and B2 lit**:
- **A1** — so you hear Cochran's voice through your headset
- **B2** — so Webex mic picks up Cochran's voice (call participants hear him)

If A1 is not lit on AUX, you won't hear Cochran. If B2 is not lit, the call won't hear Cochran.

### Karaoke Mode (K)

The **K (Karaoke)** button on the Voicemeeter AUX column can interfere with TTS audio. If you hear distorted or missing audio, turn OFF the K button on AUX Input.

## Webex

| Setting | Device |
|---------|--------|
| **Speaker** | Voicemeeter Input (VB-Audio Voicemeeter VAIO) Virtual |
| **Microphone** | Voicemeeter Out B2 (VB-Audio Voicemeeter VAIO) |

## Windows Default Playback

**Before a call with TTS:** Manually set Windows default playback to `Voicemeeter AUX Input (VB-Audio Voicemeeter VAIO)`. This is where Cochran's TTS plays via PowerShell SoundPlayer.

**After the call:** Restore to `Headset Earphone (Yealink UH36)` or preferred device.

## Two Capture Files (start both on Windows)

| File | Captures | Device | Output File |
|------|----------|--------|-------------|
| `stream_to_file.bat` | B1 — other party (Webex audio) | Voicemeeter Out B1 | B:\cochran_audio.raw |
| `stream_to_file_client.bat` | B2 — client (Yealink mic) | Voicemeeter Out B2 | B:\cochran_audio_client.raw |

## Pipeline (WSL)

```bash
# From the WSL/ environment folder:
python3 dashboard_server.py          # Dashboard on http://localhost:8765
python3 cochran_live.py --matter test  # Pipeline (test matter)
```

## ⚠️ Known Issues

- **Voicemeeter VAIO3 Input** is a GHOST DEVICE — does not feed any strip. Always use `Voicemeeter Input (VB-Audio Voicemeeter VAIO)` (without the 3).
- **WSL PowerShell session isolation** — PowerShell launched from WSL runs in Session 1 which may not have audio access. Setting Windows default playback to Voicemeeter AUX Input resolves this for TTS playback.
- **Muting headset in Voicemeeter** breaks both client capture and TTS monitoring. Use Webex mute instead during calls.
- **ffmpeg volume in Windows Volume Mixer** — if ffmpeg.exe volume is set to 1 (near zero), capture files will be silent. Check Volume Mixer if no audio is being captured.