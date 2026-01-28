#!/usr/bin/env python3
"""Standalone editor window for MicPipe slot editing"""
import sys
import json

def main():
    if len(sys.argv) < 4:
        print(json.dumps({"error": "Usage: slot_editor.py <slot_index> <title> <prompt>"}))
        sys.exit(1)
    
    slot_index = int(sys.argv[1])
    current_title = sys.argv[2]
    current_prompt = sys.argv[3]
    
    # Import Cocoa
    from AppKit import (
        NSApplication, NSWindow, NSTextField, NSTextView, NSScrollView,
        NSButton, NSFont, NSMakeRect, NSWindowStyleMaskTitled,
        NSWindowStyleMaskClosable, NSBackingStoreBuffered,
        NSBezelStyleRounded, NSFloatingWindowLevel,
        NSApplicationActivationPolicyRegular
    )
    from Foundation import NSObject
    import objc
    
    # Create application with regular activation policy (shows in dock, can receive focus)
    app = NSApplication.sharedApplication()
    app.setActivationPolicy_(NSApplicationActivationPolicyRegular)
    
    result = {"saved": False, "title": "", "prompt": ""}
    
    # Create window
    window_rect = NSMakeRect(200, 200, 500, 350)
    window = NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
        window_rect,
        NSWindowStyleMaskTitled | NSWindowStyleMaskClosable,
        NSBackingStoreBuffered,
        False
    )
    window.setTitle_(f"Edit Slot {slot_index + 1}")
    window.setLevel_(NSFloatingWindowLevel)  # Float above other windows
    
    content_view = window.contentView()
    
    # Title label
    title_label = NSTextField.alloc().initWithFrame_(NSMakeRect(20, 300, 460, 20))
    title_label.setStringValue_("Title (shown in menu):")
    title_label.setBezeled_(False)
    title_label.setDrawsBackground_(False)
    title_label.setEditable_(False)
    title_label.setSelectable_(False)
    content_view.addSubview_(title_label)
    
    # Title input
    title_field = NSTextField.alloc().initWithFrame_(NSMakeRect(20, 270, 460, 24))
    title_field.setStringValue_(current_title)
    title_field.setFont_(NSFont.systemFontOfSize_(13))
    title_field.setEditable_(True)
    title_field.setSelectable_(True)
    content_view.addSubview_(title_field)
    
    # Prompt label
    prompt_label = NSTextField.alloc().initWithFrame_(NSMakeRect(20, 240, 460, 20))
    prompt_label.setStringValue_("Prompt (multi-line, press Enter for new line):")
    prompt_label.setBezeled_(False)
    prompt_label.setDrawsBackground_(False)
    prompt_label.setEditable_(False)
    prompt_label.setSelectable_(False)
    content_view.addSubview_(prompt_label)
    
    # Prompt text view with scroll
    scroll_view = NSScrollView.alloc().initWithFrame_(NSMakeRect(20, 60, 460, 175))
    scroll_view.setBorderType_(1)
    scroll_view.setHasVerticalScroller_(True)
    
    prompt_text = NSTextView.alloc().initWithFrame_(NSMakeRect(0, 0, 440, 175))
    prompt_text.setString_(current_prompt)
    prompt_text.setFont_(NSFont.systemFontOfSize_(13))
    prompt_text.setEditable_(True)
    prompt_text.setSelectable_(True)
    prompt_text.setAllowsUndo_(True)
    
    scroll_view.setDocumentView_(prompt_text)
    content_view.addSubview_(scroll_view)
    
    # Button handler
    class ButtonHandler(NSObject):
        @objc.typedSelector(b'v@:@')
        def saveClicked_(self, sender):
            result["saved"] = True
            result["title"] = str(title_field.stringValue())
            result["prompt"] = str(prompt_text.string())
            app.stop_(None)
        
        @objc.typedSelector(b'v@:@')
        def cancelClicked_(self, sender):
            result["saved"] = False
            app.stop_(None)
    
    handler = ButtonHandler.alloc().init()
    
    cancel_btn = NSButton.alloc().initWithFrame_(NSMakeRect(380, 15, 100, 32))
    cancel_btn.setTitle_("Cancel")
    cancel_btn.setBezelStyle_(NSBezelStyleRounded)
    cancel_btn.setTarget_(handler)
    cancel_btn.setAction_(objc.selector(handler.cancelClicked_, signature=b'v@:@'))
    content_view.addSubview_(cancel_btn)
    
    save_btn = NSButton.alloc().initWithFrame_(NSMakeRect(270, 15, 100, 32))
    save_btn.setTitle_("Save")
    save_btn.setBezelStyle_(NSBezelStyleRounded)
    save_btn.setTarget_(handler)
    save_btn.setAction_(objc.selector(handler.saveClicked_, signature=b'v@:@'))
    content_view.addSubview_(save_btn)
    
    # Show window and activate
    window.center()
    window.makeKeyAndOrderFront_(None)
    window.makeFirstResponder_(title_field)
    
    # Activate this app (bring to front)
    app.activateIgnoringOtherApps_(True)
    
    # Run event loop
    app.run()
    
    # Output result as JSON
    print(json.dumps(result))


if __name__ == "__main__":
    main()
