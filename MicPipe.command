#!/bin/bash
# Get the directory where this script is located
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$DIR"

echo "🚀 Starting MicPipe using uv..."

# Check if uv is installed
if ! command -v uv &> /dev/null
then
    echo "❌ 'uv' is not installed. Please install it first (e.g., 'brew install uv')."
    echo "Press any key to exit..."
    read -n 1
    exit 1
fi

# Run the application in the background
export PATH="$HOME/.local/bin:/usr/local/bin:/opt/homebrew/bin:$PATH"
nohup uv run python main.py > /tmp/micpipe.log 2>&1 &

echo "🚀 MicPipe is starting in the background..."
echo "📂 Logs are being written to /tmp/micpipe.log"

# Wait a moment and then close the Terminal window
sleep 1
osascript -e 'tell application "Terminal" to close front window' &
exit
