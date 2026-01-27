import json
import os


class MicPipeStateStore:
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

        return state

    def save(self, current_service, sound_enabled, dedicated_windows):
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
        }
        try:
            parent = os.path.dirname(self.path)
            if parent:
                os.makedirs(parent, exist_ok=True)
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=True)
        except Exception as e:
            self._log(f"Failed to save state: {e}")
