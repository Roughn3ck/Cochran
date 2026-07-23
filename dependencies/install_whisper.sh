#!/bin/bash
# install_whisper.sh — Install faster-whisper with CUDA support
# For WSL/Linux. Windows users: see install_whisper_windows.ps1
#
# Creates a Python venv with faster-whisper and CUDA dependencies

set -e

VENV_DIR="${1:-$HOME/.local/share/whisper-venv}"

echo "=== Installing faster-whisper (CUDA) ==="
echo "Venv: $VENV_DIR"

python3 -m venv "$VENV_DIR"
source "$VENV_DIR/bin/activate"

pip install --upgrade pip
pip install faster-whisper

# CUDA libraries (bundled via pip — no system CUDA toolkit needed)
pip install nvidia-cublas-cu12 nvidia-cudnn-cu12 nvidia-cuda-nvrtc-cu12

echo ""
echo "=== faster-whisper installed ==="
echo "Model: large-v3-turbo (downloaded on first run)"
echo "Device: cuda"
echo "Compute: float16"
echo ""
echo "Venv: $VENV_DIR"
echo ""
echo "Usage in cochran_live.py:"
echo "  source $VENV_DIR/bin/activate"
echo "  export LD_LIBRARY_PATH=\"$VENV_DIR/lib/python3.12/site-packages/nvidia/cublas/lib:$VENV_DIR/lib/python3.12/site-packages/nvidia/cudnn/lib:$VENV_DIR/lib/python3.12/site-packages/nvidia/cuda_nvrtc/lib:\$LD_LIBRARY_PATH\""
echo "  python3 cochran_live.py --matter test"