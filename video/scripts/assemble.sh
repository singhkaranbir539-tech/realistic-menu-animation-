#!/usr/bin/env bash
# Concatenate the 10 scene renders, mux the mixed soundtrack, export deliverables.
set -euo pipefail
cd "$(dirname "$0")/.."
ls output/scenes/scene_*.mp4 | sort | sed "s|^|file '$PWD/|; s|$|'|" > build/concat.txt
ffmpeg -y -loglevel error -f concat -safe 0 -i build/concat.txt -i build/mix.wav \
  -map 0:v -map 1:a -c:v copy -c:a aac -b:a 256k -ar 48000 -shortest -movflags +faststart \
  output/THE_SCIENCE_OF_EXTREME_MUSCLE_GROWTH_4K.mp4
# lighter 1080x1920 copy for phones / sharing
ffmpeg -y -loglevel error -i output/THE_SCIENCE_OF_EXTREME_MUSCLE_GROWTH_4K.mp4 \
  -vf scale=1080:1920:flags=lanczos -c:v libx264 -preset slow -crf 21 -pix_fmt yuv420p \
  -c:a copy -movflags +faststart output/THE_SCIENCE_OF_EXTREME_MUSCLE_GROWTH_1080p.mp4
ffprobe -v error -show_entries format=duration,size:stream=codec_name,width,height,r_frame_rate -of compact output/THE_SCIENCE_OF_EXTREME_MUSCLE_GROWTH_4K.mp4
