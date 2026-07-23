#!/usr/bin/env python3
r"""
Cochran Legal Council (CLC) v2.1 — Dual-Source Pipeline
Real-time audio transcription + LLM strategic analysis + TTS output

Architecture (two-source dual capture):
  SOURCE A (other party — Webex audio):
    Webex -> Voicemeeter VAIO Input -> B1 Output -> ffmpeg #1 -> B:\cochran_audio.raw
                                    -> A1 Output -> Yealink Earphone (Kris hears)

  SOURCE B (client — headset mic):
    Yealink Mic -> Voicemeeter Input 1 -> B2 Output -> ffmpeg #2 -> B:\cochran_audio_client.raw
                                        -> Webex microphone (call participants hear Kris)

  OUTBOUND (Cochran speaks into the call):
    Cochran TTS -> Voicemeeter AUX Input -> B2 Output -> Webex microphone

  Two separate audio streams, two transcription feeds, speaker-labeled transcripts.
  Echo suppression (discard Whisper while speaking) applies to BOTH streams.

Usage:
  python3 cochran_live.py --matter test [--private]
  python3 cochran_live.py --matter test [--private] [--court]
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
import importlib.util

# CUDA library paths — MUST be set before faster_whisper/ctranslate2 loads
_CUDA_LIBS = [
    '/home/krisr/.local/share/whisper-venv/lib/python3.12/site-packages/nvidia/cublas/lib',
    '/home/krisr/.local/share/whisper-venv/lib/python3.12/site-packages/nvidia/cudnn/lib',
    '/home/krisr/.local/share/whisper-venv/lib/python3.12/site-packages/nvidia/cuda_nvrtc/lib',
]
_ld = os.environ.get('LD_LIBRARY_PATH', '')
for _p in _CUDA_LIBS:
    if _p not in _ld:
        _ld = f'{_p}:{_ld}'
os.environ['LD_LIBRARY_PATH'] = _ld

# ============================================================
# CONFIG
# ============================================================
# Source A — other party (Webex audio via Voicemeeter B1)
AUDIO_FILE_OTHER = "/mnt/b/cochran_audio.raw"
# Source B — client (Yealink mic via Voicemeeter B2)
AUDIO_FILE_CLIENT = "/mnt/b/cochran_audio_client.raw"

SAMPLE_RATE = 16000
CHANNELS = 1
BYTES_PER_SAMPLE = 2
CHUNK_SECONDS = 6          # 6s chunks — more context, less fragmentation
CHUNK_BYTES = 192000  # 6s * 16kHz * 1ch * 2bytes
PRE_ROLL_CHUNKS = 1
SILENCE_THRESHOLD = 3
OVERLAP_SECONDS = 2          # 2s overlap — smoother transitions
OVERLAP_BYTES = int(OVERLAP_SECONDS * SAMPLE_RATE * CHANNELS * BYTES_PER_SAMPLE)

# Whisper config
WHISPER_MODEL_DEFAULT = "large-v3-turbo"
WHISPER_DEVICE = "cuda"
WHISPER_COMPUTE = "float16"

# LLM config
LLM_MODEL_DEFAULT = "deepseek-v4-flash:cloud"
LLM_API_HOST = "localhost"
LLM_API_PORT = 11434
LLM_API_PATH = "/api/chat"
LLM_MAX_TOKENS = 60
LLM_TEMPERATURE = 0.7

# TTS config
TTS_VOICE_DEFAULT = "cochran"
TTS_OUTPUT_DIR = "/tmp/cochran/tts"
TTS_WIN_OUTPUT_DIR = "/mnt/b/cochran_tmp"
TTS_CABLE_B_INPUT = "Voicemeeter AUX Input (VB-Audio Voicemeeter VAIO)"

# Audio device names (Voicemeeter Banana)
CABLE_A_OUTPUT = "Voicemeeter Out B1 (VB-Audio Voicemeeter VAIO)"
CABLE_B_INPUT = "Voicemeeter AUX Input (VB-Audio Voicemeeter VAIO)"

# Chatterbox / Kokoro
CHATTERBOX_REF = "/home/krisr/.local/share/chatterbox/cochran-reference-24k.wav"
CHATTERBOX_BIN = "/home/krisr/.local/bin/chatterbox-tts"
KOKORO_BIN = "/home/krisr/.local/bin/kokoro-tts"
KOKORO_FALLBACK_VOICE = "am_michael"  # Male voice for Cochran (legal representative)
KOKORO_SHORT_THRESHOLD = 500  # Use Kokoro for most responses, Chatterbox only for very long text

# PowerShell / Windows binaries
POWERSHELL = "/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe"
NIRCMD = "C:\\Users\\krisr\\Documents\\ffmpeg\\nircmd.exe"  # Windows path for PowerShell

# Pipeline state
TRANSCRIPT_FILE = "/tmp/cochran/transcript.txt"
RESPONSE_FILE = "/tmp/cochran/last_response.txt"
TRANSCRIPTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "transcripts")
MATTERS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "matters")

# Speaker labels
SPEAKER_CLIENT = "CLIENT"
SPEAKER_OTHER = "OTHER_PARTY"


def log(tag, msg):
    ts = time.strftime("%H:%M:%S")
    print(f"[{ts}] [{tag}] {msg}", flush=True)


def clean_for_speech(text):
    """Strip markdown and special characters for TTS."""
    import re
    text = re.sub(r'\*{1,2}([^*]+)\*{1,2}', r'\1', text)
    text = re.sub(r'^[-*] ', '', text, flags=re.MULTILINE)
    text = text.replace('_', ' ')
    text = text.replace('"', '')
    text = re.sub(r'[\[\](){}]', '', text)
    text = text.replace('Kris', 'Chris')
    text = text.replace('Crease', 'Chris')
    text = text.replace('Muska', 'Mustka')
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def text_similarity(a, b):
    """Fuzzy similarity between two strings using word overlap ratio."""
    a_words = set(a.lower().split())
    b_words = set(b.lower().split())
    if not a_words or not b_words:
        return 0.0
    intersection = a_words & b_words
    union = a_words | b_words
    return len(intersection) / len(union)


def load_matter(matter_name):
    """Load case context from matters/<name>_context.py"""
    module_name = f"{matter_name}_context"
    file_path = os.path.join(MATTERS_DIR, f"{matter_name}_context.py")
    if not os.path.exists(file_path):
        log("MATTER", f"Context file not found: {file_path}")
        log("MATTER", f"Available matters:")
        for f in os.listdir(MATTERS_DIR) if os.path.isdir(MATTERS_DIR) else []:
            if f.endswith('_context.py') and not f.endswith('.example.py'):
                log("MATTER", f"  - {f.replace('_context.py', '')}")
        sys.exit(1)
    
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    
    log("MATTER", f"Loaded: {matter_name}")
    
    # Get session name if available
    session_name = getattr(module, 'SESSION_NAME', matter_name)
    
    return {
        'private': getattr(module, 'PRIVATE_PROMPT', ''),
        'court': getattr(module, 'COURT_PROMPT', ''),
        'default': getattr(module, 'DEFAULT_PROMPT', ''),
        'commander': getattr(module, 'COMMANDER_PROMPT', ''),
        'session_name': session_name,
    }


# ============================================================
# AUDIO CAPTURE
# ============================================================
class AudioCapture:
    def __init__(self, audio_file, chunk_bytes, overlap_bytes=0, label=""):
        self.audio_file = audio_file
        self.chunk_bytes = chunk_bytes
        self.overlap_bytes = overlap_bytes
        self.label = label
        self.offset = 0
        self._caught_up = False
        self._stall_count = 0
        self._last_size = 0
        self._stall_logged = False

    def read_chunk(self):
        if not os.path.exists(self.audio_file):
            self._stall_count += 1
            if self._stall_count == 1:
                log(f"CAPTURE-{self.label}", f"Audio file not found: {self.audio_file}")
            elif self._stall_count % 60 == 0:
                log(f"CAPTURE-{self.label}", f"Still waiting... ({self._stall_count * 0.5:.0f}s)")
            return None
        try:
            current_size = os.path.getsize(self.audio_file)
        except OSError:
            return None

        if not self._caught_up:
            if current_size >= self.chunk_bytes:
                self.offset = current_size - self.chunk_bytes
                self._caught_up = True
                log(f"CAPTURE-{self.label}", f"Caught up to live audio (offset={self.offset})")
            else:
                return None

        if current_size == self._last_size:
            self._stall_count += 1
            if self._stall_count == 60 and not self._stall_logged:
                log(f"CAPTURE-{self.label}", f"⚠️ Not growing for {self._stall_count * 0.5:.0f}s — ffmpeg may have died")
                self._stall_logged = True
            elif self._stall_count % 240 == 0:
                log(f"CAPTURE-{self.label}", f"⚠️ Still stalled ({self._stall_count * 0.5:.0f}s)")
        else:
            if self._stall_logged:
                log(f"CAPTURE-{self.label}", "✅ Capture resumed!")
            self._stall_count = 0
            self._stall_logged = False

        self._last_size = current_size

        if current_size < self.offset:
            self.offset = 0
            log(f"CAPTURE-{self.label}", "Audio file replaced, resetting to start")
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
        from faster_whisper import WhisperModel
        log("STT", f"Loading {model_name} ({device}/{compute_type})...")
        self.model = WhisperModel(model_name, device=device, compute_type=compute_type)
        log("STT", "Model loaded")

    def transcribe_pcm(self, pcm_data, sample_rate=16000):
        tmp_wav = f"/tmp/cochran/chunk_{int(time.time()*1000)}_{threading.get_ident()}.wav"
        try:
            with wave.open(tmp_wav, 'wb') as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(sample_rate)
                wf.writeframes(pcm_data)
            segments, info = self.model.transcribe(
                tmp_wav, beam_size=5, language='en',
                vad_filter=True, vad_parameters=dict(min_silence_duration_ms=500),
                initial_prompt="Cochran, Legal Council, test, courtroom, conciliation, legal representative, client, other party"
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
# LLM THINKING
# ============================================================
class Thinker:
    def __init__(self, model_id, system_prompt):
        self.model_id = model_id
        self.system_prompt = system_prompt
        self.conversation = []

    def update_prompt(self, prompt):
        self.system_prompt = prompt

    def think(self, speaker_label, transcript):
        if not transcript or len(transcript) < 5:
            return None

        self.conversation.append({"role": "user", "content": f"[{speaker_label}] Heard: \"{transcript}\""})
        if len(self.conversation) > 20:
            self.conversation = self.conversation[-20:]

        payload = json.dumps({
            "model": self.model_id,
            "messages": [
                {"role": "system", "content": self.system_prompt},
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
# TTS SPEAKING
# ============================================================
class Speaker:
    def __init__(self, voice="cochran", fallback_voice=KOKORO_FALLBACK_VOICE):
        self.voice = voice
        self.fallback_voice = fallback_voice
        self.speaking = False
        self.last_spoke_time = 0
        self.use_chatterbox = os.path.exists(CHATTERBOX_BIN)
        self.use_kokoro = os.path.exists(KOKORO_BIN)
        self.chatterbox_ref = CHATTERBOX_REF if os.path.exists(CHATTERBOX_REF) else None
        os.makedirs(TTS_OUTPUT_DIR, exist_ok=True)
        os.makedirs(TTS_WIN_OUTPUT_DIR, exist_ok=True)

        self.kokoro_pipeline = None
        if self.use_kokoro:
            log("TTS", "Loading Kokoro into memory...")
            try:
                import sys as _sys
                _sys.path.insert(0, '/home/krisr/.local/share/kokoro-venv/lib/python3.12/site-packages')
                from kokoro import KPipeline
                import numpy as np
                import soundfile as sf
                self.np = np
                self.sf = sf
                self.kokoro_pipeline = KPipeline(lang_code='a', repo_id='hexgrad/Kokoro-82M')
                log("TTS", f"Kokoro ready ({self.fallback_voice})")
            except Exception as e:
                log("TTS", f"Kokoro load failed: {e}, subprocess fallback available")
                self.kokoro_pipeline = None

    def speak_and_release(self, text):
        try:
            self.speak(text)
        finally:
            self.speaking = False
            self.last_spoke_time = time.time()
            log("TTS", "Speaking lock released")

    def _generate_tts(self, text, wav_path):
        # PRIMARY: Chatterbox with Cochran's cloned voice (slower but authentic)
        if self.use_chatterbox and self.chatterbox_ref:
            log("TTS", f"Using Chatterbox - Cochran clone ({len(text)} chars)")
            try:
                subprocess.run([CHATTERBOX_BIN, text, wav_path, self.chatterbox_ref],
                    capture_output=True, text=True, timeout=300, check=True)
                if os.path.exists(wav_path) and os.path.getsize(wav_path) > 1000:
                    return True
            except subprocess.TimeoutExpired:
                log("TTS", "Chatterbox timeout, falling back to Kokoro")
            except Exception as e:
                log("TTS", f"Chatterbox failed: {e}, falling back to Kokoro")

        # FALLBACK: In-memory Kokoro (fast, male voice)
        if self.kokoro_pipeline is not None:
            log("TTS", f"Fallback: in-memory Kokoro ({len(text)} chars)")
            try:
                generator = self.kokoro_pipeline(text, voice=self.fallback_voice, speed=1.0)
                chunks = []
                for _, _, audio in generator:
                    chunks.append(audio)
                if chunks:
                    full_audio = self.np.concatenate(chunks)
                    self.sf.write(wav_path, full_audio, 24000)
                    return True
            except Exception as e:
                log("TTS", f"In-memory Kokoro failed: {e}")

        # FALLBACK 2: Kokoro subprocess
        if self.use_kokoro:
            try:
                subprocess.run([KOKORO_BIN, text, wav_path, self.fallback_voice],
                    capture_output=True, text=True, timeout=30, check=True)
                return os.path.exists(wav_path)
            except Exception as e:
                log("TTS", f"Kokoro subprocess failed: {e}")

        log("TTS", "No TTS engine produced audio")
        return False

    def _play_to_cable_b(self, win_path):
        # Play WAV to Voicemeeter AUX Input (CABLE-B).
        # Requires Windows default playback set to "Voicemeeter AUX Input" manually.
        # nircmd auto-switch doesn't work on Windows 26200 — skip it, play directly.
        # Restore to Yealink after call is complete (manual).
        play_cmd = [POWERSHELL, '-c', f"(New-Object System.Media.SoundPlayer '{win_path}').PlaySync()"]

        try:
            result = subprocess.run(play_cmd, capture_output=True, text=True, timeout=60)
            if result.returncode != 0:
                log("TTS", f"⚠️ PlaySync failed: {result.stderr}")
            else:
                log("TTS", "Playback finished")
        except subprocess.TimeoutExpired:
            log("TTS", "Timeout playing audio")
        except Exception as e:
            log("TTS", f"Playback error: {e}")

    def speak(self, text):
        if not text or len(text) < 3:
            return

        timestamp = int(time.time() * 1000)
        wav_path = f"{TTS_OUTPUT_DIR}/cochran_{timestamp}.wav"

        try:
            if not self._generate_tts(text, wav_path):
                return

            import shutil
            win_tmp = f'{TTS_WIN_OUTPUT_DIR}/cochran_{timestamp}.wav'
            shutil.copy2(wav_path, win_tmp)
            win_path = f'B:\\cochran_tmp\\cochran_{timestamp}.wav'

            self._play_to_cable_b(win_path)

            time.sleep(0.5)
            if os.path.exists(win_tmp):
                os.remove(win_tmp)
            if os.path.exists(wav_path):
                os.remove(wav_path)
        except Exception as e:
            log("TTS", f"Error: {e}")


# ============================================================
# TRANSCRIPT MANAGER
# ============================================================
class TranscriptManager:
    def __init__(self, session_name):
        self.session_name = session_name
        self.buffer = []
        os.makedirs(TRANSCRIPTS_DIR, exist_ok=True)
        self.live_file = TRANSCRIPT_FILE
        self.response_file = RESPONSE_FILE

    def add_entry(self, speaker, text):
        """Add a transcript entry with speaker label."""
        entry = f"[{time.strftime('%H:%M:%S')}] [{speaker}] {text}"
        self.buffer.append(entry)
        self._write_live()
        return entry

    def _write_live(self):
        """Write to /tmp/cochran/transcript.txt for dashboard."""
        try:
            with open(self.live_file, 'w') as f:
                f.write('\n'.join(self.buffer))
        except:
            pass

    def write_response(self, text):
        """Write LLM response for dashboard."""
        try:
            with open(self.response_file, 'w') as f:
                f.write(f"[{time.strftime('%H:%M:%S')}] {text}")
        except:
            pass

    def save_final(self):
        """Save transcript to transcripts/ folder by session name."""
        if not self.buffer:
            return None
        filename = f"{self.session_name}.txt"
        filepath = os.path.join(TRANSCRIPTS_DIR, filename)
        with open(filepath, 'w') as f:
            f.write(f"Cochran Legal Council — Session: {self.session_name}\n")
            f.write(f"Date: {time.strftime('%Y-%m-%d %H:%M')}\n")
            f.write(f"{'='*60}\n\n")
            f.write('\n'.join(self.buffer))
        log("TRANSCRIPT", f"Saved: {filepath}")
        return filepath


# ============================================================
# MAIN PIPELINE
# ============================================================
def main():
    parser = argparse.ArgumentParser(description="Cochran Legal Council v2.1")
    parser.add_argument("--matter", default="test", help="Matter context to load from matters/ (e.g. test, fwc)")
    parser.add_argument("--whisper-model", default=WHISPER_MODEL_DEFAULT)
    parser.add_argument("--whisper-device", default=WHISPER_DEVICE)
    parser.add_argument("--llm", default=LLM_MODEL_DEFAULT)
    parser.add_argument("--voice", default=TTS_VOICE_DEFAULT)
    parser.add_argument("--no-speak", action="store_true", help="Disable TTS (text only)")
    parser.add_argument("--no-think", action="store_true", help="Disable LLM (transcription only)")
    parser.add_argument("--court", action="store_true", help="Court mode: careful advice, speaks via CABLE-B")
    parser.add_argument("--private", action="store_true", help="Private counsel: text only, no TTS")
    parser.add_argument("--commander", action="store_true", help="Commander: business call mode")
    parser.add_argument("--test-tts", action="store_true", help="Test TTS playback only (no capture/LLM)")
    args = parser.parse_args()

    # Load matter context
    matter = load_matter(args.matter)

    # Mode logic
    if args.private:
        args.no_speak = True
        mode_label = "PRIVATE COUNSEL (text only)"
    elif args.commander:
        mode_label = "COMMANDER (business call via CABLE-B)"
    elif args.court:
        mode_label = "COURT (careful advice via CABLE-B)"
    else:
        mode_label = "DEFAULT (speaks via CABLE-B)"

    os.makedirs("/tmp/cochran", exist_ok=True)
    os.makedirs(TTS_OUTPUT_DIR, exist_ok=True)
    os.makedirs(TRANSCRIPTS_DIR, exist_ok=True)

    # TTS standalone test mode
    if args.test_tts:
        log("COCHRAN", "TTS TEST MODE — speaking test phrase via CABLE-B")
        speaker = Speaker(args.voice)
        test_text = "This is a test of the Cochran Legal Council voice pipeline. If you can hear this, TTS playback is working."
        log("COCHRAN", f"Speaking: {test_text}")
        speaker.speak(test_text)
        log("COCHRAN", "TTS test complete. Check if you heard the audio in the Webex call.")
        return

    # Initialize components
    transcriber = Transcriber(args.whisper_model, args.whisper_device,
                              "float16" if args.whisper_device == "cuda" else "int8")

    # Set initial prompt based on mode
    if args.commander:
        initial_prompt = matter['commander']
    elif args.court:
        initial_prompt = matter['court']
    elif args.private:
        initial_prompt = matter['private']
    else:
        initial_prompt = matter['default']

    thinker = Thinker(args.llm, initial_prompt) if not args.no_think else None
    speaker = Speaker(args.voice)
    transcript_mgr = TranscriptManager(matter['session_name'])

    # Dual-source captures
    capture_other = AudioCapture(AUDIO_FILE_OTHER, CHUNK_BYTES, OVERLAP_BYTES, label="OTHER")
    capture_client = AudioCapture(AUDIO_FILE_CLIENT, CHUNK_BYTES, OVERLAP_BYTES, label="CLIENT")

    last_think_time = 0
    THINK_INTERVAL = 4
    ECHO_SUPPRESSION_COOLDOWN = 45  # Extended to cover Chatterbox generation + playback time

    # Track Cochran's last TTS output for echo matching
    cochran_last_spoken = ""  # The text Cochran last spoke via TTS
    cochran_spoke_until = 0   # Timestamp when echo suppression should expire

    log("COCHRAN", "=" * 60)
    log("COCHRAN", "CLC v2.1 — DUAL-SOURCE LISTEN > THINK > SPEAK")
    log("COCHRAN", "=" * 60)
    log("COCHRAN", f"Matter: {args.matter}")
    log("COCHRAN", f"Session: {matter['session_name']}")
    log("COCHRAN", f"Mode: {mode_label}")
    log("COCHRAN", f"LLM: {args.llm}")
    log("COCHRAN", f"Whisper: {args.whisper_model} ({args.whisper_device})")
    log("COCHRAN", f"Source A (other party): {AUDIO_FILE_OTHER}")
    log("COCHRAN", f"Source B (client): {AUDIO_FILE_CLIENT}")
    log("COCHRAN", f"Transcript: {TRANSCRIPTS_DIR}/{matter['session_name']}.txt")
    log("COCHRAN", "")

    running = True
    last_mode = 'private'

    def signal_handler(sig, frame):
        nonlocal running
        log("COCHRAN", "Shutting down...")
        running = False

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Pre-roll buffers for each source
    pre_roll_other = []
    pre_roll_client = []
    PRE_ROLL_MAX = PRE_ROLL_CHUNKS

    skip_phrases = ['thanks for watching', 'subscribe', 'the end', 'thank you', 'thank you.',
                     'you', 'bye', 'bye-bye', 'bye bye', 'goodbye', 'see you next time',
                     "i'll see you next time", "we'll see you next time", "we'll be right back"]

    while running:
        # Read from BOTH sources each cycle
        for source_label, capture, pre_roll in [
            (SPEAKER_OTHER, capture_other, pre_roll_other),
            (SPEAKER_CLIENT, capture_client, pre_roll_client),
        ]:
            chunk_data = capture.read_chunk()
            if chunk_data is None:
                continue

            # Check silence
            num_samples = len(chunk_data) // 2
            if num_samples > 0:
                # Sample across the entire chunk, not just the first 0.5s
                # Check 8 points spread across the chunk for speech detection
                check_points = 8
                step = max(1, num_samples // check_points)
                check_samples = []
                for i in range(0, num_samples, step):
                    end = min(i + 1000, num_samples)  # 1000 samples per check point
                    chunk_slice = chunk_data[i*2:end*2]
                    if len(chunk_slice) >= 2:
                        slice_samples = struct.unpack('<' + 'h' * (len(chunk_slice)//2), chunk_slice)
                        check_samples.extend(slice_samples)
                max_val = max(abs(s) for s in check_samples) if check_samples else 0
                vol_pct = max_val / 32767 * 100
                if vol_pct < SILENCE_THRESHOLD:
                    pre_roll.append(chunk_data)
                    if len(pre_roll) > PRE_ROLL_MAX:
                        pre_roll.pop(0)
                    continue

            # Speech detected — combine pre-roll + current
            if pre_roll:
                combined = b''.join(pre_roll) + chunk_data
                log(f"HEARD-{source_label}", f"Pre-roll: {len(pre_roll)} chunks + current")
                pre_roll.clear()
            else:
                combined = chunk_data

            # Transcribe
            text = transcriber.transcribe_pcm(combined)
            if not text or len(text) < 3:
                continue

            # Echo suppression — applies to BOTH streams when TTS is active
            if speaker.speaking:
                log('SUPPRESSED', f'Echo suppression active, discarding [{source_label}]: {text[:60]}...')
                continue

            time_since_spoke = time.time() - speaker.last_spoke_time
            if time_since_spoke < ECHO_SUPPRESSION_COOLDOWN:
                log('SUPPRESSED', f'Echo cooldown ({time_since_spoke:.1f}s), discarding [{source_label}]: {text[:60]}...')
                continue

            # Echo matching — compare transcription against what Cochran last said via TTS
            if cochran_last_spoken and time.time() < cochran_spoke_until:
                similarity = text_similarity(text, cochran_last_spoken)
                if similarity >= 0.6:
                    log('COCHRAN-ECHO', f'Echo match ({similarity:.0%}), labeling as COCHRAN: {text[:60]}...')
                    transcript_mgr.add_entry('COCHRAN', text)
                    continue

            if text.lower().strip() in skip_phrases:
                continue

            # Add to transcript with speaker label
            log(f"HEARD-{source_label}", text)
            transcript_mgr.add_entry(source_label, text)

            # Read mode from dashboard
            current_mode = 'private'
            try:
                with open('/tmp/cochran/mode.txt', 'r') as f:
                    current_mode = f.read().strip()
            except:
                pass

            if current_mode != last_mode:
                log("MODE", f"Switched from {last_mode} to {current_mode}")
                last_mode = current_mode

            # Think (skip if muted)
            if thinker and (time.time() - last_think_time) >= THINK_INTERVAL and current_mode != 'mute':
                # Update prompt based on current mode
                if current_mode == 'commander':
                    thinker.update_prompt(matter['commander'])
                elif current_mode == 'court':
                    thinker.update_prompt(matter['court'])
                elif current_mode == 'private':
                    thinker.update_prompt(matter['private'])
                else:
                    thinker.update_prompt(matter['default'])

                recent = ' '.join([e.split('] ', 1)[1] if '] ' in e else e 
                                   for e in transcript_mgr.buffer[-5:]])
                think_start = time.time()
                response = thinker.think(source_label, recent)
                think_elapsed = time.time() - think_start
                last_think_time = time.time()

                try:
                    with open('/tmp/cochran/latency.txt', 'w') as f:
                        f.write(f'{think_elapsed:.1f}s')
                except:
                    pass

                if response:
                    cleaned = clean_for_speech(response)
                    log("THINK", f"({think_elapsed:.1f}s) [{current_mode.upper()}] {cleaned}")
                    transcript_mgr.write_response(cleaned)

                    should_speak = current_mode in ('commander', 'court', 'default') and not args.private and not args.no_speak
                    if should_speak and not speaker.speaking:
                        # Track what Cochran is about to say for echo matching
                        cochran_last_spoken = cleaned
                        cochran_spoke_until = time.time() + 60  # Match window: 60s
                        speaker.speaking = True
                        threading.Thread(target=speaker.speak_and_release, args=(cleaned,), daemon=True).start()

        time.sleep(0.1)  # Small sleep to avoid busy-looping when both sources are silent

    # Save final transcript
    saved = transcript_mgr.save_final()
    if saved:
        log("COCHRAN", f"Transcript saved: {saved}")

    log("COCHRAN", "Pipeline stopped.")


if __name__ == "__main__":
    main()