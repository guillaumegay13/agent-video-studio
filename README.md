# agent-video-studio

Small multi-skill repo for short-form video production workflows.

## Skills

- `skills/mockup`: place videos inside phone mockups
- `skills/mobile-flow-recording`: record Android Emulator or iOS Simulator flows
- `skills/snapchat-overlay`: add Snapchat-style caption bars
- `skills/video-speed`: speed videos up or slow them down
- `skills/video-stitch`: join a hook and a main clip into one export

Each skill is packaged with its own `SKILL.md` and `scripts/` folder so it can be installed from this repo as a Codex-compatible skill.

## Repo Layout

- `skills/`: installable skill folders
- `assets/`: local raw media inputs, ignored by git
- `outputs/`: rendered outputs, ignored by git

## Usage

Mockup:

```bash
python3 skills/mockup/scripts/mockup_video.py skills/mockup/assets/empty_mockup.png assets/screen-recordings/input.mp4
```

Mobile flow recording:

```bash
python3 skills/mobile-flow-recording/scripts/record_mobile_flow.py android --serial emulator-5554 --duration 45
python3 skills/mobile-flow-recording/scripts/record_mobile_flow.py android --run flutter drive --target integration_test/app_test.dart
python3 skills/mobile-flow-recording/scripts/record_mobile_flow.py ios --run python3 run_agent_loop.py
```

Snapchat overlay:

```bash
python3 skills/snapchat-overlay/scripts/overlay.py assets/hooks/input.mp4 "Your hook text"
```

Video speed:

```bash
python3 skills/video-speed/scripts/video_speed.py assets/screen-recordings/input.mp4 1.5
```

Video stitch:

```bash
python3 skills/video-stitch/scripts/video_stitch.py assets/hooks/hook.mp4 outputs/mockup/mockup.mp4 --format mp4
```

## Raw Inputs

- put hook source videos in `assets/hooks/`
- put phone screen recordings in `assets/screen-recordings/`

The reusable phone mockup template is versioned inside `skills/mockup/assets/`. User-provided videos stay under the ignored root `assets/` folder, while generated files belong under `outputs/`.
