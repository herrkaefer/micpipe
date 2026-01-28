<img src="assets/logo.png" width="256">

# MicPipe 

Current version: `v1.3.0`


[中文](README.zh-CN.md)

## Overview

MicPipe is a small macOS utility that lets you use ChatGPT's web-based voice dictation feature directly within any application.

[📺 Watch Demo Video](demo/demo1.mp4)


### Key features
- **One key, two modes**: **hold to speak** or **click to toggle**
- **Customizable Global Hotkey**: Select your preferred trigger key from the menu (defaults to Fn)
- **Invisible Dedicated Window**: Transcription service runs in a dedicated hidden Chrome window to reduce flickering and interference with your normal browsing
- **Press Esc** during recording to cancel dictation (no paste)
- **State Persistence**: Your settings (chosen service, sound, hotkey) are automatically saved and restored on startup
- **Supports both ChatGPT and Google Gemini** as transcription backends
- **Automatically returns focus** to your original app and pastes the text
- **Clipboard Preservation**: Automatically restores your original clipboard content after pasting


## Requirements

- macOS 10.14+
- Python 3.11+
- Google Chrome (must enable JavaScript from Apple Events, see below)

## Quick Start

### Option 1: Command Launch (Recommended)
Double-click **`MicPipe.command`**. This script will launch the app in the background and automatically close the terminal window. It is the most reliable way to ensure the app has necessary permissions.

### Option 2: Premium Launch (Experimental)
Double-click **`MicPipe.app`**. Note: This AppleScript wrapper might fail due to macOS privacy/permission restrictions on some systems.

### Option 3: Manual Launch
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

- **MicPipe.command**: Double-click to run. This script handles permissions more reliably and will auto-close the terminal window once the app is running in the background (recommended).
- **MicPipe.app**: Double-click for a silent experience. If this fails to start or doesn't show in the menu bar, please use the `.command` method instead.
- **Terminal**: Run `uv run python main.py`.

> **Note for first-time use**: Since this is an unsigned app, macOS might block it. If so, **Right-click** `MicPipe.app` (or `.command`) and select **Open**, then click **Open** again in the warning dialog. If the `.app` version still won't start after granting permissions, please stick with `MicPipe.command`.

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

<p align="left">
  <img src="demo/menu.png" width="300" alt="Menu Status">
</p>


### Custom Hotkey

You can choose your preferred trigger key directly from the menu:

1. Click the **MicPipe** icon in the menu bar.
2. Go to **Hotkey**.
3. Select from supported keys: **Fn**, **Command**, **Option**, **Control**, or **Shift**.

The setting is saved automatically and takes effect immediately.

## Service Selection (ChatGPT / Gemini)

You can switch between transcription services via the menu bar:

1. Click the **MicPipe** icon in the menu bar.
2. Go to **Service**.
3. Select **ChatGPT** or **Gemini**.

- **ChatGPT**: Supports full features including "Cancel" (Esc).
- **Gemini**: Supports dictation, but does not currently support the "Cancel" (Esc) key due to technical limitations of the Gemini web interface.

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

## License

This project is licensed under the **GNU General Public License v3 (GPLv3)**. See the [LICENSE](LICENSE) file for details.
