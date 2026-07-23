#!/bin/bash
# install_kokoro.sh — Install Kokoro TTS (KPipeline)
# For WSL/Linux. Windows users: see install_kokoro_windows.ps1
#
# Creates a Python venv with Kokoro and dependencies

set -e

VENV_DIR="${1:-$HOME/.local/share/kokoro-venv}"

echo "=== Installing Kokoro TTS ==="
echo "Venv: $VENV_DIR"

python3 -m venv "$VENV_DIR"
source "$VENV_DIR/bin/activate"

pip install --upgrade pip
pip install kokoro soundfile torch

echo ""
echo "=== Kokoro TTS installed ==="
echo "Model: hexgrad/Kokoro-82M (downloaded from HuggingFace on first run)"
echo "Voices: af_bella, af_heart, af_nicole, af_sarah, af_sky, am_adam, am_michael"
echo ""
echo "Default voice for CLC: am_michael (male, fallback)"
echo "Primary voice: Chatterbox (Cochran clone) — see install_chatterbox.sh"
echo ""
echo "Venv: $VENV_DIR"
echo ""
echo "Pre-cached model in dependencies/kokoro-model/ — copy to:"
echo "  cp -r dependencies/kokoro-model/* ~/.cache/huggingface/hub/models--hexgrad--Kokoro-82M/snapshots/*/