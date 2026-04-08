# agent-video-studio

Small multi-skill repo for short-form video production workflows.

## Skills

- `skills/mockup`: place videos inside phone mockups
- `skills/snapchat-overlay`: add Snapchat-style caption bars

Each skill is packaged with its own `SKILL.md` and `scripts/` folder so it can be installed from this repo as a Codex-compatible skill.

## Repo Layout

- `skills/`: installable skill folders
- `assets/`: local media inputs, ignored by git
- `outputs/`: rendered outputs, ignored by git

## Usage

Mockup:

```bash
python3 skills/mockup/scripts/mockup_video.py assets/mockup/empty_mockup.png assets/mockup/input.mp4
```

Snapchat overlay:

```bash
python3 skills/snapchat-overlay/scripts/overlay.py assets/snapchat-overlay/input.mp4 "Your hook text"
```
