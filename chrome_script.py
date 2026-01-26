import subprocess
import base64
import os
import logging

logger = logging.getLogger(__name__)

def run_applescript(script):
    """Run AppleScript and return the result"""
    wrapped = (
        'try\n'
        + script
        + '\n'
        + 'on error errMsg number errNum\n'
        + 'return "__MICPIPE_APPLESCRIPT_ERROR__:" & errNum & ":" & errMsg\n'
        + 'end try'
    )
    process = subprocess.Popen(
        ["osascript", "-e", wrapped],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    out, err = process.communicate()
    out = (out or "").strip()
    
    debug = os.environ.get("MICPIPE_DEBUG_APPLESCRIPT") in ("1", "true", "TRUE", "yes", "YES")
    if out.startswith("__MICPIPE_APPLESCRIPT_ERROR__:"):
        if debug:
            logger.debug(out)
        return out
    return out

class ChromeController:
    """Base class for controlling various AI chat interfaces in Chrome."""
    def __init__(self, service_name, url_pattern, title_pattern):
        self.service_name = service_name
        self.url_pattern = url_pattern
        self.title_pattern = title_pattern

    def get_tab_location(self):
        """Return (window_id, tab_index) for the first matching tab, or None."""
        script = f'''
        tell application "Google Chrome"
            if (count of windows) = 0 then return "NOT_FOUND"
            repeat with win in windows
                set tabIndex to 1
                repeat with t in tabs of win
                    try
                        if (URL of t contains "{self.url_pattern}") or (title of t contains "{self.title_pattern}") then
                            return "WIN_ID:" & (id of win) & ",TAB:" & tabIndex
                        end if
                    end try
                    set tabIndex to tabIndex + 1
                end repeat
            end repeat
            return "NOT_FOUND"
        end tell
        '''
        res = run_applescript(script)
        if not res or res.startswith("__MICPIPE_APPLESCRIPT_ERROR__"):
            return None
        if res.startswith("WIN_ID:") and ",TAB:" in res:
            try:
                win_part, tab_part = res.split(",TAB:")
                win_id = int(win_part.replace("WIN_ID:", ""))
                tab_idx = int(tab_part)
                return (win_id, tab_idx)
            except Exception:
                return None
        return None

    def get_front_tab_location(self):
        """Return (window_id, tab_index) if the front tab matches, else None."""
        script = f'''
        tell application "Google Chrome"
            if (count of windows) = 0 then return "NOT_FOUND"
            try
                set frontWin to front window
                set winId to id of frontWin
                set tabIndex to active tab index of frontWin
                set t to active tab of frontWin
                if (URL of t contains "{self.url_pattern}") or (title of t contains "{self.title_pattern}") then
                    return "WIN_ID:" & winId & ",TAB:" & tabIndex
                end if
            end try
            return "NOT_MATCHED"
        end tell
        '''
        res = run_applescript(script)
        if not res or res.startswith("__MICPIPE_APPLESCRIPT_ERROR__"):
            return None
        if res.startswith("WIN_ID:") and ",TAB:" in res:
            try:
                win_part, tab_part = res.split(",TAB:")
                win_id = int(win_part.replace("WIN_ID:", ""))
                tab_idx = int(tab_part)
                return (win_id, tab_idx)
            except Exception:
                return None
        return None

    def _execute_js(self, js_code, preferred_location=None, open_url=None):
        b64_js = base64.b64encode(js_code.encode('utf-8')).decode('utf-8')

        # Check if preferred_location is window_id or URL based on type
        preferred_win_id = 0
        preferred_tab_index = 0
        if preferred_location and len(preferred_location) == 2:
            try:
                # Try to parse first element as int (window ID)
                preferred_win_id = int(preferred_location[0])
                preferred_tab_index = int(preferred_location[1])
            except (ValueError, TypeError):
                # Not a number, might be URL from new code
                preferred_win_id = 0
                preferred_tab_index = 0

        script = f'''
        tell application "Google Chrome"
            if not (exists window 1) then
                if "{open_url}" is not "None" then
                    make new window with properties {{URL:"{open_url}"}}
                    return "OPENING_NEW_WINDOW"
                end if
                return "NO_WINDOW"
            end if

            -- If preferred window ID is provided, try it first
            if {preferred_win_id} > 0 and {preferred_tab_index} > 0 then
                set foundWin to missing value
                set targetWinId to {preferred_win_id} as integer

                repeat with win in windows
                    set currentWinId to (id of win) as integer
                    if currentWinId = targetWinId then
                        set foundWin to win
                        exit repeat
                    end if
                end repeat

                if foundWin is not missing value then
                    try
                        set pt to tab {preferred_tab_index} of foundWin
                        set res to execute pt javascript "eval(decodeURIComponent(escape(window.atob('{b64_js}'))))"
                        return "SUCCESS:USED_WIN_ID=" & {preferred_win_id} & ":" & res
                    on error errMsg
                        -- Tab access failed, fall through to fallback
                    end try
                end if
            end if

            -- Fallback: search all windows for matching tab
            repeat with win in windows
                set tIdx to 1
                repeat with t in tabs of win
                    try
                        if (URL of t contains "{self.url_pattern}") or (title of t contains "{self.title_pattern}") then
                            set res to execute t javascript "eval(decodeURIComponent(escape(window.atob('{b64_js}'))))"
                            return "SUCCESS:FALLBACK_WIN_ID=" & (id of win) & ":" & res
                        end if
                    end try
                    set tIdx to tIdx + 1
                end repeat
            end repeat

            if "{open_url}" is not "None" then
                make new tab at window 1 with properties {{URL:"{open_url}"}}
                return "OPENING_NEW_TAB"
            end if
            return "NOT_FOUND"
        end tell
        '''
        result = run_applescript(script)
        logger.debug(f"[_execute_js] preferred_win_id={preferred_win_id}, result={result[:200]}")
        return result

    def is_front_tab_match(self) -> bool:
        return self.get_front_tab_location() is not None

class ChatGPTChrome(ChromeController):
    def __init__(self):
        super().__init__("ChatGPT", "chatgpt.com", "ChatGPT")

    def ensure_chatgpt_tab_exists(self):
        """Check if a ChatGPT tab exists, create one if not. Returns status string."""
        location = self.get_tab_location()
        if location:
            return "EXISTS"
        # No tab found, create one
        js = 'return "TAB_CHECK";'
        res = self._execute_js(js, open_url="https://chatgpt.com")
        if "OPENING" in res:
            return "CREATED"
        return res

    def is_front_tab_chatgpt(self):
        """Check if the front tab in Chrome is a ChatGPT tab. Returns 'YES' or 'NO'."""
        return "YES" if self.get_front_tab_location() is not None else "NO"

    def get_chatgpt_tab_location(self):
        """Alias for get_tab_location for clarity."""
        return self.get_tab_location()

    def get_front_chatgpt_tab_location(self):
        """Alias for get_front_tab_location for clarity."""
        return self.get_front_tab_location()

    def is_page_ready(self, preferred_location=None):
        js = '''
        (function() {
            if (document.readyState !== 'complete') return "PAGE_NOT_READY";
            var buttons = Array.from(document.querySelectorAll('button'));
            var btn = buttons.find(b =>
                (b.ariaLabel && b.ariaLabel.toLowerCase().includes('dictate')) ||
                b.querySelector('svg path[d*="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"]')
            );
            return btn ? "READY" : "BTN_NOT_FOUND";
        })()
        '''
        return self._execute_js(js, preferred_location)

    def start_dictation(self, preferred_location=None):
        js = '''
        (function() {
            var buttons = Array.from(document.querySelectorAll('button'));
            var btn = buttons.find(b =>
                (b.ariaLabel && b.ariaLabel.toLowerCase().includes('dictate')) ||
                b.querySelector('svg path[d*="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"]')
            );
            if (btn) { btn.click(); return "START_DONE"; }
            return "START_BTN_NOT_FOUND";
        })()
        '''
        return self._execute_js(js, preferred_location, open_url="https://chatgpt.com")

    def stop_dictation(self, preferred_location=None):
        """Stop dictation by clicking Submit dictation button to finish and keep transcribed text."""
        js = '''
        (function() {
            // Return window ID for debugging
            var winInfo = "UNKNOWN";
            try {
                winInfo = window.location.href;
            } catch(e) {}

            var buttons = Array.from(document.querySelectorAll('button'));
            // Submit dictation button - finishes recording and keeps transcribed text
            var btn = buttons.find(b =>
                (b.ariaLabel && b.ariaLabel.includes('Submit dictation')) ||
                b.querySelector('svg path[d*="M20 6L9 17l-5-5"]')
            );
            if (btn) {
                btn.click();
                return "SUBMIT_CLICKED:URL=" + winInfo;
            }
            return "SUBMIT_BTN_NOT_FOUND:URL=" + winInfo;
        })()
        '''
        result = self._execute_js(js, preferred_location)
        logger.debug(f"[stop_dictation] preferred_location={preferred_location}, result={result}")
        return result

    def cancel_dictation(self, preferred_location=None):
        js = '''
        (function() {
            var buttons = Array.from(document.querySelectorAll('button'));
            var btn = buttons.find(b => b.ariaLabel && b.ariaLabel.toLowerCase().includes('stop dictation'));
            if (btn) { btn.click(); return "CANCEL_DONE"; }
            return "CANCEL_BTN_NOT_FOUND";
        })()
        '''
        return self._execute_js(js, preferred_location)

    def get_text_and_clear(self, activate_first=True, preferred_location=None):
        js_code = '''
        (function() {
            var textarea = document.querySelector('#prompt-textarea');
            if (textarea) {
                var text = textarea.value || textarea.innerText || textarea.textContent || "";
                if (!text.trim()) return "EMPTY";
                textarea.value = "";
                textarea.innerText = "";
                textarea.innerHTML = "";
                textarea.dispatchEvent(new Event('input', { bubbles: true }));
                textarea.dispatchEvent(new Event('change', { bubbles: true }));
                return text.trim();
            }
            return "NOT_FOUND";
        })()
        '''
        if not activate_first:
            return self._execute_js(js_code, preferred_location)

        b64_js = base64.b64encode(js_code.encode('utf-8')).decode('utf-8')
        win_id, tab_idx = preferred_location if preferred_location else (0, 0)

        script = f'''
        tell application "Google Chrome"
            set originalWin to front window
            set originalTabIndex to active tab index of originalWin

            set targetWin to missing value
            set targetTab to missing value
            set targetTabIndex to 0

            -- Find window by ID
            if {win_id} > 0 and {tab_idx} > 0 then
                try
                    set targetWinId to {win_id} as integer
                    repeat with win in windows
                        set currentWinId to (id of win) as integer
                        if currentWinId = targetWinId then
                            set targetWin to win
                            set targetTab to tab {tab_idx} of targetWin
                            set targetTabIndex to {tab_idx}
                            exit repeat
                        end if
                    end repeat
                end try
            end if

            -- Fallback: search for matching tab
            if targetTab is missing value then
                repeat with win in windows
                    set tIdx to 1
                    repeat with t in tabs of win
                        if (URL of t contains "{self.url_pattern}") or (title of t contains "{self.title_pattern}") then
                            set targetWin to win
                            set targetTab to t
                            set targetTabIndex to tIdx
                            exit repeat
                        end if
                        set tIdx to tIdx + 1
                    end repeat
                    if targetTab is not missing value then exit repeat
                end repeat
            end if

            if targetTab is missing value then return "NOT_FOUND"

            set active tab index of targetWin to targetTabIndex
            set index of targetWin to 1
            delay 0.15
            set res to execute targetTab javascript "eval(decodeURIComponent(escape(window.atob('{b64_js}'))))"

            try
                set index of originalWin to 1
                set active tab index of originalWin to originalTabIndex
            end try
            return "SUCCESS:" & res
        end tell
        '''
        return run_applescript(script)

class GeminiChrome(ChromeController):
    def __init__(self):
        super().__init__("Gemini", "gemini.google.com", "Gemini")

    def ensure_gemini_tab_exists(self):
        """Check if a Gemini tab exists, create one if not. Returns status string."""
        location = self.get_tab_location()
        if location:
            return "EXISTS"
        js = 'return "TAB_CHECK";'
        res = self._execute_js(js, open_url="https://gemini.google.com/app")
        if "OPENING" in res:
            return "CREATED"
        return res

    def is_front_tab_gemini(self):
        """Check if the front tab in Chrome is a Gemini tab. Returns 'YES' or 'NO'."""
        return "YES" if self.get_front_tab_location() is not None else "NO"

    def get_gemini_tab_location(self):
        """Alias for get_tab_location for clarity."""
        return self.get_tab_location()

    def get_front_gemini_tab_location(self):
        """Alias for get_front_tab_location for clarity."""
        return self.get_front_tab_location()

    def is_page_ready(self, preferred_location=None):
        js = '''
        (function() {
            if (document.readyState !== 'complete') return "PAGE_NOT_READY";
            var btn = document.querySelector('.speech_dictation_mic_button');
            return btn ? "READY" : "BTN_NOT_FOUND";
        })()
        '''
        return self._execute_js(js, preferred_location)

    def start_dictation(self, preferred_location=None):
        js = '''
        (function() {
            var btn = document.querySelector('.speech_dictation_mic_button');
            if (btn) { btn.click(); return "START_DONE"; }
            return "START_BTN_NOT_FOUND";
        })()
        '''
        return self._execute_js(js, preferred_location, open_url="https://gemini.google.com/app")

    def stop_dictation(self, preferred_location=None):
        """Stop dictation - in Gemini, clicking the mic button again stops and submits."""
        js = '''
        (function() {
            // Check if mic is actively listening (has mic-on icon)
            var micOn = document.querySelector('.speech_dictation_mic_button mat-icon.mic-on');
            if (micOn) {
                // Click the mic button to stop and submit
                var btn = document.querySelector('.speech_dictation_mic_button');
                if (btn) { btn.click(); return "STOP_CLICKED"; }
            }
            // Fallback: try to find and click the send button if transcription is ready
            var sendBtn = document.querySelector('button.send-button');
            if (sendBtn) { sendBtn.click(); return "SEND_CLICKED"; }
            return "STOP_BTN_NOT_FOUND";
        })()
        '''
        return self._execute_js(js, preferred_location)

    def cancel_dictation(self, preferred_location=None):
        """Gemini does not support cancel - this is a no-op that returns a status."""
        return "CANCEL_NOT_SUPPORTED"

    def get_text_and_clear(self, activate_first=True, preferred_location=None):
        js_code = '''
        (function() {
            try {
                // Gemini uses .ql-editor with role=textbox
                // It can have different aria-labels depending on language
                var editor = document.querySelector('.ql-editor[role="textbox"]');

                // Fallback 1: Any ql-editor (Quill editor)
                if (!editor) {
                    editor = document.querySelector('.ql-editor');
                }

                // Fallback 2: contenteditable div with role=textbox
                if (!editor) {
                    editor = document.querySelector('div[contenteditable="true"][role="textbox"]');
                }

                if (!editor) {
                    return "NOT_FOUND";
                }

                // Get text - innerText works better for contenteditable
                var text = (editor.innerText || editor.textContent || "").trim();

                if (!text) {
                    return "EMPTY";
                }

                // Clear the editor by removing all child nodes
                while (editor.firstChild) {
                    editor.removeChild(editor.firstChild);
                }

                // Trigger events
                try {
                    editor.dispatchEvent(new Event('input', { bubbles: true }));
                    editor.dispatchEvent(new Event('change', { bubbles: true }));
                } catch(e) {}

                return text;
            } catch(err) {
                return "ERROR:" + err.message;
            }
        })()
        '''
        if not activate_first:
            return self._execute_js(js_code, preferred_location)

        b64_js = base64.b64encode(js_code.encode('utf-8')).decode('utf-8')
        win_id, tab_idx = preferred_location if preferred_location else (0, 0)

        script = f'''
        tell application "Google Chrome"
            set originalWin to front window
            set originalTabIndex to active tab index of originalWin

            set targetWin to missing value
            set targetTab to missing value
            set targetTabIndex to 0

            -- Find window by ID
            if {win_id} > 0 and {tab_idx} > 0 then
                try
                    set targetWinId to {win_id} as integer
                    repeat with win in windows
                        set currentWinId to (id of win) as integer
                        if currentWinId = targetWinId then
                            set targetWin to win
                            set targetTab to tab {tab_idx} of targetWin
                            set targetTabIndex to {tab_idx}
                            exit repeat
                        end if
                    end repeat
                end try
            end if

            -- Fallback: search for matching tab
            if targetTab is missing value then
                repeat with win in windows
                    set tIdx to 1
                    repeat with t in tabs of win
                        if (URL of t contains "gemini.google.com") or (title of t contains "Gemini") then
                            set targetWin to win
                            set targetTab to t
                            set targetTabIndex to tIdx
                            exit repeat
                        end if
                        set tIdx to tIdx + 1
                    end repeat
                    if targetTab is not missing value then exit repeat
                end repeat
            end if

            if targetTab is missing value then return "NOT_FOUND"

            set active tab index of targetWin to targetTabIndex
            set index of targetWin to 1
            delay 0.15
            set res to execute targetTab javascript "eval(decodeURIComponent(escape(window.atob('{b64_js}'))))"

            try
                set index of originalWin to 1
                set active tab index of originalWin to originalTabIndex
            end try
            return "SUCCESS:" & res
        end tell
        '''
        return run_applescript(script)
