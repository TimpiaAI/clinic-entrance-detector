# Comparison: Video Playback and STT Engine Options

**Context:** Selecting the best video player and speech-to-text engine for a clinic entrance kiosk running on Raspberry Pi / mini-PC with Romanian language support.

## Part 1: Video Playback Engine

**Recommendation:** MPV via python-mpv because it provides direct Python bindings, superior seamless looping, reliable OSD overlays, and eliminates the fragile socket protocol required by VLC.

### Quick Comparison

| Criterion | VLC (RC Interface) | MPV (python-mpv) | GStreamer | Electron + HTML5 |
|-----------|-------------------|-------------------|-----------|-------------------|
| Python Integration | TCP socket (fragile) | ctypes bindings (native) | GObject introspection | Subprocess / IPC |
| Seamless Looping | Poor (flickers between items) | Good (--loop-file, --seamless-looping) | Good (pipeline restart) | Good (HTML5 loop attr) |
| Text Overlay | Marquee filter (limited) | OSD + ASS format (rich) | textoverlay element | Full HTML/CSS |
| Resource Usage | ~80MB RAM | ~50MB RAM | ~40MB RAM | ~200MB+ RAM (Chromium) |
| Setup Complexity | Low (install VLC) | Low (install libmpv) | High (pipeline syntax) | High (Node.js + Electron) |
| Error Recovery | Manual reconnect | Automatic (in-process) | Complex (pipeline state) | Complex (IPC) |
| RPi Performance | Good | Good | Best (lowest level) | Poor (Chromium overhead) |
| Maturity | Very mature | Mature | Very mature | Mature |
| Kiosk Suitability | Moderate | High | High but complex | High for web UIs |
| Active Maintenance | Yes | Yes (v1.0.8, Apr 2025) | Yes | Yes |

### Detailed Analysis

**VLC via RC Interface (current approach)**
Strengths:
- Already implemented and working
- VLC handles virtually any video format
- Widely installed, well-known

Weaknesses:
- RC interface is a text-based TCP protocol designed for human use, not programmatic control
- Fullscreen flickers when switching between playlist items
- Socket disconnections require manual reconnection logic
- No proper error codes or response parsing
- Requires subprocess management (launch VLC, wait for startup, connect socket)
- Marquee overlay is limited (no rich formatting, positioning quirks)

**MPV via python-mpv (recommended)**
Strengths:
- Direct ctypes bindings to libmpv -- no network layer, no subprocess
- Property observers for event-driven programming (eof-reached, time-pos, etc.)
- OSD supports ASS subtitle format for rich text overlays
- --loop-file=inf with --seamless-looping for gap-free loops
- Well-documented Python API with examples for overlays, playlists, fullscreen
- Active maintenance (v1.0.8, April 2025)
- Lower memory footprint than VLC
- Used in production kiosk projects (raspberry-mpv-kiosk)

Weaknesses:
- Requires libmpv system library (easy to install: apt install libmpv-dev)
- Seamless looping still has minor gaps for some codecs (known mpv issue)
- OSD is less intuitive than HTML/CSS for complex layouts

**GStreamer**
Strengths:
- Lowest-level, best performance
- Most flexible pipeline architecture
- textoverlay element for text display
- Best choice for custom video processing

Weaknesses:
- Pipeline syntax is complex and hard to debug
- Error handling in pipelines is non-trivial
- Overkill for "play video, show text, switch to next video"
- Steeper learning curve
- Less Python-friendly despite GObject bindings

**Electron + HTML5 Video**
Strengths:
- Full HTML/CSS for UI (text, buttons, animations, forms)
- HTML5 video loop attribute works well
- Would be ideal if touchscreen UI is needed later
- Cross-platform

Weaknesses:
- Chromium runtime: 200MB+ RAM, significant CPU overhead
- Introduces Node.js dependency stack
- Overkill for video+text overlay
- Poor fit for Raspberry Pi (resource constrained)
- Complex IPC between Electron and Python backend

### Video Player Verdict

**Choose MPV** for this project. The migration from VLC RC to python-mpv is straightforward and eliminates the single largest source of fragility in the current architecture. Reserve Electron for future if a full touchscreen UI becomes necessary.

---

## Part 2: Speech-to-Text Engine

**Recommendation:** Faster Whisper (medium, int8) because it is the only viable offline STT option with Romanian support. Consider small model with fine-tuning for better speed/accuracy tradeoff on Raspberry Pi.

### Quick Comparison

| Criterion | Faster Whisper | Vosk | Google Cloud STT | Azure Speech | whisper.cpp |
|-----------|---------------|------|------------------|--------------|-------------|
| Romanian Support | Yes (native) | NO MODEL | Yes (ro-RO) | Yes (ro-RO) | Yes (native) |
| Offline | Yes | Yes | No | No | Yes |
| Speed (10s audio, RPi5) | ~15-40s (model dependent) | ~2-3s | ~2s (network) | ~2s (network) | ~20-50s |
| Accuracy (Romanian) | 4.7% WER (fine-tuned medium) | N/A | Good (unquantified) | Good (unquantified) | Same as Whisper |
| Cost | Free | Free | $0.006/15s | $0.01/audio min | Free |
| Internet Required | No | No | Yes | Yes | No |
| Python API | Excellent | Good | Good | Good | Subprocess/bindings |
| Model Size | 75MB - 3GB | 30-130MB | Cloud | Cloud | 75MB - 3GB |
| Custom Prompting | Yes (initial_prompt) | No | Yes (speech contexts) | Yes (phrase list) | Yes (initial_prompt) |
| VAD Filter | Yes (built-in) | Yes | Yes | Yes | Yes |

### Detailed Analysis

**Faster Whisper (recommended)**
Strengths:
- 3-6x faster than PyTorch Whisper for same accuracy
- int8 quantization works on CPU (critical for RPi)
- initial_prompt parameter helps with digit recognition and domain vocabulary
- VAD filter reduces processing of silence
- Fine-tuned Romanian models available on HuggingFace
- Active development, large community

Weaknesses:
- Medium model is slow on Raspberry Pi (~30-40s for 10s audio)
- Small model sacrifices accuracy for speed
- Fine-tuned models need CTranslate2 conversion to use with faster-whisper
- No streaming/real-time mode (batch only)

Best for: This project. Offline, Romanian, customizable, free.

**Vosk**
Strengths:
- Extremely fast (2-3s for 10s audio on RPi)
- Tiny models (30-50MB)
- Real-time streaming capability
- Works on very constrained hardware

Weaknesses:
- NO Romanian language model in official catalog
- Would require training a custom model from scratch
- Lower accuracy than Whisper for multilingual tasks

Best for: Projects with supported languages needing real-time streaming on constrained hardware.

**Google Cloud Speech-to-Text**
Strengths:
- High accuracy for Romanian (Chirp 3 model)
- Fast (network latency only)
- Custom speech adaptation for domain vocabulary
- Streaming and batch modes

Weaknesses:
- Requires internet connectivity (unacceptable for kiosk reliability)
- Per-request cost adds up
- Data privacy concern (audio sent to Google servers)
- Single point of failure (network)

Best for: Cloud-connected applications where accuracy is paramount and cost is acceptable.

**Azure Speech Services**
Strengths:
- Romanian (ro-RO) fully supported with fast transcription
- Custom speech models with plain text and pronunciation data
- Competitive accuracy

Weaknesses:
- Same internet/cost/privacy issues as Google
- More complex SDK setup

Best for: Enterprise environments already invested in Azure ecosystem.

**whisper.cpp**
Strengths:
- C++ implementation, potentially faster on some hardware
- GGML quantization options
- No Python dependency for core inference

Weaknesses:
- Slightly slower than faster-whisper on Raspberry Pi in benchmarks
- Less Pythonic (requires subprocess or ctypes wrapper)
- Smaller community/ecosystem than faster-whisper

Best for: Non-Python projects or when faster-whisper's CTranslate2 has compatibility issues.

### STT Verdict

**Faster Whisper is the only viable choice** given the constraints (offline, Romanian, Python, Raspberry Pi). The real decision is which model size:

- **On a mini-PC (x86, 8GB+ RAM):** Use medium/int8. Best accuracy, acceptable speed.
- **On Raspberry Pi 5 (4-8GB):** Use small/int8 OR a fine-tuned small Romanian model. Medium is too slow.
- **On Raspberry Pi 4 (2-4GB):** Use base/int8. Accuracy will suffer but inference is fast enough.

Consider converting `readerbench/whisper-ro` (fine-tuned small, 12.2% WER) to CTranslate2 format for the best speed/accuracy tradeoff on Raspberry Pi.

## Sources

- python-mpv PyPI: https://pypi.org/project/python-mpv/
- python-mpv GitHub: https://github.com/jaseg/python-mpv
- raspberry-mpv-kiosk: https://git.sr.ht/~jmaibaum/raspberry-mpv-kiosk
- Raspberry Pi seamless looping: https://forums.raspberrypi.com/viewtopic.php?t=274612
- VLC vs MPV: https://www.linuxfordevices.com/tutorials/linux/vlc-vs-mpv
- Faster Whisper: https://github.com/SYSTRAN/faster-whisper
- Vosk models (no Romanian): https://alphacephei.com/vosk/models
- gigant/whisper-medium-romanian: https://huggingface.co/gigant/whisper-medium-romanian
- readerbench/whisper-ro: https://huggingface.co/readerbench/whisper-ro
- Azure Romanian support: https://learn.microsoft.com/en-us/azure/ai-services/speech-service/language-support
- Google Cloud STT languages: https://cloud.google.com/speech-to-text/v2/docs/speech-to-text-supported-languages
- Whisper prompting guide: https://cookbook.openai.com/examples/whisper_prompting_guide
- RPi Whisper benchmarks: https://gektor650.medium.com/audio-transcription-with-openai-whisper-on-raspberry-pi-5-3054c5f75b95
- Open source STT comparison 2025: https://modal.com/blog/open-source-stt
- Edge STT benchmark 2025: https://www.ionio.ai/blog/2025-edge-speech-to-text-model-benchmark-whisper-vs-competitors
