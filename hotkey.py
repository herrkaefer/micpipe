"""Global hotkey listener."""

from __future__ import annotations

from typing import Callable, Set

from pynput import keyboard


class HotkeyListener:
    def __init__(self, on_toggle: Callable[[str], None]) -> None:
        self.state = "IDLE"
        self.on_toggle = on_toggle
        self._pressed: Set[keyboard.Key] = set()
        self._listener: keyboard.Listener | None = None
        self._armed = False

    def start(self) -> None:
        self._listener = keyboard.Listener(on_press=self._on_press, on_release=self._on_release)
        self._listener.start()
        self._listener.join()

    def _on_press(self, key: keyboard.Key) -> None:
        self._pressed.add(key)
        if key == keyboard.Key.alt or key == keyboard.Key.alt_l:
            print("🔎 Hotkey: Option pressed")
        elif isinstance(key, keyboard.KeyCode) and key.char:
            print(f"🔎 Hotkey: key pressed '{key.char}'")

        if self._is_hotkey_pressed() and not self._armed:
            self._armed = True
            self._toggle_state()

    def _on_release(self, key: keyboard.Key) -> None:
        if key in self._pressed:
            self._pressed.remove(key)
        if not self._is_hotkey_pressed():
            self._armed = False

    def _is_hotkey_pressed(self) -> bool:
        alt_pressed = keyboard.Key.alt in self._pressed or keyboard.Key.alt_l in self._pressed
        v_pressed = keyboard.KeyCode.from_char("v") in self._pressed
        return alt_pressed and v_pressed

    def _toggle_state(self) -> None:
        if self.state == "IDLE":
            self.state = "RECORDING"
            self.on_toggle("START")
        else:
            self.state = "IDLE"
            self.on_toggle("STOP")
