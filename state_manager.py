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

    DEFAULT_PIPE_SLOTS = [
        {"title": "Basic Correction", "prompt": "Fix the following voice transcription: 1) Fix grammar errors, typos, and filler words; 2) Add proper punctuation; 3) Auto Format: standardize addresses, phone numbers, numbers, and times to their proper formats; 4) Auto Edit: if there are contradictions, keep the true intent based on context. Output only the corrected text:"},
        {"title": "Polish Text", "prompt": "Polish and improve the following text and output only the result:"},
        {"title": "Translate to English", "prompt": "Translate the following text to English and output only the translation:"},
        {"title": "Vibe Coder", "prompt": "The following is a voice transcription of coding instructions. Please clean it up by: 1) removing filler words, hesitations and repetitions, 2) resolving any contradictions by keeping the latest intent, 3) organizing the ideas into clear, actionable instructions. Output a clean, well-structured prompt that a coding agent can directly use:"},
        {"title": "Email Writer", "prompt": "Transform the following voice transcription into a professional email. Please: 1) Identify the key points and intent; 2) Structure it with appropriate greeting, body, and closing; 3) Use professional yet friendly tone; 4) Fix any grammar issues and remove filler words; 5) Keep it concise and clear. Output only the email content:"}
    ]


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
        import copy
        state = {
            "current_service": "ChatGPT",
            "sound_enabled": True,
            "dedicated_windows": {"ChatGPT": None, "Gemini": None},
            "trigger_key": self.DEFAULT_TRIGGER_KEY,
            "pipe_slots": copy.deepcopy(self.DEFAULT_PIPE_SLOTS),
            "current_pipe_slot": -1,
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

        # Load pipe slots (support both old string format and new dict format)
        pipe_slots = data.get("pipe_slots")
        if isinstance(pipe_slots, list) and len(pipe_slots) == 5:
            converted = []
            for s in pipe_slots:
                if isinstance(s, dict) and "title" in s and "prompt" in s:
                    converted.append({"title": s["title"], "prompt": s["prompt"]})
                elif isinstance(s, str):
                    # Migrate old format: use first 20 chars as title
                    title = s[:20] + "..." if len(s) > 20 else s
                    converted.append({"title": title, "prompt": s})
                else:
                    converted.append({"title": "", "prompt": ""})
            state["pipe_slots"] = converted
        else:
            import copy
            state["pipe_slots"] = copy.deepcopy(self.DEFAULT_PIPE_SLOTS)

        # Load current correction slot
        current_slot = data.get("current_pipe_slot")
        if isinstance(current_slot, int) and -1 <= current_slot <= 4:
            state["current_pipe_slot"] = current_slot
        else:
            state["current_pipe_slot"] = -1

        return state

    def save(self, current_service, sound_enabled, dedicated_windows, trigger_key=None, pipe_slots=None, current_pipe_slot=None):
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
            "pipe_slots": pipe_slots if pipe_slots is not None else self.DEFAULT_PIPE_SLOTS.copy(),
            "current_pipe_slot": current_pipe_slot if current_pipe_slot is not None else -1,
        }
        try:
            parent = os.path.dirname(self.path)
            if parent:
                os.makedirs(parent, exist_ok=True)
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=True)
        except Exception as e:
            self._log(f"Failed to save state: {e}")
