@echo off
REM setup_audio.bat — Configure Windows audio routing for Cochran Legal Council
REM Two-cable architecture using VB-Audio Voicemeeter Banana
REM
REM Run this BEFORE starting the pipeline.
REM
REM Architecture:
REM   INBOUND (hear the call):
REM     Webex speakers -> Voicemeeter VAIO Input -> B1 Output -> ffmpeg (capture)
REM                                          -> A1 Output -> Yealink Earphone (Kris hears)
REM
REM   OUTBOUND (speak into the call):
REM     Cochran TTS -> Voicemeeter AUX Input -> B2 Output -> Webex microphone
REM     Kris voice -> Yealink Mic (Hardware Input 1) -> B2 Output -> Webex

echo ================================================
echo COCHRAN LEGAL COUNCIL — AUDIO SETUP
echo ================================================
echo.
echo TWO-CABLE ARCHITECTURE (VB-Audio Voicemeeter Banana)
echo.
echo CABLE-A (INBOUND — Cochran listens):
echo   Webex speaker = Voicemeeter VAIO
echo   VAIO strip -> B1 (ffmpeg captures from Voicemeeter Out B1)
echo   VAIO strip -> A1 (Kris hears via Yealink Earphone)
echo.
echo CABLE-B (OUTBOUND — Cochran speaks):
echo   Cochran TTS -> Voicemeeter AUX Input -> B2 -> Webex mic
echo   Yealink Mic (Hardware Input 1) -> B2 -> Webex mic
echo.
echo VOICEMEETER ROUTING:
echo   1. A1 = Headset Earphone (Yealink UH36)
echo   2. VAIO strip: A1 + B1 (call audio to Kris + ffmpeg)
echo   3. AUX strip: B2 (TTS to Webex mic)
echo   4. Hardware Input 1 = Yealink Mic: B2 (Kris to Webex mic)
echo.
echo WEBEX SETTINGS:
echo   Speaker = Voicemeeter VAIO
echo   Microphone = Voicemeeter Out B2
echo.
echo WINDOWS DEFAULT PLAYBACK:
echo   Headset Earphone (Yealink UH36) — normal default
echo   Cochran TTS temporarily switches to Voicemeeter AUX Input, then back
echo.
echo ================================================
echo.
echo Testing B1 capture (5 seconds)...
echo.

C:\Users\krisr\Documents\ffmpeg\ffmpeg.exe -y -f dshow -i "audio=Voicemeeter Out B1 (VB-Audio Voicemeeter VAIO)" -ac 1 -ar 16000 -sample_fmt s16 -t 5 B:\cochran_test.raw 2>nul

if exist B:\cochran_test.raw (
    for %%A in (B:\cochran_test.raw) do echo Test capture: %%~zA bytes
    echo B1 capture is working!
    del B:\cochran_test.raw
) else (
    echo WARNING: No audio captured from Voicemeeter Out B1.
    echo Check VAIO strip has B1 enabled and Webex speaker = Voicemeeter VAIO.
)

echo.
echo Ready to start the pipeline?
echo   1. Run: stream_to_file.bat (start ffmpeg capture)
echo   2. In WSL: python3 dashboard_server.py (start dashboard)
echo   3. In WSL: python3 cochran_live.py --private (start pipeline)
echo   4. Open: http://localhost:8765 (dashboard)
echo.
pause