import subprocess
import time
import base64
import os

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
            print(out)
        return out
    return out

class ChromeController:
    """Base class for controlling various AI chat interfaces in Chrome."""
    def __init__(self, service_name, url_pattern, title_pattern):
        self.service_name = service_name
        self.url_pattern = url_pattern
        self.title_pattern = title_pattern

    def get_tab_location(self):
        """Return (window_index, tab_index) for the first matching tab, or None."""
        script = f'''
        tell application "Google Chrome"
            if (count of windows) = 0 then return "NOT_FOUND"
            set winIndex to 1
            repeat with win in windows
                set tabIndex to 1
                repeat with t in tabs of win
                    try
                        if (URL of t contains "{self.url_pattern}") or (title of t contains "{self.title_pattern}") then
                            return "WIN:" & winIndex & ",TAB:" & tabIndex
                        end if
                    end try
                    set tabIndex to tabIndex + 1
                end repeat
                set winIndex to winIndex + 1
            end repeat
            return "NOT_FOUND"
        end tell
        '''
        res = run_applescript(script)
        if not res or res.startswith("__MICPIPE_APPLESCRIPT_ERROR__"):
            return None
        if res.startswith("WIN:") and ",TAB:" in res:
            try:
                win_part, tab_part = res.split(",TAB:")
                win_idx = int(win_part.replace("WIN:", ""))
                tab_idx = int(tab_part)
                return (win_idx, tab_idx)
            except Exception:
                return None
        return None

    def get_front_tab_location(self):
        """Return (window_index, tab_index) if the front tab matches, else None."""
        script = f'''
        tell application "Google Chrome"
            if (count of windows) = 0 then return "NOT_FOUND"
            try
                set frontWin to front window
                set winIndex to index of frontWin
                set tabIndex to active tab index of frontWin
                set t to active tab of frontWin
                if (URL of t contains "{self.url_pattern}") or (title of t contains "{self.title_pattern}") then
                    return "WIN:" & winIndex & ",TAB:" & tabIndex
                end if
            end try
            return "NOT_MATCHED"
        end tell
        '''
        res = run_applescript(script)
        if not res or res.startswith("__MICPIPE_APPLESCRIPT_ERROR__"):
            return None
        if res.startswith("WIN:") and ",TAB:" in res:
            try:
                win_part, tab_part = res.split(",TAB:")
                win_idx = int(win_part.replace("WIN:", ""))
                tab_idx = int(tab_part)
                return (win_idx, tab_idx)
            except Exception:
                return None
        return None

    def _execute_js(self, js_code, preferred_location=None, open_url=None):
        b64_js = base64.b64encode(js_code.encode('utf-8')).decode('utf-8')
        preferred_win_index = 0
        preferred_tab_index = 0
        if preferred_location and len(preferred_location) == 2:
            try:
                preferred_win_index = int(preferred_location[0])
                preferred_tab_index = int(preferred_location[1])
            except Exception:
                pass

        script = f'''
        tell application "Google Chrome"
            if not (exists window 1) then
                if "{open_url}" is not "None" then
                    make new window with properties {{URL:"{open_url}"}}
                    return "OPENING_NEW_WINDOW"
                end if
                return "NO_WINDOW"
            end if

            if {preferred_win_index} > 0 and {preferred_tab_index} > 0 then
                try
                    set pw to window {preferred_win_index}
                    set pt to tab {preferred_tab_index} of pw
                    if (URL of pt contains "{self.url_pattern}") or (title of pt contains "{self.title_pattern}") then
                        set res to execute pt javascript "eval(decodeURIComponent(escape(window.atob('{b64_js}'))))"
                        return "SUCCESS:" & res
                    end if
                end try
            end if
            
            repeat with win in windows
                set tIdx to 1
                repeat with t in tabs of win
                    try
                        if (URL of t contains "{self.url_pattern}") or (title of t contains "{self.title_pattern}") then
                            set res to execute t javascript "eval(decodeURIComponent(escape(window.atob('{b64_js}'))))"
                            return "SUCCESS:" & res
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
        return run_applescript(script)

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
            var buttons = Array.from(document.querySelectorAll('button'));
            // Submit dictation button - finishes recording and keeps transcribed text
            var btn = buttons.find(b =>
                (b.ariaLabel && b.ariaLabel.includes('Submit dictation')) ||
                b.querySelector('svg path[d*="M20 6L9 17l-5-5"]')
            );
            if (btn) { btn.click(); return "SUBMIT_CLICKED"; }
            return "SUBMIT_BTN_NOT_FOUND";
        })()
        '''
        return self._execute_js(js, preferred_location)

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
        win_idx, tab_idx = preferred_location if preferred_location else (0, 0)
        
        script = f'''
        tell application "Google Chrome"
            set originalWin to front window
            set originalTabIndex to active tab index of originalWin
            
            set targetWin to missing value
            set targetTab to missing value
            set targetTabIndex to 0

            if {win_idx} > 0 then
                try
                    set targetWin to window {win_idx}
                    set targetTab to tab {tab_idx} of targetWin
                    set targetTabIndex to {tab_idx}
                end try
            end if

            if targetTab is missing value then
                repeat with win in windows
                    set tIdx to 1
                    repeat with t in tabs of win
                        if (URL of t contains "chatgpt.com") or (title of t contains "ChatGPT") then
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

    def is_page_ready(self, preferred_location=None):
        js = '''
        (function() {
            if (document.readyState !== 'complete') return "PAGE_NOT_READY";
            var btn = document.querySelector('button[aria-label="Microphone"]');
            return btn ? "READY" : "BTN_NOT_FOUND";
        })()
        '''
        return self._execute_js(js, preferred_location)

    def start_dictation(self, preferred_location=None):
        js = '''
        (function() {
            var btn = document.querySelector('button[aria-label="Microphone"]');
            if (btn) { btn.click(); return "START_DONE"; }
            return "START_BTN_NOT_FOUND";
        })()
        '''
        return self._execute_js(js, preferred_location, open_url="https://gemini.google.com/app")

    def stop_dictation(self, preferred_location=None):
        js = '''
        (function() {
            // In Gemini, clicking the mic again stops it, or the send button appears
            var micOn = document.querySelector('button.speech_dictation_mic_button mat-icon.mic-on');
            if (micOn) {
                micOn.parentElement.click();
                return "STOP_MIC_CLICKED";
            }
            var sendBtn = document.querySelector('button[aria-label="Send message"]');
            if (sendBtn) {
                sendBtn.click();
                return "STOP_SEND_CLICKED";
            }
            return "STOP_FAILED";
        })()
        '''
        return self._execute_js(js, preferred_location)

    def cancel_dictation(self, preferred_location=None):
        js = '''
        (function() {
            var micOn = document.querySelector('button.speech_dictation_mic_button mat-icon.mic-on');
            if (micOn) { micOn.parentElement.click(); return "CANCEL_DONE"; }
            return "CANCEL_NOT_LISTENING";
        })()
        '''
        return self._execute_js(js, preferred_location)

    def get_text_and_clear(self, activate_first=True, preferred_location=None):
        js_code = '''
        (function() {
            var editor = document.querySelector('div[aria-label="Enter a prompt here"][role="textbox"]');
            if (editor) {
                var text = editor.innerText || editor.textContent || "";
                if (!text.trim()) return "EMPTY";
                editor.innerText = "";
                editor.innerHTML = "";
                editor.dispatchEvent(new Event('input', { bubbles: true }));
                return text.trim();
            }
            return "NOT_FOUND";
        })()
        '''
        if not activate_first:
            return self._execute_js(js_code, preferred_location)
        
        b64_js = base64.b64encode(js_code.encode('utf-8')).decode('utf-8')
        win_idx, tab_idx = preferred_location if preferred_location else (0, 0)
        
        script = f'''
        tell application "Google Chrome"
            set originalWin to front window
            set originalTabIndex to active tab index of originalWin
            
            set targetWin to missing value
            set targetTab to missing value
            set targetTabIndex to 0

            if {win_idx} > 0 then
                try
                    set targetWin to window {win_idx}
                    set targetTab to tab {tab_idx} of targetWin
                    set targetTabIndex to {tab_idx}
                end try
            end if

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
