#!/usr/bin/env python3
import os
from AppKit import (
    NSImage, NSBezierPath, NSColor, NSGraphicsContext,
    NSSize, NSPoint, NSBitmapImageRep, NSPNGFileType
)

def create_hollow_circle(filename, scale=1.0):
    size = 48 # Base size for @3x
    img = NSImage.alloc().initWithSize_(NSSize(size, size))
    img.lockFocus()
    
    # Set up drawing
    center = NSPoint(size/2, size/2)
    # Base radius is slightly smaller to allow for line thickness and scaling
    base_radius = size/2 - 6
    radius = base_radius * scale
    
    path = NSBezierPath.bezierPath()
    # Thicker line for better visibility
    path.setLineWidth_(4.5) 
    
    # Solid line (no dash) for a cleaner "hollow circle" look
    path.appendBezierPathWithArcWithCenter_radius_startAngle_endAngle_(
        center, radius, 0, 360
    )
    
    # Draw in black (template mode will handle reversing for dark mode)
    NSColor.blackColor().set()
    path.stroke()
    
    img.unlockFocus()
    
    # Save to file
    data = img.TIFFRepresentation()
    image_rep = NSBitmapImageRep.imageRepWithData_(data)
    # Ensure transparency: property is not strictly needed if drawing is clean, but let's be safe
    png_data = image_rep.representationUsingType_properties_(NSPNGFileType, None)
    png_data.writeToFile_atomically_(filename, True)

# Ensure assets dir exists
os.makedirs("assets", exist_ok=True)

# Generate 4 frames of pulsing/zoom animation
# Cycle: Small -> Medium -> Large -> Medium
scales = [0.65, 0.82, 1.0, 0.82]

for i, s in enumerate(scales):
    create_hollow_circle(f"assets/icon_pro_{i+1}.png", scale=s)

print("✅ Generated 4 frames of THICK hollow circles with Pulsing/Zoom effect")
