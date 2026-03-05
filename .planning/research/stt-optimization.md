# STT Optimization Research: Romanian Clinic Entrance System

**Domain:** Speech-to-Text for Romanian medical patient registration kiosk
**Researched:** 2026-03-04
**Overall confidence:** MEDIUM-HIGH (strong ecosystem data, some Romanian-specific gaps)

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Current System Analysis](#current-system-analysis)
3. [Faster Whisper Model Optimization](#1-faster-whisper-model-optimization)
4. [Romanian Fine-Tuned Models](#2-romanian-fine-tuned-models)
5. [Real-Time STT Alternatives](#3-real-time-stt-alternatives)
6. [Specialized Digit Recognition (CNP)](#4-specialized-digit-recognition-cnp)
7. [Email Dictation](#5-email-dictation)
8. [Streaming vs Batch](#6-streaming-vs-batch)
9. [Voice Activity Detection (VAD)](#7-voice-activity-detection-vad)
10. [Noise Handling](#8-noise-handling)
11. [Recommendations](#recommendations)
12. [Implementation Roadmap](#implementation-roadmap)

---

## Executive Summary

The current system uses `faster-whisper` with the generic `medium` model and `int8` quantization, recording fixed 10-second audio clips. This is a reasonable starting point, but there are significant improvements available across every dimension: model selection, recording strategy, post-processing, and noise handling.

**The single highest-impact change is switching from the generic `medium` model to a Romanian fine-tuned model.** The `readerbench/whisper-ro` (fine-tuned whisper-small) achieves 12.2% WER on Common Voice Romanian vs ~33.2% for the base small model -- and it is a *small* model, meaning it runs faster than the current medium model while being dramatically more accurate for Romanian. The `gigant/whisper-medium-romanian` achieves 4.73% WER on Common Voice Romanian, which is exceptional.

**The second highest-impact change is replacing fixed 10-second recording with VAD-based recording** using Silero-VAD, which will eliminate wasted processing time, reduce hallucination risk from silence, and provide a much better user experience.

**The third priority is specialized post-processing pipelines** for CNP digits and email addresses, which have fundamentally different recognition requirements than conversational Romanian.

---

## Current System Analysis

```python
# Current implementation (from controller.py)
SAMPLE_RATE = 16000
RECORD_TIME = 10  # Fixed 10 seconds -- PROBLEM
model = WhisperModel("medium", compute_type="int8")  # Generic, not Romanian-tuned

# CNP handling: regex strip to digits if >=10 digits found
# Email handling: regex post-processing for "arond" -> "@", "punct" -> "."
```

### Current Problems Identified

| Problem | Impact | Severity |
|---------|--------|----------|
| Generic `medium` model, not Romanian-tuned | ~33% WER on Romanian vs ~5% with fine-tuned | CRITICAL |
| Fixed 10-second recording | Wastes time if user finishes early, cuts off if slow | HIGH |
| No noise preprocessing | Clinic entrance is noisy environment | HIGH |
| Hallucination risk on silence | Whisper generates phantom text on empty audio | HIGH |
| `initial_prompt` only applies to first 30s segment | Limited effectiveness for short prompts | MEDIUM |
| Email regex is fragile | Many "arond/arong/aroon" variants needed | MEDIUM |
| No user feedback during recording | User doesn't know when to speak or stop | MEDIUM |

---

## 1. Faster Whisper Model Optimization

### Model Size Comparison for Romanian

| Model | Parameters | Speed (relative) | Expected Romanian WER | Recommendation |
|-------|-----------|-------------------|----------------------|----------------|
| `small` | 244M | 6x faster than large | ~30-33% (base) | Too inaccurate unless fine-tuned |
| `medium` (current) | 769M | 3x faster than large | ~20-25% (base, estimated) | Decent but not optimized |
| `large-v2` | 1550M | 1x baseline | ~15% (Common Voice) | Good accuracy, slow |
| `large-v3` | 1550M | 1x baseline | ~12-13% (estimated, 10-20% better than v2) | Best generic accuracy |
| `large-v3-turbo` | 809M | ~6x faster than large-v3 | ~14-15% (1-2% worse than v3) | Best speed/accuracy tradeoff |

**Confidence:** MEDIUM -- Romanian-specific WER numbers are estimated from readerbench benchmarks and OpenAI's stated 10-20% improvement of large-v3 over large-v2. The readerbench/whisper-ro model card provides the most reliable Romanian data (see Section 2).

### Compute Type for Different Hardware

| Hardware | Best compute_type | Notes |
|----------|------------------|-------|
| Apple Silicon (M1/M2/M3) | `int8` | CTranslate2 runs CPU-only on Mac; int8 is optimal for CPU. No MPS/GPU support in faster-whisper. |
| Intel mini-PC (x86-64) | `int8` | Intel MKL backend in CTranslate2 excels at int8. Best throughput on CPU. |
| NVIDIA GPU | `float16` | 5-6x faster than base Whisper with float16 on CUDA. |
| Intel with GPU (iGPU) | `int8` (CPU) | CTranslate2 does not support Intel iGPU acceleration. Stick with CPU int8. |

**Confidence:** HIGH -- confirmed from faster-whisper GitHub discussions and CTranslate2 documentation.

**Key finding:** The current `compute_type="int8"` is already optimal for both Apple Silicon and Intel CPU targets. No change needed here.

### Distil-Whisper: NOT Suitable

Distil-whisper (distil-large-v3) is **English-only**. Despite claiming multilingual capability, it produces English transcripts even when given non-English input. Do NOT use for Romanian.

**Confidence:** HIGH -- confirmed on HuggingFace model card and multiple community reports.

### large-v3-turbo: Strong Alternative for Generic Model

If staying with a generic (non-fine-tuned) model, `large-v3-turbo` is the best choice. It reduces decoder layers from 32 to 4, achieving ~6x faster inference than large-v3 with only 1-2% accuracy degradation. For Romanian specifically, it may show slightly larger degradation than for high-resource languages, but should still beat `medium`.

**Confidence:** MEDIUM -- turbo performance on Romanian specifically is not benchmarked, but general multilingual performance is well-documented.

---

## 2. Romanian Fine-Tuned Models

This is the most impactful finding. Romanian-specific fine-tuned Whisper models dramatically outperform generic models.

### Available Models

| Model | Base | Romanian WER (CV) | Romanian WER (FLEURS) | Size | Notes |
|-------|------|-------------------|----------------------|------|-------|
| `gigant/whisper-medium-romanian` | whisper-medium | **4.73%** | 19.64% | 769M | Best accuracy, same size as current model |
| `readerbench/whisper-ro` | whisper-small | **12.2%** | 10.9% | 244M | Excellent for its size, trained on Echo dataset (158K samples) |
| `Artanis1551/whisper_romanian` | whisper-small | Unknown | Unknown | 244M | Less documented |
| Base whisper-small | - | 33.2% | 29.8% | 244M | Reference baseline |
| Base whisper-large-v2 | - | 15.8% | 14.4% | 1550M | Reference baseline |

**Confidence:** HIGH -- WER numbers directly from HuggingFace model cards with documented evaluation methodology.

### Critical Comparison from readerbench/whisper-ro

This data is gold -- direct apples-to-apples comparison:

| Dataset | whisper-small (base) | whisper-large-v2 (base) | readerbench/whisper-ro (fine-tuned small) |
|---------|---------------------|------------------------|------------------------------------------|
| Common Voice | 33.2% | 15.8% | **12.2%** |
| FLEURS | 29.8% | 14.4% | **10.9%** |
| VoxPopuli | 28.6% | 14.4% | **9.4%** |
| RSC | 38.6% | 28.5% | **5.4%** |

**A fine-tuned whisper-small BEATS whisper-large-v2 on Romanian.** This means a model 6x smaller and 6x faster outperforms the generic large model. This is the strongest finding of this research.

### Recommendation: Use `gigant/whisper-medium-romanian`

The `gigant/whisper-medium-romanian` model at 4.73% WER on Common Voice is exceptional. Since the current system already uses `medium` size, this is a drop-in improvement that requires:

1. Converting the HuggingFace model to CTranslate2 format
2. Loading it in faster-whisper

```bash
# Conversion command
ct2-transformers-converter \
  --model gigant/whisper-medium-romanian \
  --output_dir whisper-medium-romanian-ct2 \
  --copy_files tokenizer.json preprocessor_config.json \
  --quantization int8
```

```python
# Updated model loading
model = WhisperModel("whisper-medium-romanian-ct2", compute_type="int8")
```

**Fallback option:** If medium is too slow for the target hardware, use `readerbench/whisper-ro` (small-based) converted to CTranslate2 -- still dramatically better than the generic medium model, and 3x faster.

### State-of-the-Art Romanian ASR (2025)

A recent paper (arxiv.org/abs/2511.03361) presents a NVIDIA FastConformer-based Romanian ASR system trained on 2,600 hours of speech, achieving up to 27% relative WER reduction over previous best systems. However, this is an academic system not readily deployable in a faster-whisper pipeline. Worth monitoring for future improvements.

**Confidence:** HIGH for the paper's existence, LOW for practical deployability.

---

## 3. Real-Time STT Alternatives

### Cloud Services

| Service | Romanian Support | Accuracy | Latency | Offline | Cost | Verdict |
|---------|-----------------|----------|---------|---------|------|---------|
| **Google Cloud STT v2** | Yes (Chirp 3) | Good (model adaptation available) | ~300ms streaming | No | $0.006-0.024/15s | Best cloud option for Romanian |
| **Azure Speech Services** | Yes | Good | ~300ms streaming | No | $1/audio hour | Good alternative |
| **Deepgram Nova-3** | Yes (recently added) | Good (>20% WER reduction for Romanian) | <300ms streaming | No | $0.0043/min | Fast, good Romanian support |
| **AssemblyAI Universal** | Likely (99 languages) | Unknown for Romanian | ~300ms | No | $0.0099/min | Unverified for Romanian |

**Confidence:** MEDIUM -- Romanian support confirmed for Google, Azure, Deepgram. AssemblyAI claims 99 languages but Romanian not specifically verified.

### Offline Alternatives

| Engine | Romanian Support | Accuracy | Speed | Size | Verdict |
|--------|-----------------|----------|-------|------|---------|
| **Vosk** | **NO** | N/A | Fast | Small (50MB) | Not viable -- no Romanian model |
| **Whisper.cpp** | Yes (same models) | Same as Whisper | Faster on some CPUs | Same | Alternative runtime, not better accuracy |
| **faster-whisper (current)** | Yes | Best with fine-tuned | Good with int8 | 769M (medium) | Stay with this |

**Confidence:** HIGH -- Vosk's language list is documented; it does not include Romanian.

### Recommendation: Stay Offline with faster-whisper

For a clinic entrance kiosk, offline operation is strongly preferred:
- No internet dependency (reliability)
- No per-request costs (the system runs continuously)
- No data privacy concerns (patient names, CNP numbers)
- Lower latency (no network round-trip)

Cloud services should only be considered if the fine-tuned Whisper models prove insufficient for real-world accuracy.

---

## 4. Specialized Digit Recognition (CNP)

### The Problem

Romanian CNP (Cod Numeric Personal) is a 13-digit number like `1850415123456`. The current system uses `initial_prompt="1 2 3 4 5 6 7 8 9 1 2 3 4"` and strips non-digit characters from the output. This is a reasonable but improvable approach.

### Why Digits Are Hard for Whisper

1. **Whisper writes out numbers as words** -- "unu opt cinci zero patru" instead of "1850415123456"
2. **Romanian digit words are long** -- "treisprezece" (thirteen) could be misheard as similar-sounding words
3. **13 consecutive digits are unnatural speech** -- people rarely say 13 digits without pausing
4. **initial_prompt only affects the first 30 seconds** -- but for 10s recordings this is actually fine

### Improvement Strategies

#### Strategy 1: Better Initial Prompt (Quick Win)
```python
# Current (too generic)
prompt = "1 2 3 4 5 6 7 8 9 1 2 3 4"

# Better: Romanian digit words + example CNP format
prompt = "CNP: 1 8 5 0 4 1 5 1 2 3 4 5 6. Codul numeric personal: unu opt cinci zero patru unu cinci unu doi trei patru cinci sase."
```

**Confidence:** MEDIUM -- prompt engineering helps but has documented limitations.

#### Strategy 2: Post-Processing Pipeline (Recommended)
```python
# Romanian digit word to number mapping
RO_DIGITS = {
    "zero": "0", "unu": "1", "doi": "2", "trei": "3",
    "patru": "4", "cinci": "5", "sase": "6", "sapte": "7",
    "opt": "8", "noua": "9",
    # Common mishearings
    "o": "0", "un": "1", "una": "1",
    "sașe": "6", "șase": "6", "șapte": "7",
    "nouă": "9",
}

def extract_cnp(text):
    """Extract 13-digit CNP from transcribed Romanian text."""
    # First: try direct digit extraction
    digits = re.sub(r"[^0-9]", "", text)
    if len(digits) == 13:
        return digits

    # Second: convert Romanian digit words to numbers
    words = text.lower().split()
    digit_str = ""
    for word in words:
        cleaned = word.strip(".,;:!?")
        if cleaned in RO_DIGITS:
            digit_str += RO_DIGITS[cleaned]
        elif cleaned.isdigit():
            digit_str += cleaned

    if len(digit_str) == 13:
        return digit_str

    # Third: CNP validation (first digit 1-8, valid date, etc.)
    return validate_cnp_candidates(digit_str)
```

**Confidence:** HIGH -- standard post-processing approach, well-established pattern.

#### Strategy 3: Two-Pass Approach for Critical Data
For CNP numbers (critical data), record twice and compare:
```
1. First recording -> CNP attempt 1
2. "Please repeat your CNP" -> CNP attempt 2
3. If match -> confirmed
4. If mismatch -> show on screen for manual correction
```

**Confidence:** HIGH -- standard UX pattern for critical numeric data.

#### Strategy 4: CNP Checksum Validation
Romanian CNP has a built-in checksum (13th digit is computed from first 12). Use this for validation:

```python
def validate_cnp(cnp_str):
    """Validate Romanian CNP checksum."""
    if len(cnp_str) != 13 or not cnp_str.isdigit():
        return False

    weights = [2, 7, 9, 1, 4, 6, 3, 5, 8, 2, 7, 9]
    total = sum(int(cnp_str[i]) * weights[i] for i in range(12))
    remainder = total % 11
    check = remainder if remainder < 10 else 1
    return check == int(cnp_str[12])
```

**Confidence:** HIGH -- CNP validation algorithm is well-documented.

---

## 5. Email Dictation

### Current Approach Analysis

The current code handles email with regex substitutions for Romanian phonetic variants of "@" and ".":
```python
# "arond/arong/aroon..." -> "@"
# "punct/dot" -> "."
```

This is a reasonable start but fragile. The fundamental problem is that Whisper transcribes "@" as the word "at" (or Romanian equivalent) and "." as "punct" or "dot".

### Known Whisper Limitation

From OpenAI community discussions: "Symbols like @ or + are printed as plain English text instead of symbols." This is a known, unfixed limitation. The @ symbol is consistently transcribed as the word "at" in English and various phonetic equivalents in other languages.

**Confidence:** HIGH -- well-documented issue.

### Improved Email Dictation Pipeline

```python
# Common Romanian ways people say email components
EMAIL_AT_VARIANTS = [
    "arond", "arong", "aroon", "aronд", "arun", "arung",
    "at", "et", "ad", "a rund", "a rond", "la",
    "malpa",  # colloquial
    "coadă de maimuță",  # "monkey tail" -- informal Romanian for @
]

EMAIL_DOT_VARIANTS = [
    "punct", "dot", "point", "punc",
]

COMMON_DOMAINS = {
    "gmail": "gmail.com",
    "yahoo": "yahoo.com",
    "outlook": "outlook.com",
    "hotmail": "hotmail.com",
    "icloud": "icloud.com",
}

def reconstruct_email(text):
    """Multi-stage email reconstruction from Romanian speech."""
    text = text.lower().strip()

    # Stage 1: Direct email pattern detection
    email_match = re.search(r'[\w.+-]+@[\w.-]+\.\w+', text)
    if email_match:
        return email_match.group(0)

    # Stage 2: Replace phonetic variants
    for variant in EMAIL_AT_VARIANTS:
        text = text.replace(variant, "@")
    for variant in EMAIL_DOT_VARIANTS:
        text = re.sub(rf'\s*{variant}\s*', '.', text)

    # Stage 3: Remove spaces, clean up
    # ... (keep existing logic but expanded)

    # Stage 4: Domain autocomplete
    parts = text.split("@")
    if len(parts) == 2:
        domain = parts[1].strip()
        for short, full in COMMON_DOMAINS.items():
            if domain.startswith(short) and "." not in domain:
                domain = full
                break
        return parts[0].replace(" ", "") + "@" + domain

    return text
```

### Better UX Approach: Spell-Out Mode

For emails, the most reliable approach is **character-by-character spelling** with a specialized prompt:

```python
# Prompt that encourages letter-by-letter dictation
email_prompt = (
    "a b c d e f g h i j k l m n o p q r s t u v w x y z "
    "arond gmail punct com, tudor punct popescu arond yahoo punct com"
)
```

Combined with a UI instruction like: "Spell your email letter by letter. Say 'arond' for @ and 'punct' for dot."

**Confidence:** MEDIUM -- this is a UX design recommendation, effectiveness depends on user compliance.

---

## 6. Streaming vs Batch

### Current Approach: Batch (Record-then-Transcribe)

```
Record 10s -> Save WAV -> Transcribe -> Display result
Total latency: 10s recording + 2-5s transcription = 12-15s
```

### Streaming Option: Real-Time Feedback

Whisper was NOT designed for streaming. Community workarounds exist but introduce:
- Boundary errors at chunk transitions
- 3.3 seconds latency at best (whisper_streaming project)
- Operational complexity

**However**, for this kiosk use case, streaming is not the right solution. The key improvement is not streaming -- it is VAD-based recording (see Section 7).

### Recommended Approach: VAD-Terminated Batch

```
Start recording -> VAD detects speech end -> Stop recording -> Transcribe
Total latency: actual_speech_time + 0.5s_silence_buffer + 2-3s transcription
```

For a typical 3-5 second utterance (a name or CNP), total latency drops to 4-6 seconds vs the current 12-15 seconds. This is a **60% latency reduction** without any streaming complexity.

**Confidence:** HIGH -- well-established pattern, Silero-VAD is proven technology.

---

## 7. Voice Activity Detection (VAD)

### Why Fixed 10-Second Recording is Bad

1. **User finishes in 3 seconds** -- 7 seconds of silence processed, hallucination risk
2. **User needs 12 seconds** -- cut off mid-sentence
3. **No feedback** -- user doesn't know when recording started/stopped
4. **Whisper hallucinates on silence** -- generates phantom text from empty audio (well-documented issue)

### VAD Comparison

| Engine | Accuracy (TPR@5%FPR) | Latency | Size | License | Python Support | Recommendation |
|--------|----------------------|---------|------|---------|---------------|----------------|
| **Silero-VAD** | 87.7% | ~1ms/30ms chunk | 1.8MB | MIT | Excellent (PyTorch/ONNX) | **Use this** |
| **WebRTC VAD** | 50% | Very low | Tiny | BSD | Good (py-webrtcvad) | Too inaccurate |
| **Picovoice Cobra** | ~99% | 0.005 RTF | Small | Commercial | Good | Overkill + paid license |

**Confidence:** HIGH -- benchmarks from Picovoice's VAD benchmark framework (github.com/Picovoice/voice-activity-benchmark).

### Recommended: Silero-VAD v5

Silero-VAD is the clear winner for this use case:
- Trained on 6000+ languages (Romanian implicitly supported)
- 1.8MB model, runs on any hardware
- ~1ms processing per 30ms audio chunk
- Already used in many Whisper pipelines
- MIT licensed
- PyTorch is already a dependency (via faster-whisper/CTranslate2)

### Implementation Pattern

```python
import torch
import sounddevice as sd
import numpy as np

# Load Silero-VAD
vad_model, utils = torch.hub.load(
    'snakers4/silero-vad', 'silero_vad', onnx=True
)
(get_speech_timestamps, _, read_audio, _, _) = utils

SAMPLE_RATE = 16000
CHUNK_DURATION = 0.03  # 30ms chunks for VAD
CHUNK_SIZE = int(SAMPLE_RATE * CHUNK_DURATION)
SILENCE_THRESHOLD = 1.5  # seconds of silence before stopping
MAX_RECORD_TIME = 15  # absolute maximum

def record_with_vad():
    """Record audio until speech ends (detected by VAD)."""
    audio_chunks = []
    silence_duration = 0
    speech_detected = False

    stream = sd.InputStream(
        samplerate=SAMPLE_RATE,
        channels=1,
        dtype='float32',
        blocksize=CHUNK_SIZE,
    )

    with stream:
        while True:
            chunk, _ = stream.read(CHUNK_SIZE)
            audio_chunks.append(chunk.copy())

            # Check VAD
            tensor = torch.FloatTensor(chunk.squeeze())
            speech_prob = vad_model(tensor, SAMPLE_RATE).item()

            if speech_prob > 0.5:
                speech_detected = True
                silence_duration = 0
            elif speech_detected:
                silence_duration += CHUNK_DURATION

            # Stop conditions
            total_duration = len(audio_chunks) * CHUNK_DURATION
            if speech_detected and silence_duration > SILENCE_THRESHOLD:
                break
            if total_duration > MAX_RECORD_TIME:
                break

    return np.concatenate(audio_chunks)
```

### faster-whisper's Built-in vad_filter

The current code already uses `vad_filter=True` in the transcribe call. This is the Silero-VAD filter INSIDE faster-whisper that filters out non-speech segments before transcription. **Keep this enabled**, but it is not a substitute for VAD-based recording termination -- it only affects transcription, not recording duration.

**Confidence:** HIGH -- this is a well-understood, well-tested approach.

---

## 8. Noise Handling

### Clinic Entrance Noise Profile

A clinic entrance typically has:
- Door opening/closing sounds (impulsive)
- Conversations from other patients (babble noise)
- Ventilation/HVAC (stationary noise)
- Street noise if doors are open (non-stationary)
- Beeping from medical equipment (tonal)

### Noise Reduction Options

| Solution | Type | Latency | Effectiveness | Complexity | Recommendation |
|----------|------|---------|---------------|------------|----------------|
| **noisereduce** (Python) | Spectral gating | Offline (post-recording) | Good for stationary noise | Low | Good first step |
| **RNNoise** | DNN-based | Real-time (~10ms) | Good general purpose | Medium (C library) | Good for real-time |
| **DeepFilterNet3** | Deep filtering | Near real-time | Best quality overall | Higher (Python) | Best if latency allows |
| **Hardware beamforming** | Microphone array | None (hardware) | Excellent | High (hardware cost) | Best long-term solution |

**Confidence:** MEDIUM -- noise reduction effectiveness is highly dependent on the specific noise environment. Testing required.

### Recommendation: Layered Approach

1. **Hardware:** Use a directional/cardioid USB microphone (not omnidirectional). This alone eliminates much background noise. Cost: $30-80.

2. **Software preprocessing with noisereduce:**
```python
import noisereduce as nr

def preprocess_audio(audio, sample_rate=16000):
    """Apply noise reduction before transcription."""
    # Stationary noise reduction (HVAC, fans)
    reduced = nr.reduce_noise(
        y=audio,
        sr=sample_rate,
        stationary=True,
        prop_decrease=0.75,  # Don't over-reduce
    )
    return reduced
```

3. **Whisper's built-in robustness:** Whisper is already reasonably noise-robust for moderate noise levels. The fine-tuned Romanian models trained on Common Voice data include some natural noise variation.

4. **VAD as noise filter:** Silero-VAD naturally ignores non-speech noise periods, so combined with the VAD-based recording, many noise segments are excluded automatically.

### What NOT to Do

- Do NOT use aggressive noise reduction that distorts speech -- this can REDUCE Whisper accuracy
- Do NOT try real-time beamforming in software without a microphone array
- Do NOT over-engineer this before testing the fine-tuned Romanian model in the actual environment

**Confidence:** HIGH for the layered approach; MEDIUM for specific parameter tuning.

---

## 9. Whisper Hallucination Prevention

This deserves its own section because it is a critical production issue.

### The Problem

Whisper generates phantom text on silence or non-speech audio. Common hallucinations include:
- Copyright notices ("Subtitles by the Amara.org community")
- Repeated phrases
- Random words from the training data

### Prevention Stack

1. **VAD-based recording** (Section 7) -- don't feed silence to Whisper
2. **vad_filter=True** in faster-whisper -- filters non-speech inside the audio
3. **Audio energy check** before transcription:
```python
def has_speech(audio, threshold=0.01):
    """Check if audio contains enough energy to be speech."""
    rms = np.sqrt(np.mean(audio**2))
    return rms > threshold
```
4. **hallucination_silence_threshold** parameter in faster-whisper:
```python
segments, _ = model.transcribe(
    "speech.wav",
    vad_filter=True,
    hallucination_silence_threshold=2.0,  # Skip silence > 2s
)
```
5. **Beam size = 1** reduces hallucination (at slight accuracy cost)
6. **Output validation** -- reject outputs that look like hallucinations:
```python
HALLUCINATION_PATTERNS = [
    r"subtitl",
    r"amara\.org",
    r"copyright",
    r"(\b\w+\b)( \1){3,}",  # Repeated words 4+ times
]
```

**Confidence:** HIGH -- hallucination is well-documented and these mitigations are proven.

---

## Recommendations

### Priority 1: Romanian Fine-Tuned Model (CRITICAL -- Do First)

**Action:** Replace `WhisperModel("medium")` with `gigant/whisper-medium-romanian` converted to CTranslate2.

**Expected improvement:** WER from ~20-25% to ~5% on standard Romanian speech.

**Effort:** 1-2 hours (download, convert, test).

**Risk:** Low -- same model architecture, same inference pipeline.

### Priority 2: VAD-Based Recording (HIGH -- Do Second)

**Action:** Replace fixed 10-second recording with Silero-VAD terminated recording.

**Expected improvement:** 60% latency reduction for typical utterances; elimination of hallucination from silence.

**Effort:** 4-6 hours (implement VAD loop, test timing, handle edge cases).

**Risk:** Low-Medium -- need to tune silence threshold for the kiosk environment.

### Priority 3: CNP Post-Processing (HIGH -- Quick Win)

**Action:** Implement Romanian digit word mapping and CNP checksum validation.

**Expected improvement:** Significant improvement in CNP recognition accuracy, immediate feedback on invalid CNPs.

**Effort:** 2-3 hours.

**Risk:** Low.

### Priority 4: Noise Preprocessing (MEDIUM -- Environment Dependent)

**Action:** Add `noisereduce` spectral gating before transcription; consider a directional microphone.

**Expected improvement:** Dependent on actual noise levels. Could be dramatic or minimal.

**Effort:** 1-2 hours for software; hardware requires purchasing microphone.

**Risk:** Low (software); Medium (choosing right hardware).

### Priority 5: Email Pipeline Improvement (MEDIUM)

**Action:** Expand email post-processing with domain autocomplete and more Romanian phonetic variants.

**Expected improvement:** Moderate -- email dictation will always be error-prone.

**Effort:** 2-3 hours.

**Risk:** Low, but may need UX changes (spell-out instructions).

### Priority 6: Hallucination Prevention (MEDIUM -- Quick Win)

**Action:** Add `hallucination_silence_threshold`, energy check, and hallucination pattern detection.

**Expected improvement:** Eliminates phantom text, improves reliability.

**Effort:** 1 hour.

**Risk:** Very low.

---

## Implementation Roadmap

### Phase 1: Quick Wins (Day 1)

```python
# 1. Switch to Romanian fine-tuned model
model = WhisperModel("whisper-medium-romanian-ct2", compute_type="int8")

# 2. Add hallucination prevention
segments, _ = model.transcribe(
    "speech.wav",
    language="ro",
    vad_filter=True,
    hallucination_silence_threshold=2.0,
    initial_prompt=prompt,
)

# 3. Add CNP validation
if is_cnp:
    cnp = extract_cnp(text)
    if validate_cnp(cnp):
        return cnp
    else:
        return "INVALID"  # trigger re-recording
```

### Phase 2: VAD Recording (Day 2-3)

```python
# Replace sd.rec(int(RECORD_TIME * SAMPLE_RATE), ...) with:
audio = record_with_vad(
    max_duration=15,
    silence_threshold=1.5,
    min_speech_duration=0.5,
)
```

### Phase 3: Noise + Polish (Day 4-5)

```python
# Add noise preprocessing
audio = preprocess_audio(audio)

# Improve email pipeline
if is_email:
    email = reconstruct_email(text)
    if validate_email(email):
        return email
```

---

## Sources

### High Confidence (Official Documentation / Model Cards)
- [gigant/whisper-medium-romanian](https://huggingface.co/gigant/whisper-medium-romanian) -- 4.73% WER on Common Voice Romanian
- [readerbench/whisper-ro](https://huggingface.co/readerbench/whisper-ro) -- Benchmark comparison table, 12.2% WER
- [SYSTRAN/faster-whisper GitHub](https://github.com/SYSTRAN/faster-whisper) -- CTranslate2 optimization, compute types
- [Silero-VAD GitHub](https://github.com/snakers4/silero-vad) -- VAD model details, benchmarks
- [OpenAI Whisper GitHub](https://github.com/openai/whisper) -- Model architecture, language support

### Medium Confidence (Verified Web Sources)
- [Picovoice VAD Benchmark 2025](https://picovoice.ai/blog/best-voice-activity-detection-vad-2025/) -- VAD comparison data
- [Northflank Open Source STT Benchmarks 2026](https://northflank.com/blog/best-open-source-speech-to-text-stt-model-in-2026-benchmarks) -- Model comparison
- [Whisper @ symbol issue](https://github.com/openai/whisper/discussions/2320) -- Email dictation limitation
- [faster-whisper int8 vs float16](https://github.com/SYSTRAN/faster-whisper/discussions/173) -- Compute type comparison
- [Deepgram Nova-3 Romanian expansion](https://deepgram.com/learn/deepgram-expands-nova-3-with-11-new-languages-across-europe-and-asia) -- Cloud alternative
- [noisereduce GitHub](https://github.com/timsainb/noisereduce) -- Noise reduction library
- [DeepFilterNet GitHub](https://github.com/Rikorose/DeepFilterNet) -- Advanced noise reduction
- [Romanian SOTA ASR (arxiv)](https://arxiv.org/abs/2511.03361) -- FastConformer Romanian system

### Low Confidence (Single Source / Unverified)
- [Whisper Large V3 Turbo performance on non-English](https://medium.com/axinc-ai/whisper-large-v3-turbo-high-accuracy-and-fast-speech-recognition-model-be2f6af77bdc) -- Turbo accuracy claims
- [Google Cloud STT Romanian](https://cloud.google.com/speech-to-text/v2/docs/speech-to-text-supported-languages) -- Chirp 3 Romanian quality unverified
- [Azure Speech Romanian](https://learn.microsoft.com/en-us/azure/ai-services/speech-service/language-support) -- Romanian quality unverified

---

## Confidence Assessment

| Area | Confidence | Reason |
|------|------------|--------|
| Romanian fine-tuned models | HIGH | Direct WER benchmarks on model cards |
| Compute type optimization | HIGH | Documented in faster-whisper/CTranslate2 |
| VAD approach (Silero-VAD) | HIGH | Well-benchmarked, widely used |
| CNP post-processing | HIGH | Standard algorithm, known Romanian digit words |
| Email dictation | MEDIUM | Fundamental Whisper limitation, no perfect solution |
| Noise handling | MEDIUM | Effectiveness depends on actual environment |
| Cloud alternatives accuracy | LOW-MEDIUM | Romanian quality claims not independently verified |
| Generic model Romanian WER | MEDIUM | Estimated from cross-references, not directly measured |

---

## Open Questions

1. **What is the actual noise level at the clinic entrance?** This determines whether noise reduction is critical or optional. Test the fine-tuned model first without noise reduction.

2. **What hardware will run in production?** Apple Silicon Mac vs Intel mini-PC affects model size decisions. Both work well with int8.

3. **Is there a screen for visual feedback?** The VLC overlay approach works but is limited. A dedicated display for "listening..." / "processing..." / showing recognized text would dramatically improve UX.

4. **How often do users fail to provide correct CNP by voice?** If >30%, consider a touchscreen fallback for CNP entry.

5. **Is the `gigant/whisper-medium-romanian` model license compatible with commercial deployment?** Check the model card's license terms.
