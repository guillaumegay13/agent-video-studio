# agent-video-studio

Small multi-skill repo for short-form video production workflows.

## Skills

- `skills/mockup`: place videos inside phone mockups
- `skills/snapchat-overlay`: add Snapchat-style caption bars
- `skills/video-speed`: speed videos up or slow them down
- `skills/video-stitch`: join a hook and a main clip into one export

Each skill is packaged with its own `SKILL.md` and `scripts/` folder so it can be installed from this repo as a Codex-compatible skill.

## Repo Layout

- `skills/`: installable skill folders
- `assets/`: local media inputs, ignored by git
- `outputs/`: rendered outputs, ignored by git

## Usage

Mockup:

```bash
python3 skills/mockup/scripts/mockup_video.py skills/mockup/assets/empty_mockup.png assets/mockup/input.mp4
```

Snapchat overlay:

```bash
python3 skills/snapchat-overlay/scripts/overlay.py assets/snapchat-overlay/input.mp4 "Your hook text"
```

Video speed:

```bash
python3 skills/video-speed/scripts/video_speed.py assets/mockup/input.mp4 1.5
```

Video stitch:

```bash
python3 skills/video-stitch/scripts/video_stitch.py assets/snapchat-overlay/hook.mp4 outputs/mockup/mockup.mp4 --format mp4
```

The reusable phone mockup template is versioned inside `skills/mockup/assets/`. User-provided videos stay under the ignored root `assets/` folder.
