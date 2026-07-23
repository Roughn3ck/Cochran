@echo off
REM stream_to_file_client.bat — Captures Voicemeeter B2 Output (client/headset mic)
REM Dual-source architecture:
REM   stream_to_file.bat         = B1 = Webex audio (other party)
REM   stream_to_file_client.bat  = B2 = Yealink mic (client)
REM
REM B2 also serves as the Webex microphone — multiple consumers can read from it.
REM
REM Usage: stream_to_file_client.bat
REM Stop: Ctrl+C

echo ================================================
echo COCHRAN — CLIENT AUDIO CAPTURE (B2)
echo ================================================
echo.
echo Capturing from: Voicemeeter Out B2 (VB-Audio Voicemeeter VAIO)
echo Writing to: B:\cochran_audio_client.raw
echo Format: 16kHz mono 16-bit PCM (Whisper-optimized)
echo.
echo This is the CLIENT source (headset mic via Voicemeeter Input 1).
echo B2 also feeds the Webex microphone — capture does not interfere.
echo.
echo Press Ctrl+C to stop
echo ================================================
echo.

REM Delete old capture file to start fresh
if exist B:\cochran_audio_client.raw del B:\cochran_audio_client.raw

C:\Users\krisr\Documents\ffmpeg\ffmpeg.exe -y -f dshow -i "audio=Voicemeeter Out B2 (VB-Audio Voicemeeter VAIO)" -ac 1 -ar 16000 -sample_fmt s16 -f s16le B:\cochran_audio_client.raw