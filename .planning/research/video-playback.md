# Video Playback Research: Seamless Transitions for Python Kiosk/Signage

**Domain:** Embedded video playback for clinic kiosk with text overlays
**Researched:** 2026-03-04
**Overall confidence:** HIGH (multiple verified sources, well-established ecosystem)

---

## Executive Summary

The current system uses VLC controlled via an RC (remote control) socket interface from Python. This approach is fundamentally fragile: socket communication adds latency, the `clear` + `add` command sequence guarantees a visible gap (black frame) between videos, and VLC's marquee text overlay via RC commands is unreliable and limited. The core problem is architectural -- VLC was designed as a standalone player, not an embeddable library, and its RC interface is a thin debugging/scripting layer never intended for real-time kiosk control.

After researching all major alternatives, **MPV via python-mpv (libmpv)** is the clear winner for this use case. It provides direct in-process library bindings (no socket overhead), native playlist management with prefetch support, flexible text overlays via both PIL image overlays and ASS-formatted OSD, and excellent cross-platform fullscreen support. The migration path from VLC RC to python-mpv is straightforward because the API maps closely to the existing helper functions.

For the specific problem of black frames between video transitions, the best mitigation is a combination of: (1) using mpv's playlist with `prefetch-playlist=yes` for local files, (2) the `keep-open=always` option to hold the last frame, and (3) for the most demanding transitions, pre-concatenating video segments with ffmpeg and using chapter-based seeking.

---

## Table of Contents

1. [Current System Analysis](#current-system-analysis)
2. [Option 1: MPV + python-mpv (RECOMMENDED)](#option-1-mpv--python-mpv-recommended)
3. [Option 2: GStreamer + Python](#option-2-gstreamer--python)
4. [Option 3: Pre-Rendered Single Video with Seeking](#option-3-pre-rendered-single-video-with-seeking)
5. [Option 4: HTML5/Electron/CEF](#option-4-html5electroncef)
6. [Option 5: PyGame/SDL2](#option-5-pygamesdl2)
7. [Option 6: Kivy](#option-6-kivy)
8. [Option 7: FFplay/FFPyPlayer](#option-7-ffplayffpyplayer)
9. [Option 8: Raspberry Pi Specific (OMXPlayer/KMS/DRM)](#option-8-raspberry-pi-specific)
10. [Comparison Matrix](#comparison-matrix)
11. [Recommendation](#recommendation)
12. [Migration Guide from VLC RC to python-mpv](#migration-guide-from-vlc-rc-to-python-mpv)

---

## Current System Analysis

**File:** `controller.py`

### How It Works Now

```
Python -> TCP socket -> VLC RC interface -> VLC playback engine
```

1. VLC is launched as a subprocess with `--extraintf rc --rc-host localhost:9090`
2. Python connects via TCP socket to port 9090
3. Commands like `clear`, `add`, `repeat on/off` are sent as text over the socket
4. Marquee text is controlled via `marq-marquee`, `marq-size`, etc.
5. Video duration is queried via ffprobe (separate subprocess)

### Why It Flickers

The command sequence for switching videos is:
```python
_rc_cmd("clear")          # <-- Playlist emptied. Screen goes BLACK.
_rc_cmd(f"add {video}")   # <-- New video starts loading. BLACK continues.
                          # <-- Video decoder initializes. Still BLACK.
                          # <-- First frame decoded and displayed. Gap over.
```

This `clear` + `add` cycle creates a guaranteed visible gap of 100-500ms of black screen. The 150ms sleep in `_rc_cmd()` adds further latency. There is no way to pre-buffer the next video in this architecture.

### Why Marquee Is Unreliable

VLC's marquee sub-source requires specific initialization order and has race conditions when updated rapidly via RC. The RC interface has no acknowledgment mechanism -- you send a command and hope it worked.

---

## Option 1: MPV + python-mpv (RECOMMENDED)

**Confidence:** HIGH (official docs, PyPI, GitHub, multiple community sources)

### What It Is

[python-mpv](https://github.com/jaseg/python-mpv) is a ctypes-based Python binding for libmpv (the mpv media player library). Unlike VLC's RC socket approach, python-mpv talks directly to mpv's C API in-process -- no sockets, no subprocesses, no serialization overhead.

### Key Advantages Over VLC RC

| Aspect | VLC RC (current) | python-mpv |
|--------|-----------------|------------|
| **Communication** | TCP socket with text parsing | Direct C API via ctypes (in-process) |
| **Latency** | 150ms+ per command | Sub-millisecond |
| **Playlist management** | `clear` + `add` (causes black frames) | `playlist_append()` + `playlist_next()` |
| **Pre-buffering** | Not possible | `prefetch-playlist=yes` |
| **Text overlay** | Unreliable marquee via RC | PIL image overlays OR ASS OSD |
| **Event handling** | Poll socket for response | Native event callbacks + property observers |
| **Threading** | Manual socket management | Built-in event thread, thread-safe API |
| **Error handling** | Parse text responses | Python exceptions |

### Playlist & Seamless Transitions

```python
import mpv

player = mpv.MPV(
    fullscreen=True,
    keep_open='always',        # Hold last frame (no black screen)
    prefetch_playlist=True,    # Pre-buffer next video in playlist
    gapless_audio=True,        # Seamless audio between items
    video_sync='display-resample',  # Sync to display refresh
    idle=True,                 # Stay open when nothing to play
    input_default_bindings=False,   # No keyboard shortcuts (kiosk)
    osc=False,                 # No on-screen controller
    osd_level=0,               # Disable default OSD
)

# Build playlist
player.playlist_append('/path/to/video1.mp4')
player.playlist_append('/path/to/video2.mp4')
player.playlist_pos = 0  # Start playing

# Switch to next video (holds last frame until new video ready)
player.playlist_next()

# Or replace current video (mpv handles transition internally)
player.loadfile('/path/to/video3.mp4', 'replace')

# Loop current video
player.loop_file = 'inf'

# Property observer for end-of-file events
@player.property_observer('eof-reached')
def on_eof(name, value):
    if value:
        handle_video_ended()
```

**Key options for minimizing black frames:**
- `keep-open=always`: Holds the last frame of each video instead of showing black
- `prefetch-playlist=yes`: Pre-buffers the next playlist item (works well for local files)
- `gapless-audio=yes`: Seamless audio transition
- `video-sync=display-resample`: Syncs to display refresh rate, reducing timing artifacts
- `tscale=mitchell`: Fixes black flash issue with gpu-next renderer

### Text Overlays

python-mpv provides **two** overlay mechanisms:

**Method 1: PIL Image Overlays (most flexible)**
```python
from PIL import Image, ImageDraw, ImageFont

overlay = player.create_image_overlay()
img = Image.new('RGBA', (800, 100), (0, 0, 0, 0))  # Transparent
draw = ImageDraw.Draw(img)
font = ImageFont.truetype('DejaVuSans.ttf', 48)
draw.text((10, 10), 'Ascultare...', font=font, fill=(255, 255, 255, 200))
overlay.update(img, pos=(screen_w//2 - 400, screen_h - 120))

# To hide:
overlay.remove()
```

**Method 2: ASS-formatted OSD overlay (simpler for text)**
```python
# Bottom-center text using ASS alignment tag
player.command('osd-overlay', 1, 'ass-events',
    '{\\an2\\fs48\\c&HFFFFFF&}Ascultare...',
    0, 0, 1920, 1080)

# To hide:
player.command('osd-overlay', 1, 'none', '', 0, 0, 0, 0)
```

ASS tag `\an2` = bottom center. `\fs48` = font size 48. `\c&HFFFFFF&` = white.

### macOS Considerations

- mpv on macOS works well with `--vo=gpu` (default) or `--vo=gpu-next`
- Fullscreen works but may need a brief delay: set `player.fullscreen = True` after `wait_until_playing()`
- On macOS, the render API is recommended over window embedding for embedded use cases
- Install via `brew install mpv` (includes libmpv)

### Linux Considerations

- mpv on Linux is rock-solid with Wayland and X11
- `--vo=gpu` with Vulkan or OpenGL backends
- Install: `apt install mpv libmpv-dev` or `brew install mpv`

### Installation

```bash
# macOS
brew install mpv
pip install python-mpv Pillow

# Linux (Debian/Ubuntu)
sudo apt install mpv libmpv-dev
pip install python-mpv Pillow

# Verify
python -c "import mpv; p = mpv.MPV(); print('OK'); p.terminate()"
```

### Sources

- [python-mpv GitHub](https://github.com/jaseg/python-mpv) -- Official repository, actively maintained
- [python-mpv PyPI](https://pypi.org/project/python-mpv/) -- Latest release April 2025
- [mpv Manual](https://mpv.io/manual/master/) -- Official documentation
- [mpv prefetch-playlist issue #7926](https://github.com/mpv-player/mpv/issues/7926) -- Local file prefetching
- [mpv black flash fix #13108](https://github.com/mpv-player/mpv/issues/13108) -- tscale=mitchell fix

---

## Option 2: GStreamer + Python

**Confidence:** MEDIUM (official docs verified, but complex implementation)

### What It Is

GStreamer is a pipeline-based multimedia framework. Its `playbin3` element supports true gapless playback by pre-rolling the next video while the current one plays. Python bindings are available via `gi.repository.Gst` (PyGObject/GObject Introspection).

### Gapless Playback Architecture

GStreamer's gapless design is the most sophisticated of all options:

1. **`about-to-finish` signal**: Emitted when current media is ending
2. **Pre-rolling**: Next video is decoded to PAUSED state with buffers ready
3. **Element reuse**: Decoders stay active, only the source layer swaps
4. **Atomic switching**: Thread-safe handoff with pad block probes

```python
import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst, GLib

Gst.init(None)

playbin = Gst.ElementFactory.make('playbin3', 'player')
playbin.set_property('uri', 'file:///path/to/video1.mp4')

next_videos = ['file:///path/to/video2.mp4', 'file:///path/to/video3.mp4']

def on_about_to_finish(playbin):
    if next_videos:
        next_uri = next_videos.pop(0)
        playbin.set_property('uri', next_uri)

playbin.connect('about-to-finish', on_about_to_finish)
playbin.set_state(Gst.State.PLAYING)

# Text overlay via textoverlay element
# (requires building custom pipeline instead of playbin)
```

### Text Overlays

GStreamer has a native `textoverlay` element (pango-based):

```
filesrc ! decodebin ! textoverlay text="Ascultare..." font-desc="Sans, 48" valignment=bottom halignment=center ! autovideosink
```

Dynamic text updates require either `appsrc` or property changes on the `textoverlay` element at runtime. A project called [video-text-relay](https://github.com/on-three/video-text-relay) demonstrates JSON RPC control of GStreamer text overlays.

### Pros

- **True gapless**: The only option with proper pre-roll architecture
- **Flexible pipeline**: Can add filters, mixers, compositors
- **Mature text overlay**: Native `textoverlay` element with pango rendering
- **Cross-platform**: Works on macOS, Linux, Raspberry Pi

### Cons

- **Complexity**: Building pipelines is significantly harder than mpv's property-based API
- **Python bindings quality**: PyGObject bindings work but are verbose and less Pythonic
- **`about-to-finish` quirks**: Signal fires multiple times for video+audio streams (2x for video-only, 4x for normal AV)
- **Debugging**: Pipeline errors are cryptic; state management is non-trivial
- **Fullscreen**: Requires manual window management or integration with a GUI toolkit
- **Overkill**: For a sequential playlist with text overlays, GStreamer's power adds unnecessary complexity

### Verdict

GStreamer is the **technically best** solution for gapless video but the **worst developer experience** for this use case. Use it only if you need frame-perfect transitions with different codecs/resolutions, or if you're building something more complex than a sequential kiosk player.

### Sources

- [GStreamer Gapless Design](https://gstreamer.freedesktop.org/documentation/additional/design/playback-gapless.html)
- [playbin3 Documentation](https://gstreamer.freedesktop.org/documentation/playback/playbin3.html)
- [textoverlay Documentation](https://gstreamer.freedesktop.org/documentation/pango/textoverlay.html)
- [Python GStreamer Tutorial](https://brettviren.github.io/pygst-tutorial-org/pygst-tutorial.html)

---

## Option 3: Pre-Rendered Single Video with Seeking

**Confidence:** HIGH (standard ffmpeg approach, well-documented)

### What It Is

Instead of switching between separate video files, concatenate all videos into one large MP4 with chapter markers. At runtime, "switch" videos by seeking to the appropriate chapter/timestamp.

### How It Works

**Step 1: Pre-render at build time**
```bash
# Create concat list
cat > concat.txt << EOF
file 'video1.mp4'
file 'video2.mp4'
file 'video3.mp4'
...
file 'video8.mp4'
EOF

# Concatenate (stream copy if same codec/resolution)
ffmpeg -f concat -safe 0 -i concat.txt -c copy combined.mp4
```

**Step 2: Add chapter metadata**
```bash
# Use ffmpeg to add chapter metadata at each video boundary
ffmpeg -i combined.mp4 -i chapters.txt -map_metadata 1 -c copy combined_chapters.mp4
```

**Step 3: Play and seek**
```python
player = mpv.MPV(fullscreen=True, hr_seek='yes')
player.play('combined.mp4')

# "Switch" to video 3 by seeking to its start time
player.seek(video3_start_time, reference='absolute')
```

### Pros

- **Zero transition gap**: Seeking within a single file has no black frame
- **Simpler pipeline**: One file, one player instance, just seek
- **Works with any player**: mpv, VLC, GStreamer all support seeking

### Cons

- **Build step required**: Must re-concatenate whenever videos change
- **All videos must match**: Same codec, resolution, framerate for stream copy
- **Chapter tracking is manual**: ffmpeg's concat demuxer does not natively support chapters (known limitation, [ticket #6468](https://trac.ffmpeg.org/ticket/6468))
- **Looping a segment**: Looping video1 while waiting for trigger requires `--ab-loop-a` and `--ab-loop-b` in mpv, which is fiddly
- **Large file**: All videos in one file, even if only some are needed

### When to Use This

This is the **best secondary strategy** to combine with mpv. For the idle loop (video1 playing continuously), use mpv's normal loop. For the sequential workflow (video2 -> video3 -> ... -> video5), pre-concatenate those into a single file and seek between segments. Hybrid approach eliminates black frames for the critical path.

### Sources

- [ffmpeg concat documentation](https://www.mux.com/articles/stitch-multiple-videos-together-with-ffmpeg)
- [ffmpeg chapter limitation #6468](https://trac.ffmpeg.org/ticket/6468)
- [Joining files with chapters](https://www.caseyliss.com/2021/1/26/joining-files-keeping-chapters-using-ffmpeg)

---

## Option 4: HTML5/Electron/CEF

**Confidence:** MEDIUM (viable but introduces heavy dependencies)

### What It Is

Use a web browser (Chromium) as the video player. HTML5 `<video>` tags with JavaScript control. Can run via Electron, CEF (Chromium Embedded Framework), or pywebview.

### Approach

```html
<video id="player" style="width:100%;height:100%;object-fit:cover" autoplay>
  <source src="video1.mp4" type="video/mp4">
</video>
<div id="overlay" style="position:absolute;bottom:50px;width:100%;text-align:center;
    font-size:48px;color:white;text-shadow:2px 2px 4px black;">
</div>

<script>
const player = document.getElementById('player');
const overlay = document.getElementById('overlay');

// Pre-load next video
const nextVideo = document.createElement('video');
nextVideo.src = 'video2.mp4';
nextVideo.preload = 'auto';

// Seamless switch (still has brief gap)
function switchTo(src) {
    player.src = src;
    player.play();
}

// Text overlay (trivial with HTML/CSS)
function showText(text) {
    overlay.textContent = text;
}
</script>
```

### Python Integration Options

| Option | Status | Notes |
|--------|--------|-------|
| **CEFPython** | UNMAINTAINED | Last release Jan 2021, no Python 3.12+ support |
| **pywebview** | Active | Lightweight, uses system WebView. Limited video control |
| **Electron** | Active | Requires Node.js. Python communicates via IPC/websocket |

### Pros

- **Text overlays are trivial**: HTML/CSS is the best text rendering engine
- **Styling flexibility**: CSS animations, transitions, fonts
- **Familiar technology**: Web development skills apply

### Cons

- **CEFPython is dead**: Last release 2021, does not support Python 3.12+
- **Heavy runtime**: Electron bundles full Chromium (~150MB)
- **Video transitions still have gaps**: HTML5 `<video>` source switching is not gapless
- **Architecture mismatch**: Adds Node.js/JavaScript layer between Python and playback
- **Resource usage**: Chromium is memory-hungry for a simple video kiosk
- **Coordination overhead**: Python needs IPC to control JavaScript video player

### Verdict

**Do not use for this project.** The only advantage (easy text overlays) is solved by python-mpv's PIL overlay or ASS OSD. The disadvantages (dead CEFPython, heavy Electron, IPC complexity, still not gapless) far outweigh the benefits. Web-based approaches make sense for content-heavy signage with HTML templates, not for a sequential video kiosk.

### Sources

- [CEFPython GitHub](https://github.com/cztomczak/cefpython) -- Last release 2021
- [CEFPython Python 3.12 issue #673](https://github.com/cztomczak/cefpython/issues/673) -- No support
- [pywebview](https://pywebview.flowrl.com/) -- Active alternative
- [Electron Kiosk](https://github.com/innovation-system/electron-kiosk)

---

## Option 5: PyGame/SDL2

**Confidence:** MEDIUM (verified documentation, but video playback is weak point)

### What It Is

PyGame is a game development library built on SDL2. It can render video frames to a surface with text overlay capabilities via SDL_ttf font rendering.

### The Problem

PyGame **does not have native video playback**. You must decode video frames yourself using:
- **moviepy** (FFmpeg-based, decodes frame-by-frame)
- **OpenCV** (`cv2.VideoCapture`)
- **ffpyplayer** (FFmpeg Python binding)
- **pyvidplayer2** (pygame-specific video wrapper)

This means you are responsible for:
- Frame timing and synchronization
- Audio playback synchronization
- Seeking
- Hardware acceleration (or lack thereof)

### Example with pyvidplayer2

```python
import pygame
from pyvidplayer2 import Video

pygame.init()
screen = pygame.display.set_mode((1920, 1080), pygame.FULLSCREEN)

video = Video("video1.mp4")
font = pygame.font.Font(None, 48)

while True:
    for event in pygame.event.get():
        pass
    if video.draw(screen, (0, 0)):
        pygame.display.flip()

    # Text overlay
    text_surface = font.render("Ascultare...", True, (255, 255, 255))
    screen.blit(text_surface, (960 - text_surface.get_width()//2, 1000))
    pygame.display.flip()
```

### Pros

- **Text rendering**: Pygame's font system is simple and reliable
- **Full control**: You own every pixel
- **Cross-platform**: SDL2 works everywhere

### Cons

- **No native video**: Must use third-party decoders
- **Manual sync**: Audio/video synchronization is your problem
- **No hardware decode**: Software decoding eats CPU
- **Reinventing the wheel**: You'd be building a video player from scratch
- **No gapless**: No mechanism for pre-buffering next video

### Verdict

**Do not use.** PyGame is excellent for games, terrible for video playback. You'd spend weeks building what mpv provides out of the box.

### Sources

- [pygame SDL2 video docs](https://www.pygame.org/docs/ref/sdl2_video.html)
- [pyvidplayer2 PyPI](https://pypi.org/project/pyvidplayer2/)
- [pygame-video-player](https://github.com/bguliano/pygame-video-player)

---

## Option 6: Kivy

**Confidence:** MEDIUM (official docs verified)

### What It Is

Kivy is a Python GUI framework with a built-in VideoPlayer widget. It can play videos fullscreen with basic controls.

### Capabilities

```python
from kivy.app import App
from kivy.uix.videoplayer import VideoPlayer

class KioskApp(App):
    def build(self):
        player = VideoPlayer(
            source='video1.mp4',
            state='play',
            options={'eos': 'loop', 'fit_mode': 'contain'},
            allow_fullscreen=False,  # Prevent user toggling
        )
        return player
```

### Pros

- **Simple API**: `source`, `state`, `eos` properties
- **Fullscreen**: Built-in support
- **Touch support**: Good for kiosk touchscreens

### Cons

- **No gapless transitions**: Changing `source` causes a visible gap
- **Limited overlay control**: Not designed for dynamic text overlays on video
- **Heavy framework**: Pulls in the entire Kivy UI toolkit for just video playback
- **GStreamer dependency**: Kivy's video provider uses GStreamer on Linux (adds complexity)
- **Fullscreen quirk**: Removes widget from parent, adds to window -- fragile for state management

### Verdict

**Do not use.** Kivy's VideoPlayer is too basic for seamless transitions and too heavy as a dependency for what is essentially a video playlist with text overlay. It does not solve the core problem (gapless switching) and adds Kivy's entire UI framework overhead.

### Sources

- [Kivy VideoPlayer docs](https://kivy.org/doc/stable/api-kivy.uix.videoplayer.html)

---

## Option 7: FFplay/FFPyPlayer

**Confidence:** MEDIUM

### FFplay

`ffplay` is FFmpeg's test media player. It is explicitly described as "a very simple and portable media player" and is **not designed for programmatic control**. There is no API, no IPC, no way to switch videos without restarting the process. **Do not use.**

### FFPyPlayer

[FFPyPlayer](https://pypi.org/project/ffpyplayer/) is a Cython-based Python binding for FFmpeg's libav libraries. It provides:
- Zero-copy frame access
- FFmpeg filter support
- Real-time stream handling
- Latest version 4.5.2 (Oct 2024) with Python 3.13 support

However, FFPyPlayer is a **decoding library**, not a player. It gives you decoded frames (as numpy arrays or textures) that you must display yourself using PyGame, OpenGL, or similar. This means you still need a display layer, which brings you back to the PyGame/SDL2 problems.

### Verdict

FFPyPlayer is useful as a **decode backend** for custom players but is not a standalone solution. If you need custom frame processing (e.g., computer vision on the video), FFPyPlayer + SDL2 would make sense. For a kiosk video player, mpv already handles decoding, display, and synchronization.

### Sources

- [FFPyPlayer PyPI](https://pypi.org/project/ffpyplayer/)
- [FFPyPlayer docs](https://matham.github.io/ffpyplayer/player.html)
- [ffplay documentation](https://ffmpeg.org/ffplay.html)

---

## Option 8: Raspberry Pi Specific

**Confidence:** HIGH (Raspberry Pi Forums, official documentation)

### OMXPlayer: DEPRECATED

OMXPlayer is **dead**. It depends on the OpenMAX API which is deprecated. It does not work on:
- 64-bit Raspberry Pi OS
- KMS GPU driver (default since Bullseye)
- Raspberry Pi 5

**Do not use OMXPlayer for any new project.**

### Recommended Approach for Raspberry Pi

1. **VLC** is now the default player on RPi OS
2. **mpv** works well with V4L2 hardware decode
3. Target general APIs: **DRI/DRM/KMS, V4L2, or libraries that use them (GStreamer, FFmpeg, mpv)**
4. Use **Full KMS** (default) -- most future-proof

For this project, **mpv on Raspberry Pi** with:
```
--vo=gpu
--hwdec=v4l2m2m     # Hardware decode via V4L2
--gpu-context=drm    # Direct rendering (no X11 needed)
```

### Sources

- [RPi accelerated video thread](https://forums.raspberrypi.com/viewtopic.php?t=317511)
- [OMXPlayer deprecation](https://forums.raspberrypi.com/viewtopic.php?t=346146)
- [Raspberry Pi Video Looper](https://videolooper.de/)

---

## Comparison Matrix

| Criterion | MPV + python-mpv | GStreamer | Pre-concat + Seek | HTML5/Electron | PyGame | Kivy | FFPyPlayer |
|-----------|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **Seamless transitions** | Good | Excellent | Excellent | Poor | Poor | Poor | N/A |
| **Text overlay** | Good | Good | Good (via mpv) | Excellent | Good | Poor | N/A |
| **Python integration** | Excellent | Fair | Excellent (via mpv) | Poor | Good | Fair | Good |
| **Fullscreen macOS** | Good | Fair | Good (via mpv) | Good | Good | Fair | N/A |
| **Fullscreen Linux** | Excellent | Good | Excellent | Good | Good | Fair | N/A |
| **Complexity** | Low | Very High | Low | High | Very High | Medium | Very High |
| **Maintenance burden** | Low | High | Low | High | High | Medium | High |
| **Dependencies** | mpv, python-mpv | GStreamer + many plugins | ffmpeg + mpv | Chromium/Electron | pygame + decoder | kivy | ffpyplayer + display |
| **RPi support** | Excellent | Good | Excellent | Poor (heavy) | Fair | Fair | Fair |
| **Dynamic video switching** | Excellent | Good | Poor (fixed at build) | Fair | Poor | Poor | N/A |
| **Active maintenance** | YES | YES | N/A | CEF: NO | YES | YES | YES |

**Ratings:** Excellent > Good > Fair > Poor

---

## Recommendation

### Primary: MPV + python-mpv

Use **MPV via python-mpv** as the sole video playback engine. It solves every problem in the current system:

| Current Problem | MPV Solution |
|----------------|-------------|
| Black frames between videos | `keep-open=always` + `prefetch-playlist` |
| Socket communication complexity | Direct ctypes API, in-process |
| Marquee text unreliability | PIL image overlays or ASS OSD |
| No pre-buffering | `prefetch-playlist=yes` |
| Fragile error handling | Python exceptions + property observers |

### Secondary: Pre-Concatenation for Critical Path

For the sequential workflow (video2 through video5), consider **also** pre-concatenating those videos into a single MP4 with timestamp markers. This gives truly zero-gap transitions for the most visible part of the user experience. Use mpv's `ab-loop` or seek to handle segment navigation.

### Do NOT Use

- **GStreamer**: Overkill complexity for a sequential playlist
- **HTML5/Electron/CEF**: CEFPython is dead, Electron is too heavy
- **PyGame**: No native video, would require building a player from scratch
- **Kivy**: Does not solve the core gapless problem
- **OMXPlayer**: Deprecated, incompatible with modern Pi

---

## Migration Guide from VLC RC to python-mpv

### Mapping Current Functions

```python
# CURRENT (VLC RC)                     # NEW (python-mpv)
# ============================================

# Setup
VLC_PATH = "..."                       # player = mpv.MPV(fullscreen=True, ...)
_launch_vlc()                          # (automatic - mpv starts with MPV())
_rc_connect()                          # (not needed - in-process)

# Play once
def play_video(video):                 def play_video(video):
    _rc_cmd("repeat off")                 player.loop_file = False
    _rc_cmd("clear")                      player.play(os.path.abspath(video))
    _rc_cmd(f"add {video}")               player.wait_for_playback()
    time.sleep(duration + 0.5)

# Play looping
def play_video_loop(video):            def play_video_loop(video):
    _rc_cmd("repeat on")                  player.loop_file = 'inf'
    _rc_cmd("clear")                      player.play(os.path.abspath(video))
    _rc_cmd(f"add {video}")

# Text overlay
def show_marquee(text):                def show_marquee(text):
    _rc_cmd(f"marq-marquee {text}")       overlay.update(render_text(text))
    _rc_cmd("marq-size 48")               # or: player.command('osd-overlay',
    _rc_cmd(...)                           #     1, 'ass-events', f'{{\\an2\\fs48}}{text}')

def hide_marquee():                    def hide_marquee():
    _rc_cmd("marq-marquee  ")             overlay.remove()

# Duration
def get_duration(video):               # player.duration (property, auto-available)
    subprocess.run(["ffprobe", ...])
```

### Estimated Migration Effort

- **Remove**: VLC launch, socket connect, `_rc_cmd()`, ffprobe duration
- **Add**: MPV initialization (~10 lines), overlay helper (~20 lines)
- **Modify**: Each `play_video*()` function (simpler, fewer lines)
- **Total**: ~2-4 hours for a developer familiar with the codebase

---

## Pitfalls & Warnings

### 1. macOS Fullscreen Timing
**Problem:** Setting `fullscreen=True` at MPV init may not work immediately on macOS.
**Fix:** Set it after `wait_until_playing()` or use a 1-second delay.

### 2. Thread Safety with Overlays
**Problem:** python-mpv's event thread can conflict with overlay updates from the main thread.
**Fix:** Use `player.command()` for ASS overlays (thread-safe) or guard PIL overlays with a lock.

### 3. prefetch-playlist Limitations
**Problem:** `prefetch-playlist` was designed for network streams. For local files, it may not behave as expected on all mpv versions.
**Fix:** Test with your specific mpv version. If needed, use the pre-concatenation approach as fallback.

### 4. libmpv Installation on macOS
**Problem:** python-mpv needs libmpv.dylib to be findable.
**Fix:** `brew install mpv` puts it in the right place. Verify with `python -c "import mpv; mpv.MPV()"`.

### 5. ASS OSD vs PIL Overlays
**Problem:** ASS `osd-overlay` requires enabling OSD features that libmpv disables by default.
**Fix:** Initialize with `osd_level=1` or use `enable_osd=True`, or prefer PIL overlays which work regardless.

---

## Open Questions for Implementation

1. **Video codec consistency**: Are all 8 videos the same resolution/framerate/codec? This matters for both mpv playlist transitions and pre-concatenation.
2. **Target hardware**: Is this macOS-only, or will it also run on Linux/RPi?
3. **Text content**: Is marquee text always static strings, or does it need to show dynamic content (e.g., transcription results)?
4. **Overlay timing**: How precisely does the text overlay need to sync with video transitions?
5. **Recovery**: What should happen if mpv crashes? Auto-restart? The current VLC approach has no crash recovery.

---

## Sources Summary

### Primary (HIGH confidence)
- [python-mpv GitHub](https://github.com/jaseg/python-mpv)
- [python-mpv PyPI](https://pypi.org/project/python-mpv/)
- [mpv Manual](https://mpv.io/manual/master/)
- [GStreamer Gapless Design](https://gstreamer.freedesktop.org/documentation/additional/design/playback-gapless.html)
- [GStreamer textoverlay](https://gstreamer.freedesktop.org/documentation/pango/textoverlay.html)

### Secondary (MEDIUM confidence)
- [mpv prefetch-playlist issues](https://github.com/mpv-player/mpv/issues/7926)
- [mpv black flash fix](https://github.com/mpv-player/mpv/issues/13108)
- [RPi video acceleration](https://forums.raspberrypi.com/viewtopic.php?t=317511)
- [FFPyPlayer docs](https://matham.github.io/ffpyplayer/player.html)

### Tertiary (for context)
- [CEFPython status](https://github.com/cztomczak/cefpython)
- [Kivy VideoPlayer](https://kivy.org/doc/stable/api-kivy.uix.videoplayer.html)
- [Raspberry Pi Video Looper](https://videolooper.de/)
