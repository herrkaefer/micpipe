"""Clipboard utilities and paste automation."""

from __future__ import annotations

from functools import wraps
from typing import Callable

import pyperclip
from Quartz import CGEventCreateKeyboardEvent, CGEventPost, CGEventSetFlags
from Quartz import kCGEventFlagMaskCommand, kCGHIDEventTap

try:
    from Carbon.HIToolbox import kVK_ANSI_V
except Exception:
    # macOS virtual keycode for "V" (US keyboard layout).
    kVK_ANSI_V = 0x09


def copy_to_clipboard(text: str) -> None:
    pyperclip.copy(text)


def paste_to_active_app() -> None:
    # Post Cmd+V keydown/keyup to the active application.
    event_down = CGEventCreateKeyboardEvent(None, kVK_ANSI_V, True)
    CGEventSetFlags(event_down, kCGEventFlagMaskCommand)
    CGEventPost(kCGHIDEventTap, event_down)

    event_up = CGEventCreateKeyboardEvent(None, kVK_ANSI_V, False)
    CGEventSetFlags(event_up, kCGEventFlagMaskCommand)
    CGEventPost(kCGHIDEventTap, event_up)


def save_and_restore_clipboard(func: Callable[..., None]) -> Callable[..., None]:
    @wraps(func)
    def wrapper(*args, **kwargs):
        original = pyperclip.paste()
        try:
            return func(*args, **kwargs)
        finally:
            pyperclip.copy(original)

    return wrapper
