@echo off
REM play_to_vbcable.bat — Plays a WAV file through VB-Cable Input (Webex mic)
REM Usage: play_to_vbcable.bat <wav_file>
REM
REM Setup: Set Windows default playback to "CABLE Input (VB-Audio Virtual Cable)"
REM Then Webex mic = CABLE Output = whatever plays through CABLE Input

if "%~1"=="" (
    echo Usage: play_to_vbcable.bat ^<wav_file^>
    exit /b 1
)

echo Playing %~1 through VB-Cable Input...

C:\Users\krisr\Documents\ffmpeg\ffmpeg.exe -i "%~1" -f wav - | C:\Users\krisr\Documents\ffmpeg\ffplay.exe -nodisp -autoexit -i pipe:0 2>nul

echo Done.