#!/bin/bash
# Get the directory where this script is located
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$DIR"

export PATH="$HOME/.local/bin:/usr/local/bin:/opt/homebrew/bin:$PATH"

if command -v uv &> /dev/null; then
    # uv handles venv creation and dependency installation automatically
    echo "🚀 Starting MicPipe using uv..."
    RUN_CMD="uv run python main.py"
else
    echo "⚙️  uv not found, using pip..."

    # Find a usable python3
    if command -v python3 &> /dev/null; then
        SYS_PYTHON="python3"
    else
        echo "❌ Python 3 not found. Please install Python 3.11 or higher."
        echo "Press any key to exit..."
        read -n 1
        exit 1
    fi

    # Create virtual environment if it doesn't exist
    if [ ! -f ".venv/bin/python" ]; then
        echo "📦 Creating virtual environment..."
        $SYS_PYTHON -m venv .venv
        if [ $? -ne 0 ]; then
            echo "❌ Failed to create virtual environment."
            echo "Press any key to exit..."
            read -n 1
            exit 1
        fi
    fi

    # Install dependencies if a key package (rumps) is missing
    if ! .venv/bin/python -c "import rumps" &> /dev/null; then
        echo "📦 Installing dependencies..."
        .venv/bin/pip install . --quiet
        if [ $? -ne 0 ]; then
            echo "❌ Failed to install dependencies."
            echo "Press any key to exit..."
            read -n 1
            exit 1
        fi
        echo "✅ Dependencies installed."
    fi

    RUN_CMD=".venv/bin/python main.py"
fi

# Run the application in the background
nohup $RUN_CMD > /tmp/micpipe.log 2>&1 &

echo "🚀 MicPipe is starting in the background..."
echo "📂 Logs are being written to /tmp/micpipe.log"

# Wait a moment and then close the Terminal window
sleep 1
osascript -e 'tell application "Terminal" to close front window' &
exit
