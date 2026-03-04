# Setting Up Claude Code for This Project

Guide to installing and configuring [Claude Code](https://docs.anthropic.com/en/docs/claude-code) to work on this codebase.

## Prerequisites

- Node.js 18+ (Claude Code is an npm package)
- An Anthropic API key **or** a Claude Max/Pro subscription
- This repo cloned locally

## Install Claude Code

```bash
npm install -g @anthropic-ai/claude-code
```

Verify installation:

```bash
claude --version
```

## Authentication

### Option A: API Key

```bash
export ANTHROPIC_API_KEY=sk-ant-...
```

Or add to your shell profile (`~/.zshrc` / `~/.bashrc`).

### Option B: Claude Subscription (Max/Pro)

```bash
claude
# Follow the browser-based OAuth login prompt on first run
```

## Launch

```bash
cd clinic-entrance-detector
claude
```

Claude Code reads the project files and understands the codebase automatically.

## Project-Level Instructions (CLAUDE.md)

Create a `CLAUDE.md` at the project root to give Claude Code persistent context about this project:

```bash
cat > CLAUDE.md << 'EOF'
# Clinic Entrance Detector

## Project Overview
Real-time person detection system using YOLO + BoT-SORT tracking.
Detects clinic entrance events via dual-zone scoring and fires webhooks.

## Tech Stack
- Python 3.11+, Ultralytics YOLO, Supervision, OpenCV
- FastAPI + Uvicorn dashboard with WebSocket updates
- Async webhook delivery with HMAC signing

## Key Files
- `main.py` — entry point, argparse flags
- `config.py` — all settings loaded from `.env` via python-dotenv
- `detector/entry_analyzer.py` — dual-zone scoring algorithm (core logic)
- `detector/person_tracker.py` — YOLO + tracker wrapper
- `detector/zone_config.py` — calibration data model
- `webhook/sender.py` — async webhook queue with retry
- `dashboard/web.py` — FastAPI dashboard + calibration UI
- `botsort_tuned.yaml` — BoT-SORT tracker config with ReID

## Running
```
python3 main.py --show-window --debug-boxes
```

## Conventions
- Config defaults live in `config.py` Settings dataclass AND `load_settings()`
- Every new setting needs: dataclass field, `load_settings()` line, `.env` entry, backward-compat constant
- Detection algorithm in `entry_analyzer.py` uses graduated scoring — don't replace with binary thresholds
- `.env` is tracked in git (no secrets — webhook URL is internal network only)
EOF
```

## Useful Commands Inside Claude Code

Once running, you can ask Claude Code to:

```
# Understand the codebase
> explain how the dual-zone entry detection works
> what happens when a person_entered event fires?

# Make changes
> add a new config setting for max track age
> fix the webhook retry logic to use exponential backoff

# Debug
> why would entry detection miss someone walking slowly?
> the tracker is assigning new IDs to the same person — diagnose

# Run and test
> run the detector with debug boxes enabled
> run the webcam test
```

## Keyboard Shortcuts

| Shortcut | Action |
|---|---|
| `Enter` | Send message |
| `Escape` | Cancel current operation |
| `Ctrl+C` | Exit Claude Code |
| `/help` | Show all commands |
| `/clear` | Clear conversation |
| `/compact` | Summarize conversation to save context |

## MCP Servers (Optional)

Claude Code supports MCP servers for extended capabilities. Useful ones for this project:

### Browser MCP (for testing the dashboard)

```json
// ~/.claude/settings.json
{
  "mcpServers": {
    "browser": {
      "command": "npx",
      "args": ["@anthropic-ai/mcp-server-browser"]
    }
  }
}
```

### Context7 (for up-to-date library docs)

```json
{
  "mcpServers": {
    "context7": {
      "command": "npx",
      "args": ["-y", "@upstash/context7-mcp"]
    }
  }
}
```

## Tips

- **Compact often**: This project has many files. Use `/compact` when context gets long.
- **Be specific**: "Fix the bbox area filter in entry_analyzer.py" works better than "fix the detector".
- **Use debug mode**: `python3 main.py --show-window --debug-boxes` gives visual feedback Claude Code can reason about.
- **Check .env alignment**: When adding settings, remind Claude to update both `config.py` defaults and `.env` values — mismatches between them have caused bugs before.
