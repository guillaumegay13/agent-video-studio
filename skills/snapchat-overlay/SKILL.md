---
name: snapchat-overlay
description: Add Snapchat-style caption bars to videos with centered emoji-safe text and ffmpeg compositing. Use when Codex needs to create short-form video hooks, overlay bold social captions, tune placement at the top, center, or bottom, or render captioned variants for social media videos.
---

# Snapchat Overlay

Use `scripts/overlay.py` to add a Snapchat-style caption bar on top of a video.

## Workflow

1. Take an input video and caption text from the user or workspace.
2. Render with the default centered placement first unless the user asks for a top or bottom hook.
3. Keep captions short enough to read quickly on mobile.
4. Adjust `--font-size`, `--bg-opacity`, and `--y-position` only when the default render does not match the intended look.

## Command

```bash
python3 scripts/overlay.py <input-video> "<caption text>" [options]
```

## Output Behavior

- Default output goes to `outputs/snapchat-overlay/` when the skill is used inside the repo layout.
- When installed as a standalone skill, default output goes to `./outputs/snapchat-overlay/` from the current working directory.

## Rendering Guidance

- Prefer white text on the default dark translucent bar unless the user requests another style.
- Preserve the source audio with `-c:a copy`.
- Use a lower CRF only when the user explicitly asks for a higher quality export.

