#!/usr/bin/env python3
r"""
Cochran - Full Listen > Think > Speak Pipeline
Real-time audio transcription + LLM strategic analysis + TTS output

Architecture:
  Windows ffmpeg -> B:\cochran_audio.raw (16kHz mono PCM)
  WSL reads /mnt/b/cochran_audio.raw -> Whisper (faster-whisper, CUDA) -> transcript
  -> Ollama LLM (glm-4.7-flash, Cochran legal context) -> strategic response
  -> Kokoro TTS -> WAV -> play to VB-Cable Input -> Webex mic

Usage:
  python3 cochran_live.py [--whisper-model MODEL] [--llm MODEL] [--voice VOICE]
  python3 cochran_live.py --no-speak   # Listen + Think only
  python3 cochran_live.py --no-think   # Listen only (transcription)
"""

import subprocess
import struct
import wave
import os
import sys
import time
import json
import signal
import threading
import argparse
import urllib.request

# ============================================================
# CONFIG
# ============================================================
AUDIO_FILE = "/mnt/b/cochran_audio.raw"
SAMPLE_RATE = 16000
CHANNELS = 1
BYTES_PER_SAMPLE = 2
CHUNK_SECONDS = 4          # 4s chunks = good balance of speed and accuracy
CHUNK_BYTES = 128000   # 4s * 16kHz * 1ch * 2bytes
SILENCE_THRESHOLD = 3  # 3% max amplitude = speech detection threshold
OVERLAP_SECONDS = 1
OVERLAP_BYTES = int(OVERLAP_SECONDS * SAMPLE_RATE * CHANNELS * BYTES_PER_SAMPLE)

# Whisper config
WHISPER_MODEL_DEFAULT = "large-v3-turbo"
WHISPER_DEVICE = "cuda"
WHISPER_COMPUTE = "float16"

# LLM config (Ollama - local/free, included in subscription)
LLM_MODEL_DEFAULT = "deepseek-v3.2:cloud"
LLM_API_HOST = "localhost"
LLM_API_PORT = 11434
LLM_API_PATH = "/api/chat"
LLM_MAX_TOKENS = 60
LLM_TEMPERATURE = 0.7

# TTS config
TTS_VOICE_DEFAULT = "cochran"
TTS_OUTPUT_DIR = "/tmp/cochran/tts"

# Pipeline state
TRANSCRIPT_FILE = "/tmp/cochran/transcript.txt"
RESPONSE_FILE = "/tmp/cochran/last_response.txt"


def clean_for_speech(text):
    """Strip markdown and special characters for TTS."""
    import re
    # Remove asterisks (bold/italic markdown)
    text = re.sub(r'\*{1,2}([^*]+)\*{1,2}', r'\1', text)
    # Remove bullet points
    text = re.sub(r'^[-*] ', '', text, flags=re.MULTILINE)
    # Remove underscores
    text = text.replace('_', ' ')
    # Remove double quotes that TTS reads as literal
    text = text.replace('"', '')
    # Remove brackets
    text = re.sub(r'[\[\](){}]', '', text)
    # Name pronunciation fixes for TTS
    text = text.replace('Kris', 'Chris')  # Kokoro pronounces Chris correctly
    text = text.replace('Crease', 'Chris')  # Whisper sometimes hears "Crease" instead of "Kris"
    # Clean up extra spaces
    text = re.sub(r'\s+', ' ', text).strip()
    return text


# ============================================================
# MODE PROMPTS (used by dashboard mode switching)
# ============================================================
PRIVATE_PROMPT = """You are Cochran - Kris's private legal counsel. NO ONE else can hear this.

Be ice cold. Measured. Strategic. Never reactive.
Never use asterisks, markdown, bullet points or special characters. Plain English only.
Say as much as the situation demands — no more, no less. Brevity is precision, not limitation.
If closing a case requires ten sentences, deliver ten. If one word suffices, deliver one.

You can share ANY strategy, weaknesses, tactical advice. This is privileged.

Ice cold. Tactical. Private counsel. Plain English. As much as needed, as few words as possible."""

COURT_PROMPT = """You are Cochran - speaking in open court where ALL parties can hear you.

CRITICAL: Do NOT reveal strategy, weaknesses, or tactical advice. You are on the record.
Never tip off the other side about your strategy.
Never use asterisks, markdown, bullet points or special characters. Plain English only.
Say as much as the situation demands — no more, no less. Brevity is precision, not limitation.
If closing a case requires a paragraph, deliver a paragraph. If one word suffices, deliver one.

Ice cold. Plain English. On the record. As much as needed, as few words as possible."""


NIRCMD = '/mnt/c/Users/krisr/Documents/ffmpeg/nircmd.exe'
POWERSHELL = '/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe'

def switch_audio_device(mode):
    """Switch Windows default audio device based on Cochran mode.
    private -> Yealink headset (the client hears locally, no Webex output)
    court   -> CABLE Input (Cochran speaks into Webex mic)
    """
    if mode == 'court':
        device = 'CABLE Input'
        desc = 'VB-Cable Input (Webex hears Cochran)'
    else:
        device = 'Headset Earphone'
        desc = 'Yealink headset (the client hears locally)'
    
    try:
        result = subprocess.run(
            [POWERSHELL, '-c', f"C:\\Users\\krisr\\Documents\\ffmpeg\\nircmd.exe setdefaultsounddevice '{device}'"],
            capture_output=True, text=True, timeout=10
        )
        log("AUDIO", f"Switched to {desc}")
        return True
    except Exception as e:
        log("AUDIO", f"Failed to switch audio: {e}")
        return False


def log(tag, msg):
    ts = time.strftime("%H:%M:%S")
    print(f"[{ts}] [{tag}] {msg}", flush=True)


# ============================================================
# AUDIO CAPTURE
# ============================================================
class AudioCapture:
    def __init__(self, audio_file, chunk_bytes, overlap_bytes=0):
        self.audio_file = audio_file
        self.chunk_bytes = chunk_bytes
        self.overlap_bytes = overlap_bytes
        self.offset = 0
        self._caught_up = False  # Skip old data on first read

    def read_chunk(self):
        if not os.path.exists(self.audio_file):
            return None
        try:
            current_size = os.path.getsize(self.audio_file)
        except OSError:
            return None

        # On first reads, skip to the end of existing data to avoid processing old audio
        if not self._caught_up:
            if current_size >= self.chunk_bytes:
                self.offset = current_size - self.chunk_bytes
                self._caught_up = True
                log("CAPTURE", f"Skipping to end of existing data (offset={self.offset})")
            else:
                return None  # File too small, wait for more data

        if current_size < self.offset:
            self.offset = 0
        if current_size < self.offset + self.chunk_bytes:
            return None
        try:
            with open(self.audio_file, 'rb') as f:
                f.seek(self.offset)
                data = f.read(self.chunk_bytes)
            self.offset += self.chunk_bytes - self.overlap_bytes
            return data
        except OSError:
            return None


# ============================================================
# WHISPER TRANSCRIPTION (faster-whisper, CUDA)
# ============================================================
class Transcriber:
    def __init__(self, model_name, device="cuda", compute_type="float16"):
        os.environ['HF_HUB_DISABLE_TELEMETRY'] = '1'
        os.environ['XDG_CACHE_HOME'] = '/home/krisr/.local/share/whisper'
        cuda = '/home/krisr/.local/share/whisper-venv/lib/python3.12/site-packages/nvidia/cublas/lib'
        cudnn = '/home/krisr/.local/share/whisper-venv/lib/python3.12/site-packages/nvidia/cudnn/lib'
        nvrtc = '/home/krisr/.local/share/whisper-venv/lib/python3.12/site-packages/nvidia/cuda_nvrtc/lib'
        ld = os.environ.get('LD_LIBRARY_PATH', '')
        os.environ['LD_LIBRARY_PATH'] = f"{cuda}:{cudnn}:{nvrtc}:{ld}"

        from faster_whisper import WhisperModel
        log("STT", f"Loading {model_name} ({device}/{compute_type})...")
        self.model = WhisperModel(model_name, device=device, compute_type=compute_type)
        log("STT", "Model loaded")

    def transcribe_pcm(self, pcm_data, sample_rate=16000):
        tmp_wav = f"/tmp/cochran/chunk_{int(time.time()*1000)}.wav"
        try:
            with wave.open(tmp_wav, 'wb') as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(sample_rate)
                wf.writeframes(pcm_data)
            segments, info = self.model.transcribe(
                tmp_wav, beam_size=5, language='en',
                vad_filter=True, vad_parameters=dict(min_silence_duration_ms=500)
            )
            text = ' '.join(seg.text.strip() for seg in segments)
            return text.strip()
        except Exception as e:
            log("STT", f"Error: {e}")
            return ""
        finally:
            if os.path.exists(tmp_wav):
                os.remove(tmp_wav)


# ============================================================
# LLM THINKING (Ollama API - free, local)
# ============================================================
class Thinker:
    SYSTEM_PROMPT = """You are Cochran - a legal strategy AI providing tactical guidance during a conciliation call.

Be ice cold. Measured. Strategic. Never reactive.
Never use asterisks, markdown, bullet points, or special characters. Speak in plain English only.
Say as much as the situation demands — no more, no less. Brevity is precision, not limitation.
If a tactical point requires expansion, expand. If one word suffices, deliver one.

Case context: Configure in case_context.py
- See case_context.example.py for template

Ice cold. Plain English. No asterisks. Tactical. As much as needed, as few words as possible."""

    def __init__(self, model_id):
        self.model_id = model_id
        self.conversation = []

    def think(self, transcript):
        if not transcript or len(transcript) < 5:
            return None

        self.conversation.append({"role": "user", "content": f"Heard: \"{transcript}\""})
        if len(self.conversation) > 20:
            self.conversation = self.conversation[-20:]

        payload = json.dumps({
            "model": self.model_id,
            "messages": [
                {"role": "system", "content": self.SYSTEM_PROMPT},
                *self.conversation
            ],
            "stream": False,
            "think": False,
            "options": {
                "num_predict": LLM_MAX_TOKENS,
                "temperature": LLM_TEMPERATURE
            }
        })

        try:
            req = urllib.request.Request(
                f"http://{LLM_API_HOST}:{LLM_API_PORT}{LLM_API_PATH}",
                data=payload.encode('utf-8'),
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=60) as resp:
                result = json.loads(resp.read().decode('utf-8'))
                response_text = result.get("message", {}).get("content", "").strip()
                if response_text:
                    self.conversation.append({"role": "assistant", "content": response_text})
                return response_text if response_text else None
        except Exception as e:
            log("LLM", f"Error: {e}")
            return None


# ============================================================
# TTS SPEAKING (Chatterbox TTS - voice cloning with Cochran reference)
# Falls back to Kokoro if Chatterbox fails
# ============================================================
class Speaker:
    COCHRAN_REF = "/mnt/b/Models/Chatterbox/cochran-reference-24k.wav"
    CHATTERBOX_BIN = "/home/krisr/.local/bin/chatterbox-tts"
    KOKORO_BIN = "/home/krisr/.local/bin/kokoro-tts"

    def __init__(self, voice="cochran", fallback_voice="af_nicole"):
        self.voice = voice
        self.fallback_voice = fallback_voice
        self.speaking = False  # Track if currently speaking to avoid overlap
        self.use_kokoro = os.path.exists(self.KOKORO_BIN)
        self.use_chatterbox = os.path.exists(self.CHATTERBOX_BIN)
        os.makedirs(TTS_OUTPUT_DIR, exist_ok=True)
        os.makedirs('/mnt/b/cochran_tmp', exist_ok=True)
        # Pre-load Kokoro into memory for fast TTS
        self.kokoro_pipeline = None
        if self.use_kokoro:
            log("TTS", f"Loading Kokoro ({self.fallback_voice}) into memory...")
            try:
                import sys
                sys.path.insert(0, '/home/krisr/.local/share/kokoro-venv/lib/python3.12/site-packages')
                from kokoro import KPipeline
                import numpy as np
                import soundfile as sf
                self.np = np
                self.sf = sf
                self.kokoro_pipeline = KPipeline(lang_code='a', repo_id='hexgrad/Kokoro-82M')
                log("TTS", f"Kokoro loaded and ready ({self.fallback_voice})")
            except Exception as e:
                log("TTS", f"Kokoro load failed: {e}, falling back to subprocess")
                self.kokoro_pipeline = None

    def speak_and_release(self, text):
        """Speak and release the speaking lock after audio finishes playing."""
        try:
            self.speak(text)
            # Play() is async - audio keeps playing after speak() returns
            # Calculate duration from text length and wait for it to finish
            if text:
                # Rough: ~150 words/min = ~2.5 words/sec = ~12 chars/sec for English
                audio_duration = max(len(text) / 12, 1.5)  # at least 1.5s
                log("TTS", f"Waiting {audio_duration:.1f}s for audio to finish playing")
                time.sleep(audio_duration)
        finally:
            self.speaking = False
            log("TTS", "Speaking lock released")

    def speak(self, text):
        if not text or len(text) < 3:
            return

        timestamp = int(time.time() * 1000)
        wav_path = f"{TTS_OUTPUT_DIR}/cochran_{timestamp}.wav"

        try:
            # Generate TTS — in-memory Kokoro if loaded, else subprocess
            if self.kokoro_pipeline is not None:
                # In-memory Kokoro (fast, ~1-2s)
                generator = self.kokoro_pipeline(text, voice=self.fallback_voice, speed=1.0)
                chunks = []
                for gs, ps, audio in generator:
                    chunks.append(audio)
                if chunks:
                    full_audio = self.np.concatenate(chunks)
                    self.sf.write(wav_path, full_audio, 24000)
                    log("TTS", f"Generated in-memory: {len(full_audio)/24000:.1f}s")
                else:
                    log("TTS", "Kokoro produced no audio")
                    return
            elif self.use_kokoro:
                # Subprocess Kokoro (slower, ~7s cold start)
                result = subprocess.run(
                    [self.KOKORO_BIN, text, wav_path, self.fallback_voice],
                    capture_output=True, text=True, timeout=30
                )
            else:
                log("TTS", "No TTS engine available")
                return

            if not os.path.exists(wav_path):
                log("TTS", "Failed to generate audio")
                return

            # Copy to Windows-accessible path for playback
            import shutil
            win_tmp = f'/mnt/b/cochran_tmp/cochran_{timestamp}.wav'
            shutil.copy2(wav_path, win_tmp)

            # Play audio — uses PowerShell SoundPlayer which plays to Windows default device
            # For Webex to hear Cochran: set Windows default playback to "CABLE Input (VB-Audio Virtual Cable)"
            # For the client to hear Cochran locally: set default to Yealink headset
            # The dashboard can show which mode is active
            win_path = f'B:\\cochran_tmp\\cochran_{timestamp}.wav'
            powershell = '/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe'
            # Play() is async - returns immediately while audio plays
            play_cmd = [
                powershell, '-c',
                f"(New-Object System.Media.SoundPlayer '{win_path}').Play()"
            ]
            result = subprocess.run(play_cmd, capture_output=True, text=True, timeout=15)
            log("TTS", f"Spoke: {text[:60]}...")

            # Wait for audio to finish playing before releasing speaking lock
            audio_duration = len(text) / 10  # rough estimate: ~10 chars per second
            time.sleep(min(audio_duration, 5))  # wait up to 5s before cleanup
            if os.path.exists(win_tmp):
                os.remove(win_tmp)
            if os.path.exists(wav_path):
                os.remove(wav_path)

        except subprocess.TimeoutExpired:
            log("TTS", "Timeout generating/playing audio")
        except Exception as e:
            log("TTS", f"Error: {e}")


# ============================================================
# MAIN PIPELINE
# ============================================================
def main():
    parser = argparse.ArgumentParser(description="Cochran - Listen > Think > Speak")
    parser.add_argument("--whisper-model", default=WHISPER_MODEL_DEFAULT)
    parser.add_argument("--whisper-device", default=WHISPER_DEVICE)
    parser.add_argument("--llm", default=LLM_MODEL_DEFAULT)
    parser.add_argument("--voice", default=TTS_VOICE_DEFAULT)
    parser.add_argument("--no-speak", action="store_true", help="Disable TTS (text only)")
    parser.add_argument("--no-think", action="store_true", help="Disable LLM (transcription only)")
    parser.add_argument("--court", action="store_true", help="Courtroom mode: advice is careful, suitable for open court. Speaks aloud.")
    parser.add_argument("--private", action="store_true", help="Private counsel mode: advice is for the client only, NO TTS. Text output only.")
    args = parser.parse_args()

    # Mode logic
    if args.private:
        args.no_speak = True  # Never speak aloud in private mode
        mode_label = "PRIVATE COUNSEL (text only, no TTS)"
    elif args.court:
        mode_label = "COURTROOM (careful advice, speaks aloud)"
    else:
        mode_label = "DEFAULT (speaks aloud)"

    os.makedirs("/tmp/cochran", exist_ok=True)
    os.makedirs(TTS_OUTPUT_DIR, exist_ok=True)

    capture = AudioCapture(AUDIO_FILE, CHUNK_BYTES, overlap_bytes=OVERLAP_BYTES)
    transcriber = Transcriber(args.whisper_model, args.whisper_device,
                              "float16" if args.whisper_device == "cuda" else "int8")
    # Mode-specific system prompts
    if args.court:
        THINKER_PROMPT = """You are Cochran - speaking in open court where ALL parties can hear you.

CRITICAL: Do NOT reveal strategy, weaknesses, or tactical advice. You are on the record.
Your role is to make confident, measured statements that support your client's position.
Never tip off the other side about your strategy.
Never use asterisks, markdown, bullet points or special characters. Plain English only.
Say as much as the situation demands — no more, no less. Brevity is precision, not limitation.
If closing a case requires a paragraph, deliver a paragraph. If one word suffices, deliver one.

                    Case: Configure in case_context.py
                    - Case details configured in case_context.py
                    - Case details configured in case_context.py

Ice cold. Plain English. On the record. As much as needed, as few words as possible."""
    elif args.private:
        THINKER_PROMPT = """You are Cochran - Kris's private legal counsel. NO ONE else can hear this.

Be ice cold. Measured. Strategic. Never reactive.
Never use asterisks, markdown, bullet points or special characters. Plain English only.
Say as much as the situation demands — no more, no less. Brevity is precision, not limitation.
If closing a case requires ten sentences, deliver ten. If one word suffices, deliver one.

You can share ANY strategy, weaknesses, tactical advice. This is privileged.

                    Case: Configure in case_context.py
                    - Case details configured in case_context.py
                    - Case details configured in case_context.py
                    - Case details configured in case_context.py
                    - Case details configured in case_context.py
                    - Case details configured in case_context.py
                    - Case details configured in case_context.py

Ice cold. Tactical. Private counsel. Plain English. As much as needed, as few words as possible."""
    else:
        THINKER_PROMPT = SYSTEM_PROMPT

    thinker = Thinker(args.llm) if not args.no_think else None
    if thinker:
        thinker.SYSTEM_PROMPT = THINKER_PROMPT
    speaker = Speaker(args.voice) if not args.no_speak else None

    transcript_buffer = []
    last_think_time = 0
    THINK_INTERVAL = 4  # seconds between LLM calls (conversational speed)

    log("COCHRAN", "=" * 60)
    log("COCHRAN", "LISTEN > THINK > SPEAK")
    log("COCHRAN", "=" * 60)
    log("COCHRAN", f"Whisper: {args.whisper_model} ({args.whisper_device})")
    log("COCHRAN", f"LLM: {args.llm} (Ollama)")
    log("COCHRAN", f"TTS: {args.voice}" + (" (DISABLED)" if args.no_speak else ""))
    log("COCHRAN", f"Mode: {mode_label}")
    log("COCHRAN", f"Audio: {AUDIO_FILE}")
    log("COCHRAN", f"Chunk: {CHUNK_SECONDS}s, Overlap: {OVERLAP_SECONDS}s")
    log("COCHRAN", f"Audio output: {'Yealink headset' if args.private else 'CABLE Input (Webex)'}")
    log("COCHRAN", "")
    log("COCHRAN", "Waiting for audio data...")
    log("COCHRAN", "  Run cochran_setup.bat on Windows, OR")
    log("COCHRAN", "  Start stream_to_file.bat + set default playback")
    log("COCHRAN", "")

    running = True
    last_mode = 'private'  # Track mode changes for audio switching

    def signal_handler(sig, frame):
        nonlocal running
        log("COCHRAN", "Shutting down...")
        running = False

    signal.signal(signal.SIGINT, signal_handler)

    while running:
        chunk_data = capture.read_chunk()
        if chunk_data is None:
            time.sleep(0.5)
            continue

        # Check silence
        num_samples = len(chunk_data) // 2
        if num_samples > 0:
            samples = struct.unpack('<' + 'h' * min(num_samples, 8000), chunk_data[:16000])
            max_val = max(abs(s) for s in samples)
            vol_pct = max_val / 32767 * 100
            if vol_pct < SILENCE_THRESHOLD:
                continue

        # LISTEN
        text = transcriber.transcribe_pcm(chunk_data)
        if not text or len(text) < 3:
            continue

        skip_phrases = ["thanks for watching", "subscribe", "the end", "thank you", "thank you.", "you", "bye", "bye-bye", "bye bye", "goodbye", "see you next time", "i'll see you next time", "we'll see you next time", "we'll be right back"]
        if text.lower().strip() in skip_phrases:
            continue

        log("HEARD", text)
        transcript_buffer.append(f"[{time.strftime('%H:%M:%S')}] {text}")

        with open(TRANSCRIPT_FILE, 'w') as f:
            f.write('\n'.join(transcript_buffer))

        # READ MODE FROM DASHBOARD
        current_mode = 'private'  # default
        try:
            with open('/tmp/cochran/mode.txt', 'r') as f:
                current_mode = f.read().strip()
        except:
            pass

        # Switch audio device when mode changes
        if current_mode != last_mode:
            log("MODE", f"Switched from {last_mode} to {current_mode}")
            switch_audio_device(current_mode)
            last_mode = current_mode

        # THINK (skip if muted)
        if thinker and (time.time() - last_think_time) >= THINK_INTERVAL and current_mode != 'mute':
            # Use appropriate system prompt based on mode
            if current_mode == 'court':
                thinker.SYSTEM_PROMPT = COURT_PROMPT
            elif current_mode == 'private':
                thinker.SYSTEM_PROMPT = PRIVATE_PROMPT
            else:
                thinker.SYSTEM_PROMPT = SYSTEM_PROMPT

            recent = ' '.join(transcript_buffer[-5:])
            think_start = time.time()
            response = thinker.think(recent)
            think_elapsed = time.time() - think_start
            last_think_time = time.time()

            # Write latency log
            try:
                with open('/tmp/cochran/latency.txt', 'w') as f:
                    f.write(f'{think_elapsed:.1f}s')
            except: pass

            if response:
                cleaned = clean_for_speech(response)
                log("THINK", f"({think_elapsed:.1f}s) [{current_mode.upper()}] {cleaned}")
                with open(RESPONSE_FILE, 'w') as f:
                    f.write(f"[{time.strftime('%H:%M:%S')}] {cleaned}")
                # SPEAK (only if mode allows and not already speaking)
                should_speak = current_mode in ('court', 'default')
                if should_speak and speaker and not speaker.speaking:
                    speaker.speaking = True
                    threading.Thread(target=speaker.speak_and_release, args=(cleaned,), daemon=True).start()

    # Save final transcript
    if transcript_buffer:
        final_path = f"/tmp/cochran/transcript_{time.strftime('%Y%m%d_%H%M%S')}.txt"
        with open(final_path, 'w') as f:
            f.write('\n'.join(transcript_buffer))
        log("COCHRAN", f"Final transcript saved: {final_path}")

    log("COCHRAN", "Pipeline stopped.")


if __name__ == "__main__":
    main()