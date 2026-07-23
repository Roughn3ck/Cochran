# STATUS.md — Cochran Legal Council

**Last updated:** 2026-07-24
**Version:** v2.1 — Dual-source architecture with TTS

---

## Current State: ✅ Pipeline Working — Windows Migration Planned

### Verified Working (24 Jul 2026)

- ✅ Dual-source capture (B1 = other party, B2 = client)
- ✅ Speaker differentiation (CLIENT / OTHER_PARTY labels)
- ✅ Whisper CUDA transcription (large-v3-turbo, 6s chunks, 2s overlap)
- ✅ DeepSeek V4 Flash LLM (~1.1-1.7s latency)
- ✅ Dashboard live transcript + strategic notes at http://localhost:8765
- ✅ Mode switching (private/court/default/commander/mute) via dashboard
- ✅ Kokoro TTS → Voicemeeter AUX → A1 (headset) + B2 (Webex mic)
- ✅ Chatterbox TTS — Cochran voice clone (working, ~10-30s latency)
- ✅ Matter loading from `matters/` subfolder
- ✅ Transcript persistence to `transcripts/` folder
- ✅ Echo suppression (45s cooldown + TTS echo matching with [COCHRAN] labels)
- ✅ Two-phase test flow (private → court) with gated transitions
- ✅ Full audio routing: TTS heard on headset, Webex mic, and other party source

### Test Flow (test_context.py)

Two-phase test with explicit gating:
1. **Phase 1 (Private):** Client introduces via headset, other party confirms via phone
2. **Phase 2 (Court):** Cochran tests TTS voice in courtroom context

### Bugs Fixed (24 Jul 2026)

| # | Bug | Fix |
|---|-----|-----|
| 1 | Silence check only sampled first 0.5s of 6s chunk | Sample 8 points across entire chunk |
| 2 | libcublas.so.12 not found | Set LD_LIBRARY_PATH before venv activation |
| 3 | TTS playback silent — WSL PowerShell in Session 1 (no audio access) | Set Windows default to Voicemeeter AUX Input |
| 4 | Voicemeeter AUX had B2 but not A1 — no headset output | Enable A1 on AUX Input column |
| 5 | Chatterbox timeout (120s) on long responses | Increased to 300s timeout |
| 6 | Kokoro used af_nicole (female) as fallback | Changed to am_michael (male) |
| 7 | TTS audio fed back as [CLIENT] — repetition loop | Echo matching: compare transcription vs TTS text, label as [COCHRAN] |
| 8 | ECHO_SUPPRESSION_COOLDOWN too short (3s) for Chatterbox | Extended to 45s |
| 9 | LLM jumped ahead on simple greeting | Step 2 requires name AND matter before confirming |
| 10 | LLM said "test complete" instead of transitioning to court | Phase-based prompt with forbidden phrases |

### What's NOT Done Yet

- [ ] Windows-native pipeline (`windows/cochran_live.py`) — eliminate WSL bridge
- [ ] nircmd replacement — auto-switch Windows default playback device
- [ ] Pipeline hardening — error recovery, crash-survivable logging
- [ ] Chatterbox latency optimization — currently ~10-30s per generation
- [ ] Pure Linux pipeline (`linux/cochran_live.py`)

### Environment Status

| Environment | Status | Notes |
|-------------|--------|-------|
| WSL/ | ✅ Active | Current working setup, bridging to Windows for audio |
| windows/ | 🔧 Planned | Full Windows-native, direct audio device access |
| linux/ | 🔜 Future | Pure Linux, no Voicemeeter dependency |

## Dependencies

| Dependency | Status | Path |
|-----------|--------|------|
| whisper-venv | ✅ | `/home/krisr/.local/share/whisper-venv/` |
| kokoro-venv | ✅ | `/home/krisr/.local/share/kokoro-venv/` |
| chatterbox-venv | ✅ | `/home/krisr/.local/share/chatterbox-venv/` |
| Cochran voice ref | ✅ | `/home/krisr/.local/share/chatterbox/cochran-reference-24k.wav` |
| kokoro-tts binary | ✅ | `/home/krisr/.local/bin/kokoro-tts` |
| chatterbox-tts binary | ✅ | `/home/krisr/.local/bin/chatterbox-tts` |
| Ollama model | ✅ | `deepseek-v4-flash:cloud` via localhost:11434 |
| ffmpeg.exe | ✅ | `C:\Users\krisr\Documents\ffmpeg\ffmpeg.exe` |
| nircmd.exe | ✅ | `C:\Users\krisr\Documents\ffmpeg\nircmd.exe` (not currently used) |