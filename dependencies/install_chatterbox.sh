#!/bin/bash
# install_chatterbox.sh — Install Chatterbox TTS (voice cloning)
# For WSL/Linux. Windows users: see install_chatterbox_windows.ps1
#
# Creates a Python venv with Chatterbox and dependencies

set -e

VENV_DIR="${1:-$HOME/.local/share/chatterbox-venv}"
BIN_DIR="${2:-$HOME/.local/bin}"
REF_DIR="${3:-$HOME/.local/share/chatterbox}"

echo "=== Installing Chatterbox TTS (voice cloning) ==="
echo "Venv: $VENV_DIR"

python3 -m venv "$VENV_DIR"
source "$VENV_DIR/bin/activate"

pip install --upgrade pip
pip install chatterbox-tts torchaudio soundfile

mkdir -p "$REF_DIR"
mkdir -p "$BIN_DIR"

echo ""
echo "=== Chatterbox TTS installed ==="
echo "Venv: $VENV_DIR"
echo ""
echo "Cochran voice reference: $REF_DIR/cochran-reference-24k.wav"
echo "Copy from: dependencies/cochran-reference-24k.wav"
echo ""
echo "Wrapper script: $BIN_DIR/chatterbox-tts"
echo "Copy from: dependencies/chatterbox-tts"