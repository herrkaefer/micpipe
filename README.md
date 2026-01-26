# MicPipe

[中文说明](README.zh-CN.md)

## Overview

MicPipe is a small macOS utility that lets you use ChatGPT's web-based voice dictation feature directly within any application.

### Key features
- One key, two modes: **hold to speak** or **click to toggle**
- Press **Esc** during recording to cancel dictation (no paste)
- Optional start/stop sound cue (menu toggle)
- Automatically returns focus to your original app and pastes the text
- If recording starts from ChatGPT, the text stays there (no round‑trip paste)

## Requirements

- macOS 10.14+
- Python 3.11+
- Google Chrome (must enable JavaScript from Apple Events, see below)

## Quick start (uv)

```bash
uv run python main.py
```

## Installation

### 1. Install dependencies

- Python 3.11+
- Google Chrome
- `uv` (Python package manager)

### 2. Configure Chrome (important)

Enable **Allow JavaScript from Apple Events** in Chrome:

1. Open Chrome
2. Go to menu bar: **View** → **Developer** → **Allow JavaScript from Apple Events**
3. Make sure this option is checked ✓

> ⚠️ If you don't see this option, ensure you're using the official Google Chrome (not Chromium).

### 3. Run the app

```bash
uv run python main.py
```

Grant the required permissions when prompted.

## Usage

MicPipe uses the **Fn key** to trigger recording, with two operation modes:

### Hold Mode (hold to speak)

1. **Hold Fn** to start recording (menu bar icon turns red)
2. Speak...
3. **Release Fn** to stop and transcribe
4. Transcribed text is automatically pasted into the original app

### Toggle Mode (click to toggle)

1. **Quick tap Fn** to start recording
2. Speak...
3. **Tap Fn again** to stop and transcribe
4. Transcribed text is automatically pasted into the original app

### Cancel Recording

- Press **Esc** during recording to cancel
- Canceling will not paste any text

### Menu Bar Icon Status

- 🎙️ Microphone icon: Idle
- 🔴 Pulsing red: Recording
- ⚙️ Circle icon: Transcribing

Click the menu item to toggle sound cues.

### Custom Hotkey

The hotkey is currently hardcoded to **Fn** (keycode 63). To change it, edit line 31 in `main.py`:

```python
TRIGGER_KEY_CODE = 63  # Change this value; common keycodes are listed in comments
```

> Changing the hotkey via the menu is not supported.

## Permissions (important)

The following permissions are required on first run:

### 1. Accessibility (required)

- **Purpose**: Listen for Fn hotkey, simulate `Cmd+V` paste
- **Location**: System Settings → Privacy & Security → Accessibility
- Add and enable the terminal app running MicPipe (e.g., Terminal, iTerm2)

### 2. Automation > Google Chrome (required)

- **Purpose**: Control the ChatGPT tab in Chrome via AppleScript
- **Location**: System Settings → Privacy & Security → Automation
- Ensure your terminal app has permission to control Google Chrome

### 3. Microphone (required in Chrome)

- **Purpose**: ChatGPT dictation requires microphone access
- **Location**: Chrome will prompt for permission on first use; click Allow

## How it works (technical)

- Captures the frontmost app at the moment recording starts.
- One hotkey, two behaviors: **Hold Fn** to record (hold mode), **release Fn** to stop (auto transcribe).
- Uses AppleScript/JavaScript to control the ChatGPT tab in Chrome:
  - Click “Dictate” to start
  - Click “Submit Dictation” to stop and retrieve text
  - Click “Stop Dictation” to cancel on Esc
- Restores focus to the original app and simulates `Cmd+V` to paste.
- A short WAV sound is played on start/stop when enabled.

### Why this approach?

We explored several technical paths before settling on the current AppleScript bridge:
- **Option A: CDP (Chrome DevTools Protocol)** — Failed. ChatGPT's anti-bot protection (Cloudflare/Turnstile) detects CDP and triggers verification challenges, preventing regular usage.
- **Option B: Headless Browsers (Puppeteer/Playwright)** — Failed. The main blocker is the **inability to access the microphone** in headless mode, along with bot detection issues.

**The Solution**: Using AppleScript to interact with your daily Google Chrome window.
- **Pros**: It leverages your existing login session and microphone permissions in a real browser environment, effectively bypassing bot detection.
- **Limitation**: Because it relies heavily on macOS-specific AppleScript and Quartz APIs, this project is **not cross-platform**. Implementations for Linux or Windows would require separate developement based on similar automation principles.

## Compatibility

- macOS 10.14+
- Python 3.11+
- Google Chrome
