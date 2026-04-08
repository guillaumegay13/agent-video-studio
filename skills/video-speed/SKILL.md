---
name: video-speed
description: Change a video's playback speed with ffmpeg while keeping audio in sync. Use when Codex needs to make a video faster or slower, produce 1.25x, 1.5x, 2x, or custom speed variants, preserve or mute audio, or export a sped-up social-media clip.
---

# Video Speed

Use `scripts/video_speed.py` to change playback speed for a local video file.

## Workflow

1. Take the input video path and requested speed from the user.
2. Use a factor above `1.0` to speed up the video and a factor below `1.0` to slow it down.
3. Keep audio by default so the result stays in sync with the new playback rate.
4. Use `--mute` only when the user wants silent output.
5. Keep the default output location unless the user explicitly asks for a custom file path.

## Command

```bash
python3 scripts/video_speed.py <input-video> <speed> [options]
```

Examples:

```bash
python3 scripts/video_speed.py /path/to/input.mp4 1.5
python3 scripts/video_speed.py /path/to/input.mp4 2
python3 scripts/video_speed.py /path/to/input.mp4 0.75 --mute
```

## Output Behavior

- Default output goes to `outputs/video-speed/` when the skill is used inside the repo layout.
- When installed as a standalone skill, default output goes to `./outputs/video-speed/` from the current working directory.

## Rendering Guidance

- Use the default codec auto-selection unless the user explicitly asks for software x264.
- Preserve audio when possible.
- Use `--crf` only for `libx264`; use `--bitrate` for hardware encoding modes.
