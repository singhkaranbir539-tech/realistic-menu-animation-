# The Science of Extreme Muscle Growth

A 172-second vertical (9:16, 2160×3840, 30 fps) animated science documentary. It has no human presenter. The narrator is **NEURO**, a floating 3D-style brain who stays in the top-right corner, with lip sync driven by the narration audio.

Everything is generated procedurally from code. No stock footage, AI video or paid services are used.

| Layer | How it is made |
|---|---|
| Narration | [Kokoro](https://github.com/thewh1teagle/kokoro-onnx) TTS, a deep male voice blend (`am_michael` + `am_onyx`), synthesised clause by clause so every subtitle and visual cue is timed exactly |
| Visuals | `renderer/render.html` draws each frame on an HTML canvas (muscle-fibre bundles, molecules, bloodstream fly-through, sarcomeres, athlete, HUD), and headless Chromium captures it |
| Lip sync | Per-frame RMS envelope of the narration drives NEURO's mouth; blinks, brows, gaze and floating are procedural |
| Music & SFX | `scripts/audio.py` synthesises a cinematic electronic score plus impacts, neural zaps, whooshes, HUD blips, timer ticks and stretch textures; music ducks under speech |
| Subtitles | Burned in (bold white, orange keywords) and exported as `output/subtitles.srt` |

## Deliverables (`output/`)
- `THE_SCIENCE_OF_EXTREME_MUSCLE_GROWTH_4K.mp4`: final H.264 + AAC, 2160×3840 (not committed because of its size; rebuild it with the steps below)
- `THE_SCIENCE_OF_EXTREME_MUSCLE_GROWTH_1080p.mp4`: lighter 1080×1920 copy
- `scenes/scene_01.mp4 … scene_10.mp4`: individual 4K scene renders (not committed)
- `narration.wav`: narration only
- `subtitles.srt`: subtitle file

## Rebuild
```bash
pip install kokoro-onnx soundfile scipy        # plus the model files, see scripts/tts.py
python3 scripts/tts.py                          # narration, timings, lip-sync envelope, SRT
python3 scripts/audio.py                        # music + SFX + final mix
node renderer/capture.js 1,2,3,4,5,6,7,8,9,10 2 # render scenes at 2x (4K)
scripts/assemble.sh                             # concat + mux + 1080p copy
node renderer/capture.js preview 12,58,140 1    # quick still previews into build/
```

`scenes.json` holds the scene timing, titles, narration and highlighted keywords.
