@echo off
REM stream_to_file.bat — Captures VB-Cable audio to raw file for WSL Cochran pipeline
REM VB-Cable Input must be set as Windows default playback device
REM
REM Usage: stream_to_file.bat
REM Stop: Ctrl+C

echo ================================================
echo COCHRAN AUDIO CAPTURE
echo ================================================
echo.
echo Capturing from: CABLE Output (VB-Audio Virtual Cable)
echo Writing to: B:\cochran_audio.raw
echo Format: 16kHz mono 16-bit PCM (Whisper-optimized)
echo.
echo Press Ctrl+C to stop
echo ================================================
echo.

REM Delete old capture file to start fresh
if exist B:\cochran_audio.raw del B:\cochran_audio.raw

C:\Users\krisr\Documents\ffmpeg\ffmpeg.exe -y -f dshow -i "audio=CABLE Output (VB-Audio Virtual Cable)" -ac 1 -ar 16000 -sample_fmt s16 -f s16le B:\cochran_audio.raw