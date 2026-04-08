---
name: mockup
description: Composite a video or screen recording into a phone mockup frame with ffmpeg. Use when Codex needs to place a video inside a device mockup, tune fit or crop, adjust screen detection, or render polished phone-mockup assets from a mockup PNG and input video.
---

# Mockup

Use `scripts/mockup_video.py` to render a video inside a phone frame.

## Workflow

1. Take a mockup PNG and an input video path from the user or workspace.
2. Render with the default `contain` fit first when the user wants the whole screen visible.
3. If the result feels slightly cropped, reduce `--scale` incrementally, usually `0.99`, `0.985`, or `0.97`.
4. Prefer `--screen-detection raw` for visually fuller framing.
5. Use `--screen-detection safe` only when the mockup mask clips the top or rounded edges.
6. Keep `--max-output-height 1920` unless the user explicitly wants the full mockup resolution.

## Command

```bash
python3 scripts/mockup_video.py <mockup.png> <input-video> [options]
```

## Fit Guidance

- Use `--fit-mode contain` for normal app demos and screen recordings.
- Use `--fit-mode cover` only when the user explicitly wants edge-to-edge fill and accepts cropping.
- Use `--screen-bg-color 000000` unless the mockup requires another in-screen letterbox color.

## Output Behavior

- Default output goes to `outputs/mockup/` when the skill is used inside the repo layout.
- When installed as a standalone skill, default output goes to `./outputs/mockup/` from the current working directory.

