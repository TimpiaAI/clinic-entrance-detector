import time
import threading
import os
import re
import socket
import subprocess
import sys

from flask import Flask
import sounddevice as sd
from scipy.io.wavfile import write
from faster_whisper import WhisperModel
import numpy as np

# --- Video files ---
VIDEO1 = "video1.mp4"
VIDEO2 = "video2.mp4"
VIDEO3 = "video3.mp4"
VIDEO4 = "video4.mp4"
VIDEO5 = "video5.mp4"
VIDEO6 = "video6.mp4"
VIDEO7 = "video7.mp4"
VIDEO8 = "video8.mp4"

trigger_event = threading.Event()

SAMPLE_RATE = 16000
RECORD_TIME = 10

model = WhisperModel("medium", compute_type="int8")

# --- VLC with RC (remote control) interface ---
VLC_PATH = "/Applications/VLC.app/Contents/MacOS/VLC"
RC_PORT = 9090

_rc_sock = None


def _launch_vlc():
    """Launch VLC once with RC interface + its own native fullscreen window."""
    proc = subprocess.Popen([
        VLC_PATH,
        "--fullscreen",
        "--no-video-title-show",
        "--extraintf", "rc",
        "--rc-host", f"localhost:{RC_PORT}",
        "--sub-source=marq",
        "--mouse-hide-timeout=0",
        "--video-on-top",
    ])
    time.sleep(2)
    return proc


def _rc_connect():
    """Connect to VLC's RC socket."""
    global _rc_sock
    _rc_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    _rc_sock.connect(("localhost", RC_PORT))
    _rc_sock.settimeout(2.0)
    try:
        _rc_sock.recv(4096)  # read banner
    except socket.timeout:
        pass


def _rc_cmd(cmd):
    """Send a command to VLC RC and return the response."""
    # Flush any stale data
    _rc_sock.setblocking(False)
    try:
        while _rc_sock.recv(4096):
            pass
    except (BlockingIOError, OSError):
        pass
    _rc_sock.setblocking(True)
    _rc_sock.settimeout(2.0)

    _rc_sock.sendall((cmd + "\n").encode())
    time.sleep(0.15)
    try:
        data = _rc_sock.recv(4096).decode()
        for line in data.split("\n"):
            line = line.strip().lstrip("> ").strip()
            if line and line != cmd:
                return line
        return ""
    except socket.timeout:
        return ""


def get_duration(video):
    """Get video duration in seconds via ffprobe."""
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                video
            ],
            capture_output=True, text=True
        )
        return float(result.stdout.strip())
    except Exception as e:
        print(f"ffprobe failed for {video}: {e}, defaulting to 60s")
        return 60.0


# ---------- playback helpers ----------

def play_video(video):
    """Play a video once, blocking for its full duration."""
    duration = get_duration(video)
    _rc_cmd("repeat off")
    _rc_cmd("clear")
    _rc_cmd(f"add {os.path.abspath(video)}")
    print(f"Playing: {video} ({duration:.1f}s)", flush=True)
    time.sleep(duration + 0.5)


def play_video_for(video, seconds):
    """Play a video (looping) for a fixed number of seconds."""
    _rc_cmd("repeat on")
    _rc_cmd("clear")
    _rc_cmd(f"add {os.path.abspath(video)}")
    print(f"Playing: {video} for {seconds}s", flush=True)
    time.sleep(seconds)


def play_video_loop(video):
    """Start looping a video. Returns immediately."""
    _rc_cmd("repeat on")
    _rc_cmd("clear")
    _rc_cmd(f"add {os.path.abspath(video)}")
    print(f"Looping: {video}", flush=True)


# ---------- marquee (on-screen text) ----------

def show_marquee(text, duration_ms=0):
    """Show text overlay at bottom-center of the video."""
    _rc_cmd(f"marq-marquee {text}")
    _rc_cmd("marq-size 48")
    _rc_cmd("marq-color 16777215")   # 0xFFFFFF
    _rc_cmd("marq-opacity 255")
    _rc_cmd("marq-position 8")       # bottom-center
    _rc_cmd(f"marq-timeout {duration_ms}")


def hide_marquee():
    """Clear the marquee text."""
    _rc_cmd("marq-marquee  ")
    _rc_cmd("marq-timeout 1")


# ---------- idle loop ----------

def idle_loop():
    """Loop VIDEO1 until trigger_event fires."""
    print("Entering idle loop...", flush=True)
    play_video_loop(VIDEO1)
    trigger_event.wait()
    print("Trigger received, leaving idle loop.", flush=True)


# ---------- speech recording + transcription ----------

def speech(language="ro", prompt=None, is_email=False, on_recording_done=None):
    """Record audio and transcribe with Faster Whisper."""
    print("Recording speech...", flush=True)

    audio = sd.rec(
        int(RECORD_TIME * SAMPLE_RATE),
        samplerate=SAMPLE_RATE,
        channels=1,
        dtype="float32",
    )
    sd.wait()

    if on_recording_done:
        on_recording_done()

    max_val = np.max(np.abs(audio))
    if max_val > 0:
        audio = audio / max_val

    write("speech.wav", SAMPLE_RATE, audio)

    kwargs = dict(vad_filter=True)
    if language:
        kwargs["language"] = language
    if prompt:
        kwargs["initial_prompt"] = prompt
    segments, _ = model.transcribe("speech.wav", **kwargs)

    text = ""
    for s in segments:
        text += s.text + " "
    text = text.strip()

    # CNP detection: if mostly digits, strip to digits only
    digits_only = re.sub(r"[^0-9]", "", text)
    if len(digits_only) >= 10:
        text = digits_only
        print("CNP detected:", text, flush=True)
        return text

    if not is_email:
        print("Speech detected:", text, flush=True)
        return text

    # Email reconstruction from messy transcription
    email_attempt = text.lower()
    email_attempt = re.sub(
        r"\s*(punct|dot|\.)\s*(com|ro|net|org|gmail|yahoo)", r".", email_attempt
    )
    email_attempt = re.sub(
        r"\s*(arond|arong|aroon|aronд|arun|arung|at|et|ad|@|a run|a rung)\s*",
        "@",
        email_attempt,
    )
    if "@" in email_attempt and "." in email_attempt.split("@")[-1]:
        parts = email_attempt.split("@")
        local = parts[0].replace(" ", "").rstrip(".")
        domain = parts[1].replace(" ", "").lstrip(".") if len(parts) > 1 else ""
        email_attempt = local + "@" + domain
        email_attempt = re.sub(r"[^a-z0-9@._\-]", "", email_attempt)
        print("Email detected:", email_attempt, flush=True)
        return email_attempt

    print("Speech detected:", text, flush=True)
    return text


# ---------- combined play + STT ----------

def play_video_then_stt(video, language="ro", prompt=None, is_email=False):
    """Play a question video, then loop VIDEO1 while recording + transcribing."""
    play_video(video)
    play_video_loop(VIDEO1)

    show_marquee("Ascultare...")

    result = speech(
        language=language,
        prompt=prompt,
        is_email=is_email,
        on_recording_done=lambda: show_marquee("Procesare..."),
    )

    show_marquee(result, duration_ms=5000)
    time.sleep(3)
    hide_marquee()

    return result


# ---------- main workflow ----------

def workflow():
    while True:
        print("Waiting for webhook...", flush=True)
        trigger_event.clear()
        idle_loop()

        play_video(VIDEO2)

        play_video_then_stt(VIDEO3)
        play_video_then_stt(VIDEO6)
        play_video_then_stt(
            VIDEO7, language="ro", prompt="1 2 3 4 5 6 7 8 9 1 2 3 4"
        )
        play_video_then_stt(
            VIDEO8,
            language="ro",
            prompt="tudor.trocaru arond gmail punct com, radu.popescu arond yahoo punct com, ion.ionescu arond gmail punct com",
            is_email=True,
        )

        play_video(VIDEO4)
        play_video_for(VIDEO1, 5)
        play_video(VIDEO5)
        # Loop back — idle_loop will restart VIDEO1 seamlessly


# ---------- Flask webhook ----------

app = Flask(__name__)


@app.route("/trigger", methods=["POST", "GET"])
def webhook():
    trigger_event.set()
    print("Trigger received", flush=True)
    return {"status": "ok"}


def server():
    app.run(host="0.0.0.0", port=5050)


# ---------- startup ----------

print("Launching VLC...", flush=True)
_vlc_proc = _launch_vlc()
_rc_connect()
print("Connected to VLC RC interface.", flush=True)

threading.Thread(target=server, daemon=True).start()
workflow()
