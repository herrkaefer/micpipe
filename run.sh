#!/bin/bash
# MicPipe Startup Script

echo "======================================"
echo "    MicPipe - Dual Hotkey Version"
echo "======================================"
echo ""
echo "Starting application..."
echo ""
echo "Hotkey Info:"
echo "  🎯 Hold Fn Key → Hold to Speak"
echo "  🔄 Right Cmd Key → Toggle to Start/End"
echo ""
echo "Both hotkeys can be used interchangeably!"
echo "Press Ctrl+C to exit"
echo ""

# Check for virtual environment
if [ -d ".venv" ]; then
    echo "Starting with virtual environment..."
    uv run python main.py
else
    echo "Starting with system Python..."
    python main.py
fi

