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

# Run the application using uv
# This handles the environment and dependencies automatically
uv run python main.py
