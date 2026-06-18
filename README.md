# ⚖️ Cochran

**If the glove don't fit, you must acquit.**

Legal AI pipeline for real-time phone calls. Listen → Think → Speak. Cochran sits in on live calls — mediation, conciliation, disputes, negotiations — and provides real-time strategic counsel. Part of [The Pack](https://github.com/Roughn3ck/ExecutiveMind) at [Executive Mind](https://executivemind.io).

---

## What This Is

Cochran is a real-time legal AI that listens to your phone calls, thinks through strategy, and speaks counsel into your ear. Built for adversarial contexts — FWC conciliation, family law mediation, tenancy disputes, insurance claims, employment negotiations, any call where you need a second brain.

The pipeline runs entirely on local hardware:

```
Call Audio → VB-Cable → ffmpeg (16kHz PCM)
       ↓
faster-whisper (CUDA STT) → transcript
       ↓
DeepSeek V3.2 (reasoning) → strategic response
       ↓
Kokoro / Chatterbox TTS → voice output
       ↓
VB-Cable → back into the call
```

## What's Here

| File | Purpose |
|------|---------|
| `cochran_live.py` | Main pipeline (Listen → Think → Speak) |
| `dashboard_server.py` | HTTP server for live dashboard |
| `dashboard.html` | Web dashboard with real-time mode switching |
| `stream_to_file.bat` | Windows ffmpeg audio capture |
| `setup_audio.bat` | Audio routing instructions |
| `case_context.example.py` | Template for case-specific prompts |
| `cochran_logo.png` | Logo |
| `cochran_avatar.jpg` | Avatar |

### Modes

| Flag | Mode | Voice | Description |
|------|------|-------|-------------|
| `--private` | 🤐 Private Counsel | ❌ Text only | Full strategy, no holds barred |
| `--court` | ⚖️ Court Open | ✅ Speaks aloud | Careful, on the record |
| `--default` | 🎙️ Default | ✅ Speaks aloud | No restrictions |
| `--no-think` | Transcribe only | ❌ | No LLM, just transcript |
| `--no-speak` | Listen + Think | ❌ | No voice output |

### Latency Budget

| Step | Time |
|------|------|
| Whisper (4s chunk) | ~0.1s |
| DeepSeek V3.2 Cloud | ~2.7s |
| Kokoro TTS (in-memory) | ~1.1s |
| Audio playback | ~0.5s |
| **Total** | **~4.5s** |

## Pack Links

- 🐺 [The Pack](https://github.com/Roughn3ck/ExecutiveMind) — Main org repo
- 🏔️ [Kimi](https://github.com/Roughn3ck/Kimi) — Director & operations
- 🌊 [Slater](https://github.com/Roughn3ck/Slater) — CTO, architecture & blockchain
- 🎨 [Aria](https://github.com/Roughn3ck/Aria) — Web design & brand
- 🔒 [Vault](https://github.com/Roughn3ck/Vault) — Treasury guardian & privacy
- 🔍 [Scout](https://github.com/Roughn3ck/Scout) — Market intelligence
- 🛡️ [Chief](https://github.com/Roughn3ck/Chief) — Security lead
- 😈 [Mischief](https://github.com/Roughn3ck/Mischief) — Red team & pentesting

## License

MIT — See [LICENSE](LICENSE)

---

*If the glove don't fit, you must acquit.* ⚖️