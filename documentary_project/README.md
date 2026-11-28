# Muscle Growth — cinematic scientific documentary (172.37 s)

Fully procedural 3D documentary rendered offline with free tools only (Three.js in headless Chromium,
FFmpeg, Kokoro TTS, numpy). No source footage, frames, speakers, screenshots or stock are used.

## Important deviations from the brief (read first)
| Brief | What happened | Why |
|---|---|---|
| Transcribe the supplied reference MP4 | **No MP4 was ever supplied.** Narration text comes from the repo's existing script (`input/script_source.json`, from branch `claude/vibrant-davinci-29pppv`) and is **synthesised** with Kokoro TTS. It is *not* the original speaker's voice or wording. | User chose this option ("GO"). |
| faster-whisper / whisper.cpp word timing | Word timing is derived from the TTS: clause times are exact, words are phoneme-weighted splits snapped to energy minima (≥90 ms). | Model hosts (Hugging Face) are blocked in this environment. |
| Native 3840×2160 | Rendered natively at **1920×1080/30**. 4K files are **Lanczos-upscaled** and named `*_UPSCALED_*`. | Software (SwiftShader) GPU, ~4–5 s per frame. |
| Vertical 1080×1920 | Re-composed (own camera framing, vertical overlay layout) and rendered natively at **720×1280**, upscaled to 1080×1920 (`*_UPSCALED_*`). | Same render-time limit. |
| Statistics / studies | None are invented; all graphics carry "CONCEPTUAL VISUALIZATION · NOT TO SCALE", context notes stay qualitative. | Brief rule. |

## Layout
```
input/        script_source.json (narration text)
audio/        narration_raw/processed, music, sfx, final_mix (.flac committed, .wav regenerated), mix_report.json
transcript/   transcript.json (sections>clauses>words), transcript.srt, words.srt, cues.json
storyboard/   shots.json (49 shots: camera, focus, params, callouts, transitions), production.json, semantic_timeline.json
keyframes/    keyframe stills (jpg) + contact sheets
scenes/       engine.js (HDR pipeline, DOF, bloom, AgX grade, transitions), lib.js (materials/SDF/molecules),
              overlay.js (motion graphics), worlds/*.js (body, fibers, sarcomere, blood, molecules, cell, powder, synthesis, timeline)
materials/    see README (procedural, in code)
animations/   see README (camera/param system is data in shots.json)
scripts/      tts.py, storyboard.py, audio.py, subtitles.py, capture.js, assemble.py, qc.py, contact_sheet.py
subtitles/    landscape_1080p.ass, vertical_1080x1920.ass (word-synced karaoke), transcript.srt, words.srt
renders/      resumable 6 s segments (gitignored)
output/       final MP4s, render_quality_report.{json,md}, asset_licence_manifest.json
```

## Rebuild
```bash
npm install                                   # three@0.170.0
python3 scripts/tts.py                        # narration + word timing (needs kokoro.onnx/voices.bin)
python3 scripts/storyboard.py                 # shots.json / production.json
python3 scripts/audio.py                      # score, SFX, ducking, loudnorm -14 LUFS / -1.5 dBTP
python3 scripts/subtitles.py                  # ASS + SRT, verifies wording == transcript
node scripts/capture.js still h 12.5,40 --out keyframes   # any stills
node scripts/capture.js h                     # landscape, resumable (skips finished segments)
node scripts/capture.js v --size 720x1280 --out renders/v # vertical
python3 scripts/assemble.py h && python3 scripts/assemble.py v
python3 scripts/qc.py                         # output/render_quality_report.md
```

## Outputs
Masters (CRF 17–18, AAC 320k) are too large for git and are delivered separately; size-capped copies
(`*_1080p_clean.mp4`, `*_1080p_subtitled.mp4`, `*_vertical_*_subtitled.mp4`) are committed. See
`output/render_quality_report.md` for the verified specs, durations, decode checks and loudness.
