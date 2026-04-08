---
name: mobile-flow-recording
description: Record Android Emulator or iOS Simulator flows to mp4, optionally while an automation command runs. Default to Android for Linux, CI, and VPS agents via adb screenrecord. Use when Codex needs to capture a simulator session, wrap an AI agent loop or test run with start/stop recording, or export a reusable screen recording asset.
---

# Mobile Flow Recording

Use `scripts/record_mobile_flow.py` to record a phone simulator or emulator session into an `.mp4`.

This skill is for raw device capture, especially when the recording should start before an automation loop and stop when that loop exits.

## Platform Choice

- Default to `android` for Linux, CI, and VPS agents.
- Use `android` when the flow runs in Android Emulator or a connected Android device over `adb`.
- Use `ios` only when the flow must run in iOS Simulator on macOS with Xcode installed.

## Workflow

1. Pick `android` unless the user explicitly needs iOS.
2. Use a direct recording when the user only needs manual capture.
3. Use `--run ...` when the recording should wrap an automation command.
4. Keep the default output location unless the user asks for a specific path.
5. For Android, remember that `screenrecord` is capped at 180 seconds per invocation.

## Command

```bash
python3 scripts/record_mobile_flow.py <ios|android> [options]
```

Examples:

```bash
python3 scripts/record_mobile_flow.py android --serial emulator-5554 --duration 45
python3 scripts/record_mobile_flow.py android --run flutter drive --target integration_test/app_test.dart
python3 scripts/record_mobile_flow.py ios --run python3 run_agent_loop.py
```

## Output Behavior

- Default output goes to `outputs/mobile-flow-recording/` when the skill is used inside the repo layout.
- When installed as a standalone skill, default output goes to `./outputs/mobile-flow-recording/` from the current working directory.

## Recording Guidance

- Use `--run` for end-to-end flows so the recording automatically starts before the command and stops after it exits.
- Use `--pre-delay` when the simulator needs a moment to settle before the automation starts.
- For Android, pass `--serial` when more than one emulator or device is connected.
- For Android on Linux, make sure `adb devices` shows a connected emulator before invoking the skill.
- If the user needs a longer Android capture than 180 seconds, split the flow into segments.
- For iOS, leave the default `booted` target unless the user explicitly names a simulator UDID.

## Linux / VPS Guidance

- This skill is intended to run on Linux VPS agents through the `android` backend.
- The host only needs `adb` access to the emulator or device. No macOS-specific tooling is required.
- `adb shell screenrecord` records on-device, so the host does not need a desktop session just to capture video.
- The skill does not hardcode Safari, Settings, or any demo flow. It records whatever UI your wrapped command drives.
