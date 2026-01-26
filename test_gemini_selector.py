#!/usr/bin/env python3
"""Test script to check Gemini selectors"""

from chrome_script import GeminiChrome

gemini = GeminiChrome()

# Test finding the input area
js_test = '''
(function() {
    var results = [];

    // Test various selectors
    var selectors = [
        '.ql-editor[contenteditable="true"]',
        'div[contenteditable="true"].textarea',
        '.input-area-container rich-textarea div[contenteditable="true"]',
        'rich-textarea div[contenteditable="true"]',
        'div[contenteditable="true"]',
        '[contenteditable="true"]'
    ];

    for (var i = 0; i < selectors.length; i++) {
        var elem = document.querySelector(selectors[i]);
        if (elem) {
            results.push({
                selector: selectors[i],
                text: (elem.innerText || elem.textContent || "").substring(0, 50),
                className: elem.className || "",
                tagName: elem.tagName
            });
        }
    }

    return JSON.stringify(results);
})()
'''

print("Testing Gemini selectors...")
print("Please make sure you have a Gemini tab open with some text in the input box.")
input("Press Enter to continue...")

result = gemini._execute_js(js_test)
print("\nResult:")
print(result)
