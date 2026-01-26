#!/usr/bin/env python3
"""Simple test for Gemini text extraction"""

from chrome_script import GeminiChrome

gemini = GeminiChrome()

# Very simple test
js = '''
(function() {
    var editor = document.querySelector('div[aria-label="Enter a prompt here"][role="textbox"]');
    if (!editor) return "EDITOR_NOT_FOUND";
    var text = editor.innerText || "";
    return "TEXT_LENGTH:" + text.length + " CONTENT:" + text.substring(0, 100);
})()
'''

print("Testing Gemini text extraction...")
print("Make sure Gemini tab has text in the input box")
input("Press Enter to test...")

result = gemini._execute_js(js)
print(f"\nResult: {result}")
