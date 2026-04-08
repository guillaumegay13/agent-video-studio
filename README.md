# agent-video-studio

Small repo of content-production skills.

## Structure

- `skills/mockup`: puts videos into phone mockups
- `skills/snapchat-overlay`: adds Snapchat-style text overlays
- `assets/`: local media inputs, ignored by git
- `outputs/`: rendered outputs, ignored by git

## Usage

Mockup:

```bash
python3 skills/mockup/mockup_video.py assets/mockup/empty_mockup.png assets/mockup/input.mp4
```

Snapchat overlay:

```bash
python3 skills/snapchat-overlay/overlay.py assets/snapchat-overlay/input.mp4 "Your hook text"
```
