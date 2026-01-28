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
__version__ = "1.3.0"

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

        # Load saved state
        state = self.state_store.load()
        self.current_service = state["current_service"]
        self.sound_enabled = state["sound_enabled"]
        self.dedicated_windows = state["dedicated_windows"]
        self.trigger_key = state["trigger_key"]
        self.pipe_slots = state["pipe_slots"]
        self.current_pipe_slot = state["current_pipe_slot"]
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
        self.status_item = rumps.MenuItem("Status: Ready", callback=None)

        # Service selection submenu
        self.service_chatgpt = rumps.MenuItem("ChatGPT", callback=self.select_chatgpt)
        self.service_chatgpt.state = 1 if self.current_service == "ChatGPT" else 0
        self.service_gemini = rumps.MenuItem("Gemini", callback=self.select_gemini)
        self.service_gemini.state = 1 if self.current_service == "Gemini" else 0
        self.service_menu = rumps.MenuItem("Service")
        self.service_menu.add(self.service_chatgpt)
        self.service_menu.add(self.service_gemini)

        # Hotkey selection submenu
        self.hotkey_menu = rumps.MenuItem("Hotkey")
        self.hotkey_items = {}
        for keycode, display_name in MicPipeStateStore.HOTKEY_OPTIONS:
            item = rumps.MenuItem(display_name, callback=self._make_hotkey_callback(keycode))
            item.state = 1 if keycode == self.trigger_key else 0
            self.hotkey_items[keycode] = item
            self.hotkey_menu.add(item)

        # AI Pipe submenu
        self.pipe_menu = rumps.MenuItem("AI Pipe")
        self.pipe_items = {}
        
        # Off option
        off_item = rumps.MenuItem("Off", callback=self._make_pipe_callback(-1))
        off_item.state = 1 if self.current_pipe_slot == -1 else 0
        self.pipe_items[-1] = off_item
        self.pipe_menu.add(off_item)
        
        # Slot options
        for i in range(5):
            slot_label = self._get_slot_label(i)
            item = rumps.MenuItem(slot_label, callback=self._make_pipe_callback(i))
            item.state = 1 if self.current_pipe_slot == i else 0
            self.pipe_items[i] = item
            self.pipe_menu.add(item)
        
        self.pipe_menu.add(None)  # Separator
        
        # Edit options
        for i in range(5):
            edit_item = rumps.MenuItem(f"Edit Slot {i+1}...", callback=self._make_edit_slot_callback(i))
            self.pipe_menu.add(edit_item)

        key_name = self._get_key_name(self.trigger_key)
        self.hold_mode_info = rumps.MenuItem(f"  Hold → Hold to Speak", callback=None)
        self.toggle_mode_info = rumps.MenuItem(f"  Click → Toggle Start/Stop", callback=None)
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
            self.hotkey_menu,
            self.pipe_menu,
            None,  # Separator
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
        self.state_store.save(
            self.current_service, 
            self.sound_enabled, 
            self.dedicated_windows, 
            self.trigger_key,
            self.pipe_slots,
            self.current_pipe_slot
        )

    def _make_hotkey_callback(self, keycode):
        """Create a callback function for hotkey menu item selection."""
        def callback(_):
            if self.is_recording:
                return  # Don't change hotkey during recording
            # Update checkmarks
            for kc, item in self.hotkey_items.items():
                item.state = 1 if kc == keycode else 0
            self.trigger_key = keycode
            self._save_state()
            # Show notification about the change
            key_name = self._get_key_name(keycode)
            rumps.notification("MicPipe", "Hotkey Changed", f"New hotkey: {key_name}")
        return callback

    def _get_slot_label(self, slot_index):
        """Get display label for a correction slot"""
        prompt = self.pipe_slots[slot_index]
        if not prompt:
            return f"Slot {slot_index + 1}: (empty)"
        # Show first 30 chars of prompt
        preview = prompt[:30] + "..." if len(prompt) > 30 else prompt
        return f"Slot {slot_index + 1}: {preview}"

    def _make_pipe_callback(self, slot_index):
        """Create callback for selecting a correction slot"""
        def callback(_):
            if self.is_recording:
                return  # Don't change during recording
            # Update checkmarks
            for idx, item in self.pipe_items.items():
                item.state = 1 if idx == slot_index else 0
            self.current_pipe_slot = slot_index
            self._save_state()
            
            # Show notification
            if slot_index == -1:
                rumps.notification("MicPipe", "AI Pipe", "AI Pipe disabled")
            else:
                rumps.notification("MicPipe", "AI Pipe", f"Using Slot {slot_index + 1}")
        return callback

    def _make_edit_slot_callback(self, slot_index):
        """Create callback for editing a pipe slot"""
        def callback(_):
            current_prompt = self.pipe_slots[slot_index]
            
            # Use AppleScript for better dialog behavior
            import subprocess
            
            # Escape quotes for AppleScript
            escaped_prompt = current_prompt.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n')
            
            script = f'''
            tell application "System Events"
                activate
                set dialogResult to display dialog "Enter the prompt for AI Pipe:" default answer "{escaped_prompt}" with title "Edit Slot {slot_index + 1}" buttons {{"Cancel", "OK"}} default button "OK"
                if button returned of dialogResult is "OK" then
                    return text returned of dialogResult
                else
                    return "<<CANCELLED>>"
                end if
            end tell
            '''
            
            try:
                result = subprocess.run(
                    ['osascript', '-e', script],
                    capture_output=True,
                    text=True,
                    timeout=120
                )
                
                if result.returncode == 0:
                    new_prompt = result.stdout.strip()
                    if new_prompt != "<<CANCELLED>>":
                        self.pipe_slots[slot_index] = new_prompt
                        self._save_state()
                        
                        # Update menu label
                        new_label = self._get_slot_label(slot_index)
                        self.pipe_items[slot_index].title = new_label
                        
                        rumps.notification("MicPipe", "Slot Updated", f"Slot {slot_index + 1} has been updated")
            except subprocess.TimeoutExpired:
                pass
            except Exception as e:
                logger.error(f"Failed to show edit dialog: {e}")
        
        return callback

    def _compute_dedicated_bounds(self, debug: bool):
        # Fixed window size that ensures the microphone button is visible
        width = 700
        height = 500

        if debug:
            # Debug mode: visible window at top-left
            return (0, 0, width, height)

        # Production mode: Push window to bottom-right corner, minimizing visible area.
        # macOS enforces that at least a few pixels remain visible. Through testing:
        # - Pushing right: left = screen_width - 5 leaves only ~5px visible
        # - Pushing down: top = screen_height - 50 works well
        try:
            screens = NSScreen.screens()
            if not screens:
                return (20000, 2000, 20000 + width, 2000 + height)
            # Get the main screen dimensions
            main_screen = screens[0].frame()
            screen_width = int(main_screen.size.width)
            screen_height = int(main_screen.size.height)
            # Position at bottom-right corner, leaving minimal visible area
            left = screen_width - 5  # Only ~5px visible on right edge
            top = screen_height - 50  # Near bottom of screen
            return (left, top, left + width, top + height)
        except Exception:
            return (20000, 2000, 20000 + width, 2000 + height)

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
            if keycode == self.trigger_key:
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
        btn_missing_hits = 0

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
                btn_missing_hits += 1
                if btn_missing_hits >= 6:
                    self._prompt_service_login("请在专属窗口登录后再试一次。")
                    return
            else:
                btn_missing_hits = 0

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
        if status in ("PAGE_NOT_READY", "BTN_NOT_FOUND"):
            self._enter_waiting_state(is_hold_mode)
            return

        # 3. Update status and state
        self.current_state = "RECORDING"
        self.status_item.title = "Status: 🎤 Recording..."

        # Note: We don't pre-fill prompt here because it prevents the send button from appearing.
        # Instead, we'll combine prompt + transcription in stop_recording.

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
        btn_missing_hits = 0

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
                btn_missing_hits += 1
                if btn_missing_hits >= 6:
                    self.waiting_for_page = False
                    self.should_auto_start = False
                    self.current_state = "IDLE"
                    self.status_item.title = "Status: Ready"
                    self._prompt_service_login("录音按钮不可用，请登录或检查权限后重试。")
                    return
            else:
                btn_missing_hits = 0

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


        # Branch based on AI Pipe mode
        text = ""
        if (self.current_service == "ChatGPT" and 
            self.current_pipe_slot >= 0 and 
            self.pipe_slots[self.current_pipe_slot]):
            # --- AI Pipe Mode ---
            text = self._wait_and_copy_response()
            if text and self.target_app:
                self.target_app.activateWithOptions_(NSApplicationActivateIgnoringOtherApps)
                time.sleep(0.2)
                paste_text(text, snapshot=None)  # No clipboard restoration in AI mode
            
            self.current_state = "IDLE"
            self.status_item.title = "Status: Ready"
            return

        # --- Standard Mode (Existing Flow) ---
        # Take a clipboard snapshot while we wait for transcription
        clipboard_snapshot = snapshot_clipboard()

        # Poll for transcribed text (total ~5s)
        text = ""
        force_activate = True
        max_attempts = 12

        for i in range(max_attempts):
            # Progressive retry intervals
            if i == 0:
                time.sleep(0.5)  # First attempt
            elif i == 1:
                time.sleep(0.1)  # 2nd attempt
            elif i == 2:
                time.sleep(0.2)  # 3rd attempt
            elif i == 3:
                time.sleep(0.3)  # 4th attempt
            elif i == 4:
                time.sleep(0.4)  # 5th attempt
            else:
                time.sleep(0.5)  # 5th+ attempts

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

    def _wait_and_copy_response(self, timeout=30):
        """Get transcription, combine with prompt, submit, and wait for AI response"""
        # Step 1: Get the transcription text from input box
        transcription = ""
        force_activate = True
        max_attempts = 12
        
        for i in range(max_attempts):
            if i == 0:
                time.sleep(0.5)
            elif i == 1:
                time.sleep(0.1)
            elif i == 2:
                time.sleep(0.2)
            else:
                time.sleep(0.5)
            
            res = self.chrome.get_text_and_clear(
                activate_first=force_activate,
                preferred_location=self.service_tab_location,
            )
            logger.debug(f"Getting transcription attempt {i+1}/{max_attempts}: {res}")
            force_activate = False
            
            if res.startswith("SUCCESS:"):
                content = res.split("SUCCESS:", 1)[1]
                if content.startswith("EMPTY|DBG=") or content.startswith("NOT_FOUND|DBG="):
                    logger.debug(content)
                    force_activate = True
                    continue
                
                if content and content not in ["EMPTY", "NOT_FOUND", "SUCCESS", "missing value"]:
                    transcription = content
                    logger.debug(f"Got transcription: {transcription[:50]}...")
                    break
                force_activate = True
        
        if not transcription:
            logger.error("Failed to get transcription")
            return ""
        
        # Step 2: Combine prompt with transcription
        prompt = self.pipe_slots[self.current_pipe_slot]
        combined_text = prompt + "\n" + transcription
        logger.debug(f"Combined text: {combined_text[:100]}...")
        
        # Step 3: Fill the combined text back into the input box
        try:
            fill_res = self.chrome.pre_fill_prompt(combined_text, preferred_location=self.service_tab_location)
            logger.debug(f"Fill result: {fill_res}")
            time.sleep(0.3)  # Wait for UI to update
        except Exception as e:
            logger.error(f"Failed to fill combined text: {e}")
            return ""
        
        # Step 4: Submit the message
        try:
            submit_res = self.chrome.submit_message(preferred_location=self.service_tab_location)
            logger.debug(f"Submit result: {submit_res}")
            if "NOT_FOUND" in submit_res or "DISABLED" in submit_res:
                logger.error(f"Submit failed: {submit_res}")
                return ""
        except Exception as e:
            logger.error(f"Failed to submit message: {e}")
            return ""

        # Step 5: Poll for response completion
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                status = self.chrome.is_response_complete(preferred_location=self.service_tab_location)
                if "COMPLETE" in status:
                    break
                elif "ERROR" in status:
                    logger.error(f"Response error: {status}")
                    return ""
            except Exception as e:
                logger.debug(f"Error checking response status: {e}")
            time.sleep(0.5)
        else:
            logger.error("Timeout waiting for AI response")
            rumps.notification("MicPipe", "Timeout", "AI response took too long")
            return ""

        # Step 6: Extract AI response text directly from DOM
        try:
            # Short wait for UI to stabilize
            time.sleep(1.0)
            extract_res = self.chrome.click_copy_button(preferred_location=self.service_tab_location)
            logger.debug(f"Text extraction result: {extract_res}")
            
            if extract_res.startswith("SUCCESS:"):
                # Parse the inner result
                inner = extract_res.split("SUCCESS:", 1)[1]
                # Format: USED_WIN_ID=xxx,TAB=x:TEXT:actual text
                # or just: TEXT:actual text
                if ":TEXT:" in inner:
                    text = inner.split(":TEXT:", 1)[1]
                    return text
                elif inner.startswith("TEXT:"):
                    text = inner.split("TEXT:", 1)[1]
                    return text
                elif inner in ["NO_RESPONSE", "EMPTY_RESPONSE"]:
                    logger.error(f"No AI response found: {inner}")
                    return ""
                else:
                    # Unexpected format, log it
                    logger.error(f"Unexpected extraction result format: {inner}")
                    return ""
            else:
                logger.error(f"Extraction failed: {extract_res}")
                return ""
        except Exception as e:
            logger.error(f"Failed to extract AI response: {e}")
            return ""

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
