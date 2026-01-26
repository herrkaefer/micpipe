#!/usr/bin/env python3
"""Test if Chrome window IDs change when switching windows"""

from chrome_script import ChatGPTChrome
import time

chrome = ChatGPTChrome()

print("=== Window ID Stability Test ===")
print("Please open 2 Chrome windows, both with ChatGPT tabs")
input("Press Enter when ready...")

# Get all windows
script = '''
tell application "Google Chrome"
    set result to ""
    repeat with win in windows
        set result to result & "Window ID: " & (id of win) & ", Tab 1 URL: "
        try
            set result to result & (URL of tab 1 of win)
        end try
        set result to result & "\\n"
    end repeat
    return result
end tell
'''

from chrome_script import run_applescript

print("\n--- Initial state ---")
print(run_applescript(script))

print("\nNow switch to a DIFFERENT Chrome window")
input("Press Enter after switching...")

print("\n--- After switching windows ---")
print(run_applescript(script))

print("\nSwitch back to the original window")
input("Press Enter after switching back...")

print("\n--- After switching back ---")
print(run_applescript(script))

print("\n=== Test Complete ===")
print("Check if the Window IDs changed.")
