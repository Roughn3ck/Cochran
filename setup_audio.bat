@echo off
REM setup_audio.bat — Configure Windows audio routing for Cochran
REM Run this BEFORE starting Webex + Cochran pipeline
REM
REM After running:
REM   1. Webex speakers should be set to "CABLE Input" (so Cochran hears the call)
REM   2. Webex microphone should be set to "CABLE Output" (so Cochran speaks)
REM   3. Your headphones should stay on Yealink (so you can still hear)

echo ================================================
echo COCHRAN AUDIO ROUTING SETUP
echo ================================================
echo.
echo MANUAL STEPS REQUIRED:
echo.
echo 1. Right-click speaker icon in taskbar ^> Sound Settings
echo.
echo 2. Set DEFAULT playback (speakers) to:
echo    "CABLE Input (VB-Audio Virtual Cable)"
echo    ^(This routes ALL system audio through VB-Cable^)
echo    ^(Cochran captures from CABLE Output^)
echo.
echo 3. In Webex Settings ^> Audio:
echo    SPEAKER = "CABLE Input (VB-Audio Virtual Cable)"
echo    MICROPHONE = "CABLE Output (VB-Audio Virtual Cable)"
echo.
echo 4. Set your HEADPHONES to Yealink in:
echo    Sound Settings ^> App volume and device preferences
echo    ^(So you can still hear the call through your headset^)
echo.
echo 5. Alternatively: Keep headphones on Yealink, set Webex
echo    speaker to BOTH Yealink + CABLE Input using:
echo    Settings ^> Sound ^> App volume ^> Webex ^> Output = CABLE Input
echo.
echo ================================================
echo.
echo Audio routing:
echo   Webex call audio ^> CABLE Input ^> CABLE Output ^> ffmpeg ^> cochran_audio.raw
echo   Cochran TTS ^> CABLE Input ^> CABLE Output ^> Webex mic ^> call participants
echo.
echo Starting VB-Cable capture test (5 seconds)...
echo.

C:\Users\krisr\Documents\ffmpeg\ffmpeg.exe -y -f dshow -i "CABLE Output (VB-Audio Virtual Cable)" -ac 1 -ar 16000 -sample_fmt s16 -t 5 B:\cochran_test.raw 2>nul

if exist B:\cochran_test.raw (
    for %%A in (B:\cochran_test.raw) do echo Test capture: %%~zA bytes
    echo VB-Cable capture is working!
    del B:\cochran_test.raw
) else (
    echo WARNING: No audio captured. Check VB-Cable is installed and CABLE Output is available.
)

echo.
echo Ready to start the pipeline? Run: stream_to_file.bat
pause