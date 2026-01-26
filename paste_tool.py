import pyperclip
import time
from Quartz.CoreGraphics import (
    CGEventCreateKeyboardEvent,
    CGEventPost,
    kCGHIDEventTap,
    kCGEventFlagMaskCommand
)

def paste_text(text):
    """Put text into clipboard and simulate Cmd+V"""
    if not text or text == "SUCCESS" or text == "CHATGPT_NOT_FOUND":
        return
        
    # 1. Put into clipboard
    pyperclip.copy(text)
    time.sleep(0.1)  # Give the system a bit of response time
    
    # 2. Simulate Command + V
    # Key codes: V = 9, Command = kCGEventFlagMaskCommand
    cmd_v_down = CGEventCreateKeyboardEvent(None, 9, True)
    CGEventSetFlags(cmd_v_down, kCGEventFlagMaskCommand)
    CGEventPost(kCGHIDEventTap, cmd_v_down)
    
    cmd_v_up = CGEventCreateKeyboardEvent(None, 9, False)
    CGEventPost(kCGHIDEventTap, cmd_v_up)

# Polyfill for missing import function
def CGEventSetFlags(event, flags):
    from Quartz.CoreGraphics import CGEventSetFlags as _CGEventSetFlags
    _CGEventSetFlags(event, flags)

