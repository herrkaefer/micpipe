import logging
import time
import os
import Quartz
import threading
import re
import rumps
import argparse
from AppKit import NSWorkspace, NSApplicationActivateIgnoringOtherApps, NSSound, NSScreen
from chrome_script import ChatGPTChrome, GeminiChrome
from clipboard_guard import snapshot_clipboard
from paste_tool import paste_text
from state_manager import MicPipeStateStore

# ============================================================
# HOTKEY CONFIGURATION - Change the keycode below to customize
# ============================================================
# Common keycodes for reference:
#   63  - Fn (Function key)
#   54  - Right Command
#   55  - Left Command
#   58  - Right Option
#   61  - Left Option
#   59  - Right Control
#   62  - Left Control
#   60  - Left Shift
#   56  - Right Shift
#   48  - Tab
#   53  - Escape
#   51  - Delete (Backspace)
#   117 - Forward Delete
#   36  - Return (Enter)
#   49  - Space
# ============================================================
__version__ = "1.2.0"


TRIGGER_KEY_CODE = 63  # Fn key (supports both Hold and Toggle modes)

def configure_logging(debug: bool):
    logging.basicConfig(
        level=logging.DEBUG if debug else logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

logger = logging.getLogger(__name__)

# ============================================================

class MicPipeApp(rumps.App):
    _TAB_LOC_RE = re.compile(r"(?:USED_WIN_ID|FALLBACK_WIN_ID)=(\d+),TAB=(\d+):")

    def __init__(self, debug: bool = False):
        super(MicPipeApp, self).__init__("MicPipe", quit_button="Quit")
        self.base_path = os.path.dirname(__file__)
        self.icon = os.path.join(self.base_path, "assets/icon_idle_template.png")
        self.template = True  # Enable template mode for idle icon
        self.state_path = os.path.join(
            os.path.expanduser("~"),
            "Library",
            "Application Support",
            "MicPipe",
            "micpipe_state.json",
        )
        self.state_store = MicPipeStateStore(self.state_path, logger)
        self.debug = debug
        self.dedicated_bounds = self._compute_dedicated_bounds(debug)

        # Service selection (ChatGPT or Gemini)
        self.current_service = "ChatGPT"  # Default service
        self.sound_enabled = True
        self.dedicated_windows = {"ChatGPT": None, "Gemini": None}
        state = self.state_store.load()
        self.current_service = state["current_service"]
        self.sound_enabled = state["sound_enabled"]
        self.dedicated_windows = state["dedicated_windows"]
        self.chatgpt_chrome = ChatGPTChrome()
        self.gemini_chrome = GeminiChrome()
        self.chrome = self.chatgpt_chrome if self.current_service == "ChatGPT" else self.gemini_chrome  # Active controller

        self.is_recording = False
        self.current_state = "IDLE"
        self.animation_frame = 0

        # Internal state
        self.target_app = None
        self.target_is_service_page = False  # True if triggered from ChatGPT/Gemini page
        self.trigger_key_currently_pressed = False
        self.should_auto_start = False
        self.waiting_for_page = False
        self.service_tab_location = None  # Dedicated window location
        self.dedicated_window = None
        self._sound_start = os.path.join(self.base_path, "assets", "sound_start.wav")
        self._sound_stop = os.path.join(self.base_path, "assets", "sound_stop.wav")

        # Ensure dedicated window exists at startup (in background)
        self._ensure_dedicated_window()
        threading.Thread(target=self._check_service_ready_on_startup).start()

        # Build menu
        key_name = self._get_key_name(TRIGGER_KEY_CODE)
        self.status_item = rumps.MenuItem("Status: Ready", callback=None)

        # Service selection submenu
        self.service_chatgpt = rumps.MenuItem("ChatGPT", callback=self.select_chatgpt)
        self.service_chatgpt.state = 1 if self.current_service == "ChatGPT" else 0
        self.service_gemini = rumps.MenuItem("Gemini", callback=self.select_gemini)
        self.service_gemini.state = 1 if self.current_service == "Gemini" else 0
        self.service_menu = rumps.MenuItem("Service")
        self.service_menu.add(self.service_chatgpt)
        self.service_menu.add(self.service_gemini)

        self.hotkey_info = rumps.MenuItem(f"Hotkey: {key_name}", callback=None)
        self.hold_mode_info = rumps.MenuItem(f"  Hold {key_name} → Hold to Speak", callback=None)
        self.toggle_mode_info = rumps.MenuItem(f"  Click {key_name} → Toggle Start/Stop", callback=None)
        self.cancel_mode_info = rumps.MenuItem("  Press Esc → Cancel Dictation", callback=None)
        self.sound_toggle_item = rumps.MenuItem(
            "Sound: On" if self.sound_enabled else "Sound: Off",
            callback=self.toggle_sound
        )
        self.version_info = rumps.MenuItem(f"Version: {__version__}", callback=None)

        self.menu = [
            self.status_item,
            None,  # Separator
            self.service_menu,
            None,  # Separator
            self.hotkey_info,
            self.hold_mode_info,
            self.toggle_mode_info,
            self.cancel_mode_info,
            None,  # Separator
            self.sound_toggle_item,
            None,  # Separator
            self.version_info
        ]

        # Animation timer (runs at 10Hz)
        self.timer = rumps.Timer(self._update_animation, 0.1)
        self.timer.start()

    def _save_state(self):
        self.state_store.save(self.current_service, self.sound_enabled, self.dedicated_windows)

    def _compute_dedicated_bounds(self, debug: bool):
        if debug:
            return (60, 60, 1100, 800)

        # Place the window just outside the bottom-left of the virtual screen bounds.
        try:
            screens = NSScreen.screens()
            if not screens:
                return (-2000, -1900, -1900, -1800)
            min_x = min(s.frame().origin.x for s in screens)
            min_y = min(s.frame().origin.y for s in screens)
            left = int(min_x - 2000)
            bottom = int(min_y - 2000)
            right = left + 100
            top = bottom + 100
            return (left, top, right, bottom)
        except Exception:
            return (-2000, -1900, -1900, -1800)

    def _get_ready_status(self, res: str) -> str:
        if not res or not res.startswith("SUCCESS"):
            return ""
        return res.rsplit(":", 1)[-1]

    def _prompt_service_login(self, details: str):
        location = self.service_tab_location or self.dedicated_windows.get(self.current_service)
        if location:
            try:
                self.chrome.reveal_window(location[0])
            except Exception:
                pass
        rumps.notification(
            "MicPipe",
            f"{self.current_service} 登录/权限问题",
            details
        )

    def _update_service_tab_location_from_result(self, result: str):
        """Update self.service_tab_location when Chrome reports the actual window/tab used."""
        if not result:
            return
        m = self._TAB_LOC_RE.search(result)
        if not m:
            return
        try:
            win_id = int(m.group(1))
            tab_idx = int(m.group(2))
        except Exception:
            return
        if win_id > 0 and tab_idx > 0:
            old = self.service_tab_location
            self.service_tab_location = (win_id, tab_idx)
            self.dedicated_window = self.service_tab_location
            self.dedicated_windows[self.current_service] = self.service_tab_location
            self._save_state()
            if old != self.service_tab_location:
                logger.debug(f"Updated service_tab_location: {old} -> {self.service_tab_location}")

    def _ensure_dedicated_window(self):
        """Ensure the dedicated window exists for the current service."""
        try:
            chrome = self.chatgpt_chrome if self.current_service == "ChatGPT" else self.gemini_chrome
            service_name = self.current_service

            location = self.dedicated_windows.get(service_name)
            if location and chrome.is_window_alive(*location):
                self.dedicated_window = location
                self.service_tab_location = location
                try:
                    chrome.set_window_bounds(location[0], self.dedicated_bounds)
                except Exception:
                    pass
                self._save_state()
                return location, False

            new_location = chrome.create_dedicated_window(bounds=self.dedicated_bounds)
            if new_location:
                self.dedicated_windows[service_name] = new_location
                self.dedicated_window = new_location
                self.service_tab_location = new_location
                logger.info(f"{service_name} dedicated window created: {new_location}")
                self._save_state()
                return new_location, True

            logger.error(f"Failed to create dedicated window for {service_name}")
            return None, False
        except Exception as e:
            logger.error(f"Failed to ensure dedicated window: {e}")
            return None, False

    def select_chatgpt(self, _):
        """Switch to ChatGPT service."""
        if self.is_recording:
            return  # Don't switch during recording
        self.current_service = "ChatGPT"
        self.chrome = self.chatgpt_chrome
        self.service_chatgpt.state = 1
        self.service_gemini.state = 0
        self.cancel_mode_info.title = "  Press Esc → Cancel Dictation"
        self._save_state()
        self._ensure_dedicated_window()

    def select_gemini(self, _):
        """Switch to Gemini service."""
        if self.is_recording:
            return  # Don't switch during recording
        self.current_service = "Gemini"
        self.chrome = self.gemini_chrome
        self.service_chatgpt.state = 0
        self.service_gemini.state = 1
        self.cancel_mode_info.title = "  Press Esc → Cancel (ChatGPT only)"
        self._save_state()
        self._ensure_dedicated_window()

    def _update_animation(self, _):
        """Update menu bar icon based on current state"""
        self.animation_frame += 1

        if self.current_state == "IDLE":
            idle_icon = os.path.join(self.base_path, "assets/icon_idle_template.png")
            if self.icon != idle_icon:
                self.icon = idle_icon
                self.template = True
                self.title = None

        elif self.current_state == "RECORDING":
            # Pulsating red dot animation (every 2 frames = 5Hz)
            if self.animation_frame % 2 == 0:
                frame = (self.animation_frame // 2) % 4 + 1
                self.icon = os.path.join(self.base_path, f"assets/icon_rec_{frame}.png")
                self.template = False # Red color needs template=False
                self.title = None

        elif self.current_state == "WAITING" or self.current_state == "PROCESSING":
            # Spinning/Processing icon (every 3 frames)
            if self.animation_frame % 3 == 0:
                self.icon = os.path.join(self.base_path, "assets/icon_processing.png")
                self.template = True
                self.title = None
                # Optional: rotate icon if supported, but here we just keep it static 
                # or we could have multiple processing frames.

    def _get_key_name(self, keycode):
        """Get human-readable key name from keycode"""
        key_names = {
            63: "Fn",
            54: "Right Cmd",
            55: "Left Cmd",
            58: "Right Option",
            61: "Left Option",
            59: "Right Control",
            62: "Left Control",
            60: "Left Shift",
            56: "Right Shift",
            48: "Tab",
            53: "Esc",
            51: "Delete",
            117: "Forward Delete",
            36: "Return",
            49: "Space",
        }
        return key_names.get(keycode, f"Key {keycode}")

    def _play_sound(self, path):
        if not self.sound_enabled:
            return
        try:
            sound = NSSound.alloc().initWithContentsOfFile_byReference_(path, True)
            if sound:
                sound.play()
        except Exception:
            pass

    def toggle_sound(self, _):
        self.sound_enabled = not self.sound_enabled
        self.sound_toggle_item.title = "Sound: On" if self.sound_enabled else "Sound: Off"
        self._save_state()

    def event_callback(self, proxy, event_type, event, refcon):
        """System event callback: Monitor trigger key"""
        if event_type == Quartz.kCGEventKeyDown:
            keycode = Quartz.CGEventGetIntegerValueField(event, 9)
            if keycode == 53:  # Esc
                # Gemini does not support cancel, only ChatGPT does
                if self.current_service == "ChatGPT" and (self.is_recording or self.waiting_for_page):
                    threading.Thread(target=self.cancel_recording).start()
                return event

        if event_type == Quartz.kCGEventFlagsChanged:
            keycode = Quartz.CGEventGetIntegerValueField(event, 9)
            flags = Quartz.CGEventGetFlags(event)

            # Handle trigger key - Dual Mode (Hold or Toggle)
            if keycode == TRIGGER_KEY_CODE:
                key_pressed = self._is_key_pressed(keycode, flags)

                # Prevent duplicate events
                if key_pressed == self.trigger_key_currently_pressed:
                    return event
                self.trigger_key_currently_pressed = key_pressed

                # Dual Mode behavior:
                # - Hold Mode: Hold key to speak, release to stop
                # - Toggle Mode: Quick click to start, click again to stop
                if key_pressed and not self.is_recording:
                    threading.Thread(target=lambda: self.start_recording(is_hold_mode=True)).start()
                elif not key_pressed:
                    # User released trigger key
                    if self.is_recording:
                        threading.Thread(target=self.stop_recording).start()

        return event

    def cancel_recording(self):
        """Cancel the current dictation without pasting text (ChatGPT only)"""
        if not self.is_recording and not self.waiting_for_page:
            return

        # Gemini does not support cancel
        if self.current_service == "Gemini":
            return

        # Cancel any pending auto-start
        if self.waiting_for_page:
            self.waiting_for_page = False
            self.should_auto_start = False

        if self.is_recording:
            self.is_recording = False
            self._play_sound(self._sound_stop)
            self.current_state = "PROCESSING"
            self.status_item.title = "Status: ⏳ Cancelling..."
            try:
                self.chrome.cancel_dictation(preferred_location=self.service_tab_location)
            except Exception:
                pass

        # Restore focus to original app
        if self.target_app:
            time.sleep(0.1)
            self.target_app.activateWithOptions_(NSApplicationActivateIgnoringOtherApps)

        self.current_state = "IDLE"
        self.status_item.title = "Status: Ready"

    def _is_key_pressed(self, keycode, flags):
        """Check if a specific key is pressed based on keycode and flags"""
        # Map keycodes to their corresponding flag masks
        flag_masks = {
            63: Quartz.kCGEventFlagMaskSecondaryFn,      # Fn
            54: Quartz.kCGEventFlagMaskCommand,          # Right Cmd
            55: Quartz.kCGEventFlagMaskCommand,          # Left Cmd
            58: Quartz.kCGEventFlagMaskAlternate,        # Right Option
            61: Quartz.kCGEventFlagMaskAlternate,        # Left Option
            59: Quartz.kCGEventFlagMaskControl,          # Right Control
            62: Quartz.kCGEventFlagMaskControl,          # Left Control
            60: Quartz.kCGEventFlagMaskShift,            # Left Shift
            56: Quartz.kCGEventFlagMaskShift,            # Right Shift
        }

        mask = flag_masks.get(keycode)
        if mask:
            return bool(flags & mask)
        return False

    def _enter_waiting_state(self, is_hold_mode):
        """Enter waiting state while the service page loads."""
        self.current_state = "WAITING"
        self.status_item.title = "Status: ⏳ Loading page..."
        self.waiting_for_page = True
        # Always auto-start once the page is ready (both Hold and Toggle)
        self.should_auto_start = True
        threading.Thread(target=self._wait_and_start_recording).start()
        # Restore focus while the page loads so dictation result can paste back.
        if self.target_app:
            time.sleep(0.1)
            self.target_app.activateWithOptions_(NSApplicationActivateIgnoringOtherApps)

    def _check_service_ready_on_startup(self):
        """On app launch, verify that the service page is usable and prompt if not."""
        max_wait_time = 20
        poll_interval = 0.5
        elapsed = 0

        while elapsed < max_wait_time:
            time.sleep(poll_interval)
            elapsed += poll_interval

            if not self.service_tab_location:
                return

            res = self.chrome.is_page_ready(preferred_location=self.service_tab_location)
            status = self._get_ready_status(res)
            if status == "READY":
                return
            if status == "BTN_NOT_FOUND":
                self._prompt_service_login("请在专属窗口登录后再试一次。")
                return

    def start_recording(self, is_hold_mode=False):
        """Start recording (for both Hold and Toggle modes)"""
        if self.is_recording:
            return

        # 1. Record the current focused application
        self.target_app = NSWorkspace.sharedWorkspace().frontmostApplication()
        self.target_is_service_page = False

        # 2. Ensure dedicated window exists
        location, created = self._ensure_dedicated_window()
        if not location:
            self.current_state = "IDLE"
            self.status_item.title = "Status: Ready"
            rumps.notification(
                "MicPipe",
                "Window Error",
                f"Could not create {self.current_service} dedicated window."
            )
            return
        self.service_tab_location = location

        if created:
            self._enter_waiting_state(is_hold_mode)
            return

        # If the page is still loading, wait before starting dictation
        ready_res = self.chrome.is_page_ready(preferred_location=self.service_tab_location)
        status = self._get_ready_status(ready_res)
        if status == "PAGE_NOT_READY":
            self._enter_waiting_state(is_hold_mode)
            return
        if status == "BTN_NOT_FOUND":
            self.current_state = "IDLE"
            self.status_item.title = "Status: Ready"
            self._prompt_service_login("请在专属窗口登录后再试一次。")
            return

        # 3. Update status and state
        self.current_state = "RECORDING"
        self.status_item.title = "Status: 🎤 Recording..."

        # 4. Start Chrome dictation
        res = self.chrome.start_dictation(preferred_location=self.service_tab_location)
        if res.startswith("SUCCESS"):
            self._update_service_tab_location_from_result(res)
            self.is_recording = True
            self._play_sound(self._sound_start)
        else:
            # Failed to start; inform the user so they know why nothing happened.
            self.current_state = "IDLE"
            self.status_item.title = "Status: Ready"
            rumps.notification(
                "MicPipe",
                "Start Failed",
                f"Could not start {self.current_service} dictation. Details: {res or 'UNKNOWN'}"
            )

        # 4. Restore focus
        if self.target_app:
            time.sleep(0.1)
            self.target_app.activateWithOptions_(NSApplicationActivateIgnoringOtherApps)

    def _wait_and_start_recording(self):
        """Poll for page readiness and start recording once ready"""
        max_wait_time = 15  # Maximum 15 seconds
        poll_interval = 0.5  # Check every 0.5 seconds
        elapsed = 0

        while elapsed < max_wait_time:
            time.sleep(poll_interval)
            elapsed += poll_interval

            # Check if user cancelled (e.g., released Fn key in Hold mode)
            if not self.should_auto_start:
                self.waiting_for_page = False
                self.current_state = "IDLE"
                self.status_item.title = "Status: Ready"
                return

            # Check if page is ready
            res = self.chrome.is_page_ready(preferred_location=self.service_tab_location)
            status = self._get_ready_status(res)
            if status == "READY":
                # Page is ready, check again if we should still start
                if self.should_auto_start:
                    self._retry_start_recording()
                else:
                    self.waiting_for_page = False
                    self.current_state = "IDLE"
                    self.status_item.title = "Status: Ready"
                return
            if status == "BTN_NOT_FOUND":
                self.waiting_for_page = False
                self.should_auto_start = False
                self.current_state = "IDLE"
                self.status_item.title = "Status: Ready"
                self._prompt_service_login("录音按钮不可用，请登录或检查权限后重试。")
                return

        # Timeout: page didn't load in time
        self.waiting_for_page = False
        self.should_auto_start = False
        self.current_state = "IDLE"
        self.status_item.title = "Status: Ready"
        rumps.notification("MicPipe", "Timeout", "Page took too long to load. Please try again.")

    def _retry_start_recording(self):
        """Retry starting recording after page loads"""
        # Clear waiting flags
        self.waiting_for_page = False
        self.should_auto_start = False

        res = self.chrome.start_dictation(preferred_location=self.service_tab_location)
        if res.startswith("SUCCESS"):
            self._update_service_tab_location_from_result(res)
            self.is_recording = True
            self.current_state = "RECORDING"
            self.status_item.title = "Status: 🎤 Recording..."
            self._play_sound(self._sound_start)
        else:
            # Failed to start even after waiting
            self.current_state = "IDLE"
            self.status_item.title = "Status: Ready"
            rumps.notification("MicPipe", "Error", "Failed to start recording. Please try again.")

        # Restore focus to original app
        if self.target_app:
            time.sleep(0.1)
            self.target_app.activateWithOptions_(NSApplicationActivateIgnoringOtherApps)

    def stop_recording(self):
        """Stop recording (for both Hold and Toggle modes)"""
        if not self.is_recording:
            return

        self.is_recording = False
        self._play_sound(self._sound_stop)
        self.current_state = "PROCESSING"
        self.status_item.title = "Status: ⏳ Transcribing..."

        logger.debug(f"Stopping dictation at location: {self.service_tab_location}")
        stop_res = ""
        try:
            stop_res = self.chrome.stop_dictation(preferred_location=self.service_tab_location)
        except Exception as e:
            stop_res = f"EXCEPTION:{e}"

        if stop_res.startswith("SUCCESS"):
            # Capture the location reported by Chrome for follow-up actions.
            self._update_service_tab_location_from_result(stop_res)

        if (not stop_res) or ("NOT_FOUND" in stop_res) or ("BTN_NOT_FOUND" in stop_res):
            self.current_state = "IDLE"
            self.status_item.title = "Status: Ready"
            rumps.notification(
                "MicPipe",
                "Stop Failed",
                f"Could not stop {self.current_service} dictation automatically. "
                f"It may still be recording in Chrome. Details: {stop_res or 'UNKNOWN'}"
            )
            return

        # If we're already on the service page, don't extract/clear/paste. Leaving the text
        # in the input box is the expected behavior.
        if self.target_is_service_page:
            self.current_state = "IDLE"
            self.status_item.title = "Status: Ready"
            return

        # Take a clipboard snapshot while we wait for transcription
        clipboard_snapshot = snapshot_clipboard()

        # Poll for transcribed text (max 5 attempts)
        text = ""
        force_activate = True
        max_attempts = 5

        for i in range(max_attempts):
            # Progressive retry intervals
            if i == 0:
                time.sleep(1.0)  # First attempt: wait 1s for transcription to complete
            elif i < 3:
                time.sleep(0.5)  # 2nd-3rd attempts: quick retry
            else:
                time.sleep(1.0)  # 4th-5th attempts: standard interval

            res = self.chrome.get_text_and_clear(
                activate_first=force_activate,
                preferred_location=self.service_tab_location,
            )
            logger.debug(f"Attempt {i+1}/{max_attempts}: {res}")
            force_activate = False
            if res.startswith("SUCCESS:"):
                content = res.split("SUCCESS:", 1)[1]
                # Debuggable empty states from the page:
                # - "EMPTY"
                # - "EMPTY|DBG=..."
                # - "NOT_FOUND"
                # - "NOT_FOUND|DBG=..."
                if content.startswith("EMPTY|DBG=") or content.startswith("NOT_FOUND|DBG="):
                    logger.debug(content)
                    force_activate = True
                    continue

                if content and content not in ["EMPTY", "NOT_FOUND", "SUCCESS", "missing value"]:
                    text = content
                    logger.debug(f"Got text: {text[:50]}...")
                    break
                # If still empty, try re-activating on the next poll
                force_activate = True

        # Paste result
        if text:
            if self.target_app:
                self.target_app.activateWithOptions_(NSApplicationActivateIgnoringOtherApps)
                time.sleep(0.2)
            paste_text(text, snapshot=clipboard_snapshot)

        self.current_state = "IDLE"
        self.status_item.title = "Status: Ready"

    def run_app(self):
        # Create Event Tap
        tap = Quartz.CGEventTapCreate(
            Quartz.kCGSessionEventTap,
            Quartz.kCGHeadInsertEventTap,
            Quartz.kCGEventTapOptionDefault,
            Quartz.kCGEventMaskForAllEvents,
            self.event_callback,
            None
        )

        if not tap:
            rumps.alert("Permission Error", "Please grant Accessibility permissions in System Settings.")
            return

        run_loop_source = Quartz.CFMachPortCreateRunLoopSource(None, tap, 0)
        Quartz.CFRunLoopAddSource(Quartz.CFRunLoopGetCurrent(), run_loop_source, Quartz.kCFRunLoopCommonModes)
        Quartz.CGEventTapEnable(tap, True)
        
        # Start rumps main loop
        self.run()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="MicPipe")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging and visible window")
    args = parser.parse_args()

    configure_logging(args.debug)
    app = MicPipeApp(debug=args.debug)
    app.run_app()
