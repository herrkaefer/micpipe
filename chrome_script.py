import subprocess
import base64
import os
import logging
import json

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
    def __init__(self, service_name, url_pattern, title_pattern, default_url):
        self.service_name = service_name
        self.url_pattern = url_pattern
        self.title_pattern = title_pattern
        self.default_url = default_url

    def create_dedicated_window(self, bounds=(50, 50, 500, 400)):
        """Create a dedicated Chrome window and return (window_id, tab_index) or None."""
        open_url = self.default_url
        script = f'''
        tell application "Google Chrome"
            if (count of windows) = 0 then
                make new window
            end if
            set newWin to make new window with properties {{bounds:{{{bounds[0]}, {bounds[1]}, {bounds[2]}, {bounds[3]}}}}}
            set URL of active tab of newWin to "{open_url}"
            if (count of windows) > 1 then
                set index of newWin to (count of windows)
            end if
            return "WIN_ID:" & (id of newWin) & ",TAB:1"
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

    def is_window_alive(self, window_id, tab_index) -> bool:
        """Check if a specific window/tab still exists and matches the service."""
        try:
            win_id = int(window_id)
            tab_idx = int(tab_index)
        except (ValueError, TypeError):
            return False
        if win_id <= 0 or tab_idx <= 0:
            return False

        script = f'''
        tell application "Google Chrome"
            if (count of windows) = 0 then return "NO_WINDOW"
            set targetWin to missing value
            set targetWinId to {win_id} as integer
            repeat with win in windows
                set currentWinId to (id of win) as integer
                if currentWinId = targetWinId then
                    set targetWin to win
                    exit repeat
                end if
            end repeat
            if targetWin is missing value then return "NOT_FOUND"
            try
                set t to tab {tab_idx} of targetWin
            on error
                return "TAB_NOT_FOUND"
            end try
            set tUrl to ""
            set tTitle to ""
            try
                set tUrl to (URL of t) as text
            end try
            try
                set tTitle to (title of t) as text
            end try
            if (tUrl contains "{self.url_pattern}") or (tTitle contains "{self.title_pattern}") then
                return "OK"
            end if
            return "MISMATCH"
        end tell
        '''
        res = run_applescript(script)
        return res == "OK"

    def reveal_window(self, window_id, bounds=(60, 60, 1100, 800)) -> bool:
        """Resize and bring a Chrome window to the front."""
        try:
            win_id = int(window_id)
        except (ValueError, TypeError):
            return False
        if win_id <= 0:
            return False
        script = f'''
        tell application "Google Chrome"
            if (count of windows) = 0 then return "NO_WINDOW"
            set targetWin to missing value
            set targetWinId to {win_id} as integer
            repeat with win in windows
                set currentWinId to (id of win) as integer
                if currentWinId = targetWinId then
                    set targetWin to win
                    exit repeat
                end if
            end repeat
            if targetWin is missing value then return "NOT_FOUND"
            set bounds of targetWin to {{{bounds[0]}, {bounds[1]}, {bounds[2]}, {bounds[3]}}}
            set index of targetWin to 1
            activate
            return "OK"
        end tell
        '''
        res = run_applescript(script)
        return res == "OK"

    def set_window_bounds(self, window_id, bounds) -> bool:
        """Resize/move a Chrome window without changing focus."""
        try:
            win_id = int(window_id)
        except (ValueError, TypeError):
            return False
        if win_id <= 0:
            return False
        script = f'''
        tell application "Google Chrome"
            if (count of windows) = 0 then return "NO_WINDOW"
            set targetWin to missing value
            set targetWinId to {win_id} as integer
            repeat with win in windows
                set currentWinId to (id of win) as integer
                if currentWinId = targetWinId then
                    set targetWin to win
                    exit repeat
                end if
            end repeat
            if targetWin is missing value then return "NOT_FOUND"
            set bounds of targetWin to {{{bounds[0]}, {bounds[1]}, {bounds[2]}, {bounds[3]}}}
            return "OK"
        end tell
        '''
        res = run_applescript(script)
        return res == "OK"

    def demote_window(self, window_id) -> bool:
        """Push a Chrome window to the back of the window stack so it is no longer the 'last active' window.

        This prevents the dedicated (hidden) window from hijacking external link opens.
        Only acts when Chrome has 2+ windows; single-window case is a no-op.
        """
        try:
            win_id = int(window_id)
        except (ValueError, TypeError):
            return False
        if win_id <= 0:
            return False
        script = f'''
        tell application "Google Chrome"
            if (count of windows) < 2 then return "SKIP"
            set targetWin to missing value
            set targetWinId to {win_id} as integer
            repeat with win in windows
                set currentWinId to (id of win) as integer
                if currentWinId = targetWinId then
                    set targetWin to win
                    exit repeat
                end if
            end repeat
            if targetWin is missing value then return "NOT_FOUND"
            set index of targetWin to (count of windows)
            return "OK"
        end tell
        '''
        res = run_applescript(script)
        return res in ("OK", "SKIP")

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
            if (count of windows) = 0 then return "NO_WINDOW"
            if {preferred_win_id} <= 0 or {preferred_tab_index} <= 0 then return "NO_LOCATION"

            set foundWin to missing value
            set targetWinId to {preferred_win_id} as integer

            repeat with win in windows
                set currentWinId to (id of win) as integer
                if currentWinId = targetWinId then
                    set foundWin to win
                    exit repeat
                end if
            end repeat

            if foundWin is missing value then return "NOT_FOUND"

            try
                set pt to tab {preferred_tab_index} of foundWin
            on error
                return "NOT_FOUND"
            end try

            -- Verify the preferred tab is still the right service tab.
            set ptUrl to ""
            set ptTitle to ""
            try
                set ptUrl to (URL of pt) as text
            end try
            try
                set ptTitle to (title of pt) as text
            end try

            if not ((ptUrl contains "{self.url_pattern}") or (ptTitle contains "{self.title_pattern}")) then
                return "NOT_FOUND"
            end if

            set res to execute pt javascript "eval(decodeURIComponent(escape(window.atob('{b64_js}'))))"
            return "SUCCESS:USED_WIN_ID=" & {preferred_win_id} & ",TAB=" & {preferred_tab_index} & ":" & res
        end tell
        '''
        result = run_applescript(script)
        logger.debug(f"[_execute_js] preferred_win_id={preferred_win_id}, result={result[:200]}")
        return result

    def is_front_tab_match(self) -> bool:
        return self.get_front_tab_location() is not None

class ChatGPTChrome(ChromeController):
    def __init__(self):
        super().__init__("ChatGPT", "chatgpt.com", "ChatGPT", "https://chatgpt.com")

    def ensure_chatgpt_tab_exists(self):
        """Create a dedicated ChatGPT window. Returns status string."""
        location = self.create_dedicated_window()
        return "CREATED" if location else "ERROR"

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
        return self._execute_js(js, preferred_location)

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
            // Submit dictation button - finishes recording and keeps transcribed text.
            // If this selector fails due to UI/locale changes, the caller should notify the user.
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
            function diag(payload) {
                try { return JSON.stringify(payload); } catch (e) { return String(payload); }
            }

            function isVisible(el) {
                try {
                    if (!el) return false;
                    var r = el.getBoundingClientRect();
                    return !!(r && r.width > 0 && r.height > 0);
                } catch (e) {
                    return false;
                }
            }

            function findComposerBox() {
                // 1) Known stable IDs / test IDs (varies by rollout)
                var el = document.querySelector('#prompt-textarea');
                if (el) return { el: el, via: '#prompt-textarea' };

                el = document.querySelector('[data-testid="prompt-textarea"]');
                if (el) return { el: el, via: '[data-testid=\"prompt-textarea\"]' };

                // 2) Prefer the textbox inside the form that owns the send button (less ambiguity)
                var sendBtn = document.querySelector('button[data-testid="send-button"]');
                if (sendBtn && sendBtn.closest) {
                    var form = sendBtn.closest('form');
                    if (form) {
                        el =
                            form.querySelector('#prompt-textarea') ||
                            form.querySelector('[data-testid="prompt-textarea"]') ||
                            form.querySelector('textarea') ||
                            form.querySelector('div[contenteditable="true"][role="textbox"]') ||
                            form.querySelector('div[contenteditable="true"]');
                        if (el) return { el: el, via: 'send-button.closest(form)' };
                    }
                }

                // 3) Last resort: pick a visible textarea/contenteditable textbox
                var candidates = []
                    .concat(Array.from(document.querySelectorAll('textarea')))
                    .concat(Array.from(document.querySelectorAll('div[contenteditable="true"][role="textbox"]')))
                    .concat(Array.from(document.querySelectorAll('div[contenteditable="true"]')));

                for (var i = 0; i < candidates.length; i++) {
                    if (isVisible(candidates[i])) return { el: candidates[i], via: 'visible-candidate' };
                }
                return null;
            }

            var found = findComposerBox();
            if (!found || !found.el) {
                return "NOT_FOUND|DBG=" + diag({
                    href: (function(){ try { return location.href; } catch(e) { return null; } })(),
                    title: (function(){ try { return document.title; } catch(e) { return null; } })(),
                    promptTextareas: document.querySelectorAll('#prompt-textarea').length,
                    testidTextareas: document.querySelectorAll('[data-testid="prompt-textarea"]').length,
                    sendButtons: document.querySelectorAll('button[data-testid="send-button"]').length,
                });
            }
            var box = found.el;

            // Ensure the composer is focused; in some UI states transcription is only materialized after focus.
            try { box.focus(); } catch(e) {}

            var text = "";
            try {
                if (typeof box.value === 'string') text = box.value;
                if (!text) text = box.innerText || box.textContent || "";
            } catch(e) {}

            if (!text || !text.trim()) {
                var valLen = 0;
                var innerLen = 0;
                try { valLen = (typeof box.value === 'string') ? box.value.length : 0; } catch(e) {}
                try { innerLen = (box.innerText || box.textContent || "").length; } catch(e) {}
                return "EMPTY|DBG=" + diag({
                    href: (function(){ try { return location.href; } catch(e) { return null; } })(),
                    title: (function(){ try { return document.title; } catch(e) { return null; } })(),
                    via: found.via,
                    tag: (function(){ try { return box.tagName; } catch(e) { return null; } })(),
                    id: (function(){ try { return box.id; } catch(e) { return null; } })(),
                    dataTestid: (function(){ try { return box.getAttribute('data-testid'); } catch(e) { return null; } })(),
                    isVisible: isVisible(box),
                    valLen: valLen,
                    innerLen: innerLen,
                });
            }

            // Clear composer
            try {
                if (typeof box.value === 'string') box.value = "";
            } catch(e) {}
            try {
                box.innerText = "";
                box.textContent = "";
                box.innerHTML = "";
            } catch(e) {}

            try {
                box.dispatchEvent(new Event('input', { bubbles: true }));
                box.dispatchEvent(new Event('change', { bubbles: true }));
            } catch(e) {}

            return text.trim();
        })()
        '''
        if not activate_first:
            return self._execute_js(js_code, preferred_location)

        if not preferred_location:
            return "NO_LOCATION"
        b64_js = base64.b64encode(js_code.encode('utf-8')).decode('utf-8')
        win_id, tab_idx = preferred_location

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

            -- Validate the preferred tab is still the right service tab.
            if targetTab is not missing value then
                set ptUrl to ""
                set ptTitle to ""
                try
                    set ptUrl to (URL of targetTab) as text
                end try
                try
                    set ptTitle to (title of targetTab) as text
                end try
                if not ((ptUrl contains "{self.url_pattern}") or (ptTitle contains "{self.title_pattern}")) then
                    return "NOT_FOUND"
                end if
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
            try
                if (count of windows) > 1 then
                    set index of targetWin to (count of windows)
                end if
            end try
            return "SUCCESS:" & res
        end tell
        '''
        return run_applescript(script)

    def pre_fill_prompt(self, prompt, preferred_location=None):
        """Pre-fill prompt text in the input box using execCommand for better reactivity"""
        js_code = f'''
        (function() {{
            var box = document.querySelector('#prompt-textarea');
            if (!box) {{
                box = document.querySelector('[data-testid="prompt-textarea"]');
            }}
            if (!box) return "NOT_FOUND";
            
            try {{
                box.focus();
                // Select all and delete (clear)
                document.execCommand('selectAll', false, null);
                document.execCommand('delete', false, null);
                
                // Insert text via execCommand (this triggers React state updates more reliably)
                var success = document.execCommand('insertText', false, {json.dumps(prompt)});
                
                if (!success) {{
                    // Fallback to setting property
                    if (box.tagName === 'TEXTAREA' || typeof box.value === 'string') {{
                        box.value = {json.dumps(prompt)};
                    }} else {{
                        box.innerText = {json.dumps(prompt)};
                    }}
                    box.dispatchEvent(new Event('input', {{ bubbles: true }}));
                    box.dispatchEvent(new Event('change', {{ bubbles: true }}));
                }}
                
                return "SUCCESS";
            }} catch(e) {{
                return "ERROR:" + e.message;
            }}
        }})()
        '''
        return self._execute_js(js_code, preferred_location)


    def submit_message(self, preferred_location=None):
        """Click the send button to submit the message"""
        js = '''
        (function() {
            var sendBtn = document.querySelector('button[data-testid="send-button"]') ||
                          document.querySelector('button[aria-label="Send prompt"]') ||
                          document.querySelector('button[data-testid="composer-submit-button"]') ||
                          document.querySelector('#composer-submit-button');
            
            // If still not found, search by SVG path (extreme fallback)
            if (!sendBtn) {
                var svgs = document.querySelectorAll('svg');
                for (var i = 0; i < svgs.length; i++) {
                    if (svgs[i].innerHTML.indexOf('M15.192') !== -1) { // ChatGPT send icon signature
                        sendBtn = svgs[i].closest('button');
                        if (sendBtn) break;
                    }
                }
            }

            if (sendBtn) {
                if (sendBtn.disabled) return "SEND_BTN_DISABLED";
                sendBtn.click();
                return "SENT";
            }
            return "SEND_BTN_NOT_FOUND";
        })()
        '''
        return self._execute_js(js, preferred_location)


    def is_response_complete(self, preferred_location=None):
        """Check if AI response is complete (Simpler, more robust version)"""
        js = '''
        (function() {
            // 1. If stop button exists, we are definitely NOT done
            var stopBtn = document.querySelector('button[data-testid="stop-button"]') ||
                          document.querySelector('button[aria-label="Stop streaming"]') ||
                          document.querySelector('button[aria-label="Stop generating"]');
            if (stopBtn) return "GENERATING";
            
            // 2. Assistant messages check
            var assistants = document.querySelectorAll('[data-message-author-role="assistant"]');
            if (assistants.length === 0) return "NO_RESPONSE";
            
            // 3. check for streaming class as secondary indicator
            var isStreaming = !!document.querySelector('.streaming') || !!document.querySelector('.result-streaming');
            if (isStreaming) return "GENERATING";
            
            // 4. If stop button is gone and we have messages, we consider it potential completion
            return "COMPLETE";
        })()
        '''
        return self._execute_js(js, preferred_location)



    def click_copy_button(self, preferred_location=None):
        """Extract text content from the last AI response directly (no clipboard API needed)"""
        js = """
        (function() {
            var assistants = document.querySelectorAll('[data-message-author-role="assistant"]');
            if (assistants.length === 0) return "NO_RESPONSE";
            
            var lastAssistant = assistants[assistants.length - 1];
            
            // Find the markdown content container
            var mdContainer = lastAssistant.querySelector('.markdown') ||
                              lastAssistant.querySelector('[class*="markdown"]') ||
                              lastAssistant.querySelector('.prose') ||
                              lastAssistant;
            
            // Get text content, preserving some structure
            var text = "";
            
            // Try to get inner text which preserves line breaks better
            if (mdContainer) {
                text = mdContainer.innerText || mdContainer.textContent || "";
            }
            
            // Clean up the text
            text = text.trim();
            
            if (text) {
                return "TEXT:" + text;
            }
            return "EMPTY_RESPONSE";
        })()
        """
        return self._execute_js(js, preferred_location)



class GeminiChrome(ChromeController):
    def __init__(self):
        super().__init__("Gemini", "gemini.google.com", "Gemini", "https://gemini.google.com/app")

    def ensure_gemini_tab_exists(self):
        """Create a dedicated Gemini window. Returns status string."""
        location = self.create_dedicated_window()
        return "CREATED" if location else "ERROR"

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
        return self._execute_js(js, preferred_location)

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

        if not preferred_location:
            return "NO_LOCATION"
        b64_js = base64.b64encode(js_code.encode('utf-8')).decode('utf-8')
        win_id, tab_idx = preferred_location

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

            -- Validate the preferred tab is still the right service tab.
            if targetTab is not missing value then
                set ptUrl to ""
                set ptTitle to ""
                try
                    set ptUrl to (URL of targetTab) as text
                end try
                try
                    set ptTitle to (title of targetTab) as text
                end try
                if not ((ptUrl contains "{self.url_pattern}") or (ptTitle contains "{self.title_pattern}")) then
                    return "NOT_FOUND"
                end if
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
            try
                if (count of windows) > 1 then
                    set index of targetWin to (count of windows)
                end if
            end try
            return "SUCCESS:" & res
        end tell
        '''
        return run_applescript(script)
