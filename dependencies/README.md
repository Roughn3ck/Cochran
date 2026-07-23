# Dependencies — Cochran Legal Council

This folder contains install scripts, model files, and download instructions for all CLC dependencies.

## Contents

```
dependencies/
├── README.md                      # This file
├── install_whisper.sh             # faster-whisper + CUDA install (WSL/Linux)
├── install_kokoro.sh              # Kokoro TTS install (WSL/Linux)
├── install_chatterbox.sh          # Chatterbox TTS install (WSL/Linux)
├── kokoro-tts                     # Wrapper script for kokoro subprocess
├── chatterbox-tts                 # Wrapper script for chatterbox subprocess
├── cochran-reference-24k.wav      # Cochran voice clone reference (1.5MB)
├── kokoro-model/                  # Kokoro-82M model + voices
│   ├── config.json
│   ├── kokoro-v1_0.pth            # 327MB model
│   └── voices/                    # 7 voice packs
│       ├── af_bella.pt
│       ├── af_heart.pt
│       ├── af_nicole.pt
│       ├── af_sarah.pt
│       ├── af_sky.pt
│       ├── am_adam.pt
│       └── am_michael.pt          # CLC fallback voice
└── VBCABLE_Driver_Pack45/         # VB-Audio Virtual Cable driver
    ├── vbaudio_cable64_2003.cat
    ├── vbaudio_cable64_2003.sys
    └── vbaudio_cable64arm_win10.sys
```

## Installation Guide

### 1. faster-whisper (Speech to Text)

**WSL/Linux:**
```bash
bash dependencies/install_whisper.sh
# Creates venv at ~/.local/share/whisper-venv
# Model (large-v3-turbo) downloads on first run (~1.5GB)
```

**Windows (planned):**
```powershell
# pip install faster-whisper
# CUDA: requires NVIDIA driver installed (not CUDA toolkit)
# pip install nvidia-cublas-cu12 nvidia-cudnn-cu12 nvidia-cuda-nvrtc-cu12
```

### 2. Ollama (LLM Inference)

Download and install from **https://ollama.com**

```bash
# Install the model
ollama pull deepseek-v4-flash:cloud

# Verify it's running
curl http://localhost:11434/api/tags
```

The pipeline calls Ollama via `localhost:11434/api/chat`. No API key needed for local inference.

### 3. Kokoro TTS (Fast Fallback Voice)

**WSL/Linux:**
```bash
bash dependencies/install_kokoro.sh
# Creates venv at ~/.local/share/kokoro-venv
```

**Pre-cached model:** The `kokoro-model/` folder contains the full Kokoro-82M model and all 7 voice packs. To use the cache instead of downloading from HuggingFace:

```bash
# Copy to HuggingFace cache location
mkdir -p ~/.cache/huggingface/hub/models--hexgrad--Kokoro-82M/snapshots/f3ff3571791e39611d31c381e3a41a3af07b4987/
cp -r dependencies/kokoro-model/* ~/.cache/huggingface/hub/models--hexgrad--Kokoro-82M/snapshots/f3ff3571791e39611d31c381e3a41a3af07b4987/
```

**Default voice for CLC:** `am_michael` (male, professional)
**Available voices:** af_bella, af_heart, af_nicole, af_sarah, af_sky (female) / am_adam, am_michael (male)

### 4. Chatterbox TTS (Cochran Voice Clone)

**WSL/Linux:**
```bash
bash dependencies/install_chatterbox.sh
# Creates venv at ~/.local/share/chatterbox-venv

# Copy the Cochran voice reference
mkdir -p ~/.local/share/chatterbox
cp dependencies/cochran-reference-24k.wav ~/.local/share/chatterbox/

# Copy the wrapper script
cp dependencies/chatterbox-tts ~/.local/bin/
chmod +x ~/.local/bin/chatterbox-tts
```

The Cochran voice reference (`cochran-reference-24k.wav`) is a 1.5MB 24kHz WAV file used for voice cloning. This produces Cochran's authentic voice but has higher latency (~10-30s per generation).

### 5. VB-Audio Voicemeeter Banana (Audio Routing)

**Manual download required** — Voicemeeter Banana is free from VB-Audio:

1. Go to **https://vb-audio.com/Voicemeeter/banana.htm**
2. Click the download button
3. Run the installer
4. Reboot after installation

**VBCABLE Driver Pack** is included in `dependencies/VBCABLE_Driver_Pack45/` — this is the basic virtual cable driver. Voicemeeter Banana includes its own virtual cables, so VBCABLE is only needed if you want additional virtual cables beyond what Voicemeeter provides.

See `VB-AUDIO-SETUP.md` (in root or environment folder) for Voicemeeter Banana routing configuration.

### 6. ffmpeg (Audio Capture — Windows)

1. Download from **https://ffmpeg.org/download.html** (Windows build)
2. Extract to `C:\Users\<user>\Documents\ffmpeg\`
3. Verify: `ffmpeg.exe` should be at `C:\Users\<user>\Documents\ffmpeg\ffmpeg.exe`

The two batch files (`stream_to_file.bat`, `stream_to_file_client.bat`) use ffmpeg's DirectShow (dshow) to capture audio from Voicemeeter's virtual outputs.

## Quick Install (WSL — all dependencies)

```bash
# 1. Install all venvs
bash dependencies/install_whisper.sh
bash dependencies/install_kokoro.sh
bash dependencies/install_chatterbox.sh

# 2. Copy Kokoro model to HF cache
mkdir -p ~/.cache/huggingface/hub/models--hexgrad--Kokoro-82M/snapshots/f3ff3571791e39611d31c381e3a41a3af07b4987/
cp -r dependencies/kokoro-model/* ~/.cache/huggingface/hub/models--hexgrad--Kokoro-82M/snapshots/f3ff3571791e39611d31c381e3a41a3af07b4987/

# 3. Copy Cochran voice reference
mkdir -p ~/.local/share/chatterbox
cp dependencies/cochran-reference-24k.wav ~/.local/share/chatterbox/

# 4. Copy wrapper scripts
cp dependencies/kokoro-tts ~/.local/bin/ && chmod +x ~/.local/bin/kokoro-tts
cp dependencies/chatterbox-tts ~/.local/bin/ && chmod +x ~/.local/bin/chatterbox-tts

# 5. Install Ollama + model
# Download from https://ollama.com
ollama pull deepseek-v4-flash:cloud

# 6. Install Voicemeeter Banana (Windows side)
# Download from https://vb-audio.com/Voicemeeter/banana.htm
```

## Version Information

| Dependency | Version | Notes |
|-----------|---------|-------|
| faster-whisper | 1.2.1 | CUDA, float16 |
| Whisper model | large-v3-turbo | ~1.5GB, downloads on first run |
| Kokoro | 82M (v1.0) | 7 voices, 24kHz output |
| Chatterbox | latest | Voice cloning, PerthNet |
| Ollama | latest | Local inference, port 11434 |
| LLM model | deepseek-v4-flash:cloud | Via Ollama |
| Voicemeeter | Banana | 5 inputs, 5 outputs, A1-A3 + B1-B2 |
| ffmpeg | N-124881 | DirectShow capture |