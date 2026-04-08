---
name: video-stitch
description: Stitch two videos together into one timeline export with ffmpeg. Use when Codex needs to place a hook before a main clip, combine an intro and a mockup video, normalize both clips to a 9:16 canvas, preserve or synthesize audio continuity, or export the final result as mp4, mov, or webm.
---

# Video Stitch

Use `scripts/video_stitch.py` to concatenate two videos into a single output.

## Workflow

1. Take the first and second video paths from the user.
2. Keep the default `1080x1920` export when producing short-form vertical videos.
3. Use `--fit-mode contain` unless the user explicitly wants edge-to-edge cropping.
4. Select the output container with `--format mp4`, `--format mov`, or `--format webm`.
5. Keep audio by default; the script generates silence for clips that have no audio so the final export still works.

## Command

```bash
python3 scripts/video_stitch.py <first-video> <second-video> [options]
```

Examples:

```bash
python3 scripts/video_stitch.py /path/to/hook.mp4 /path/to/mockup.mp4
python3 scripts/video_stitch.py /path/to/hook.mp4 /path/to/mockup.mp4 --format mov
python3 scripts/video_stitch.py /path/to/hook.mp4 /path/to/mockup.mp4 --format webm --fit-mode cover
```

## Output Behavior

- Default output goes to `outputs/video-stitch/` when the skill is used inside the repo layout.
- When installed as a standalone skill, default output goes to `./outputs/video-stitch/` from the current working directory.

## Rendering Guidance

- Use `mp4` for the default social workflow unless the user asks for another container.
- Use `mov` when the user wants an H.264 QuickTime-style export.
- Use `webm` only when the destination explicitly needs it.
- Keep `1080x1920` and `30 fps` as the default short-form export target.
