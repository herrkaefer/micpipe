#!/bin/bash

# Voice Changer Script
# Usage: ./voice_change.sh input_file [pitch_value] [output_file]

INPUT="$1"
PITCH="${2:-0.85}"
OUTPUT="${3:-${INPUT%.*}_modified.mp4}"

if [ -z "$INPUT" ]; then
    echo "Usage: $0 input_video [pitch] [output_video]"
    exit 1
fi

FFMPEG_PATH=$(which ffmpeg)
if [ -z "$FFMPEG_PATH" ]; then
    FFMPEG_PATH="/usr/local/bin/ffmpeg"
fi

echo "Processing $INPUT with pitch $PITCH..."
$FFMPEG_PATH -i "$INPUT" \
    -filter:a "rubberband=pitch=$PITCH,aresample=44100" \
    -c:v libx264 -preset fast -crf 22 \
    -c:a aac -b:a 192k \
    -y "$OUTPUT"

echo "Done! Saved to $OUTPUT"
