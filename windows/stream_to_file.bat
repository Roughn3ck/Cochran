@echo off
REM stream_to_file.bat — Captures Voicemeeter B1 Output audio for WSL Cochran pipeline
REM Two-cable architecture (VB-Audio Voicemeeter Banana):
REM   CABLE-A: Webex call audio → Voicemeeter VAIO → B1 → ffmpeg (Cochran listens)
REM   CABLE-B: Cochran TTS → Voicemeeter AUX → B2 → Webex microphone (Cochran speaks)
REM
REM Usage: stream_to_file.bat
REM Stop: Ctrl+C

echo ================================================
echo COCHRAN LEGAL COUNCIL — AUDIO CAPTURE
echo ================================================
echo.
echo Capturing from: Voicemeeter Out B1 (VB-Audio Voicemeeter VAIO)
echo Writing to: B:\cochran_audio.raw
echo Format: 16kHz mono 16-bit PCM (Whisper-optimized)
echo.
echo Two-cable architecture:
echo   CABLE-A (capture): Webex -> Voicemeeter VAIO -> B1 Output -> ffmpeg
echo   CABLE-B (playback): Cochran TTS -> Voicemeeter AUX -> B2 Output -> Webex mic
echo.
echo Press Ctrl+C to stop
echo ================================================
echo.

REM Delete old capture file to start fresh
if exist B:\cochran_audio.raw del B:\cochran_audio.raw

C:\Users\krisr\Documents\ffmpeg\ffmpeg.exe -y -f dshow -i "audio=Voicemeeter Out B1 (VB-Audio Voicemeeter VAIO)" -ac 1 -ar 16000 -sample_fmt s16 -f s16le B:\cochran_audio.raw