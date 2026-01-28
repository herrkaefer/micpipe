import json
import os


class MicPipeStateStore:
    # Supported hotkey options: (keycode, display_name)
    # These are common keys used for voice input in various apps
    HOTKEY_OPTIONS = [
        (63, "Fn"),                    # Function key (default)
        (54, "Right Command (⌘)"),     # Right Cmd
        (55, "Left Command (⌘)"),      # Left Cmd
        (58, "Right Option (⌥)"),      # Right Option/Alt
        (61, "Left Option (⌥)"),       # Left Option/Alt
        (59, "Right Control (⌃)"),     # Right Control
        (62, "Left Control (⌃)"),      # Left Control
        (60, "Right Shift (⇧)"),       # Right Shift
        (56, "Left Shift (⇧)"),        # Left Shift
    ]

    DEFAULT_TRIGGER_KEY = 63  # Fn key

    def __init__(self, path, logger=None):
        self.path = path
        self.logger = logger

    def _log(self, msg):
        if self.logger:
            try:
                self.logger.debug(msg)
            except Exception:
                pass

    def load(self):
        state = {
            "current_service": "ChatGPT",
            "sound_enabled": True,
            "dedicated_windows": {"ChatGPT": None, "Gemini": None},
            "trigger_key": self.DEFAULT_TRIGGER_KEY,
        }
        try:
            if not os.path.exists(self.path):
                return state
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            self._log(f"Failed to load state: {e}")
            return state

        service = data.get("current_service")
        if service in ("ChatGPT", "Gemini"):
            state["current_service"] = service

        sound = data.get("sound_enabled")
        if isinstance(sound, bool):
            state["sound_enabled"] = sound

        windows = data.get("dedicated_windows")
        if isinstance(windows, dict):
            for key in ("ChatGPT", "Gemini"):
                loc = windows.get(key)
                if isinstance(loc, list) and len(loc) == 2:
                    try:
                        win_id = int(loc[0])
                        tab_idx = int(loc[1])
                        if win_id > 0 and tab_idx > 0:
                            state["dedicated_windows"][key] = (win_id, tab_idx)
                    except Exception:
                        pass

        # Load trigger key
        trigger_key = data.get("trigger_key")
        valid_keycodes = [opt[0] for opt in self.HOTKEY_OPTIONS]
        if isinstance(trigger_key, int) and trigger_key in valid_keycodes:
            state["trigger_key"] = trigger_key

        return state

    def save(self, current_service, sound_enabled, dedicated_windows, trigger_key=None):
        payload = {
            "current_service": current_service,
            "sound_enabled": sound_enabled,
            "dedicated_windows": {
                "ChatGPT": list(dedicated_windows.get("ChatGPT"))
                if dedicated_windows.get("ChatGPT")
                else None,
                "Gemini": list(dedicated_windows.get("Gemini"))
                if dedicated_windows.get("Gemini")
                else None,
            },
            "trigger_key": trigger_key if trigger_key is not None else self.DEFAULT_TRIGGER_KEY,
        }
        try:
            parent = os.path.dirname(self.path)
            if parent:
                os.makedirs(parent, exist_ok=True)
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=True)
        except Exception as e:
            self._log(f"Failed to save state: {e}")
