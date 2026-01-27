import subprocess
import time

from clipboard_guard import overwrite_clipboard_with_text, restore_clipboard

def paste_text(text, snapshot=None):
    """Put text into clipboard, simulate Cmd+V, then restore clipboard."""
    if not text or text == "SUCCESS" or text == "CHATGPT_NOT_FOUND":
        return

    try:
        # 1. Put into clipboard
        overwrite_clipboard_with_text(text)
        time.sleep(0.03)  # Give the system a bit of response time

        # 2. Simulate Command + V via AppleScript
        script = r'''
        tell application "System Events"
          keystroke "v" using {command down}
        end tell
        '''
        subprocess.run(["osascript", "-e", script], check=True)
    finally:
        # 3. Restore clipboard (best-effort)
        time.sleep(0.05)
        if snapshot is not None:
            restore_clipboard(snapshot)
