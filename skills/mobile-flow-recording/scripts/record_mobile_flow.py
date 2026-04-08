#!/usr/bin/env python3
"""Record iOS Simulator or Android Emulator flows to an mp4 file."""

import argparse
import math
import shutil
import signal
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path


ANDROID_MAX_DURATION = 180


def get_skill_root() -> Path:
    """Return the skill root by walking up to the directory with SKILL.md."""
    for parent in Path(__file__).resolve().parents:
        if (parent / "SKILL.md").exists():
            return parent
    sys.exit("Could not locate skill root (SKILL.md not found).")


def get_output_root(skill_name: str) -> Path:
    """Return the preferred output root for repo and installed-skill layouts."""
    skill_root = get_skill_root()
    repo_root = skill_root.parent.parent
    if skill_root.parent.name == "skills" and (repo_root / "skills").exists():
        return repo_root / "outputs" / skill_name
    return Path.cwd() / "outputs" / skill_name


def ensure_binary(name: str) -> None:
    """Exit with a clear message when a required binary is unavailable."""
    if shutil.which(name):
        return
    sys.exit(f"Required command not found in PATH: {name}")


def ensure_supported_backend(platform: str) -> None:
    """Fail fast when the selected backend cannot run on the current host."""
    if platform == "ios" and sys.platform != "darwin":
        sys.exit(
            "The `ios` backend requires macOS with Xcode and iOS Simulator. "
            "Use the `android` backend for Linux or VPS agents."
        )


def run_checked(cmd: list[str], error_message: str) -> None:
    """Run a command and exit with a task-specific message if it fails."""
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0:
        return

    details = result.stderr.strip() or result.stdout.strip()
    if details:
        sys.exit(f"{error_message}\n{details}")
    sys.exit(error_message)


def adb_base(serial: str | None) -> list[str]:
    """Build the base adb invocation with an optional serial selector."""
    cmd = ["adb"]
    if serial:
        cmd.extend(["-s", serial])
    return cmd


def list_adb_devices() -> list[str]:
    """Return connected adb devices that are ready for commands."""
    ensure_binary("adb")

    subprocess.run(
        ["adb", "start-server"],
        capture_output=True,
        text=True,
        check=False,
    )
    result = subprocess.run(
        ["adb", "devices"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        details = result.stderr.strip() or result.stdout.strip()
        if details:
            sys.exit(f"Could not list adb devices.\n{details}")
        sys.exit("Could not list adb devices.")

    devices: list[str] = []
    for line in result.stdout.splitlines():
        line = line.strip()
        if not line or line.startswith("List of devices attached"):
            continue
        if "\t" not in line:
            continue

        serial, status = line.split("\t", 1)
        if status == "device":
            devices.append(serial)

    return devices


def ensure_android_device_available(serial: str | None) -> None:
    """Validate that adb can reach the intended Android target."""
    devices = list_adb_devices()

    if serial:
        if serial in devices:
            return

        available = ", ".join(devices) if devices else "none"
        sys.exit(
            f"Requested Android serial `{serial}` is not available over adb. "
            f"Connected devices: {available}."
        )

    if not devices:
        sys.exit(
            "No Android emulator or device is available over adb. "
            "Start an emulator or connect a device before recording."
        )

    if len(devices) > 1:
        sys.exit(
            "More than one Android emulator/device is connected. "
            "Pass `--serial` to choose one: "
            + ", ".join(devices)
        )


def build_output_path(platform: str, explicit_output: str | None) -> Path:
    """Resolve the output path and create its parent directory."""
    if explicit_output:
        output_path = Path(explicit_output).expanduser()
        if not output_path.is_absolute():
            output_path = Path.cwd() / output_path
    else:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = get_output_root("mobile-flow-recording")
        output_path = output_dir / f"{platform}-flow_{timestamp}.mp4"

    output_path = output_path.resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    return output_path


def remote_android_path(local_output: Path) -> str:
    """Return a stable temporary path on the Android device."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"/sdcard/Download/{local_output.stem}_{timestamp}.mp4"


def start_ios_recording(device: str, output_path: Path, codec: str) -> subprocess.Popen[bytes]:
    """Start an iOS Simulator recording process."""
    ensure_binary("xcrun")

    cmd = [
        "xcrun",
        "simctl",
        "io",
        device,
        "recordVideo",
        f"--codec={codec}",
        str(output_path),
    ]
    print(f"Starting iOS recording: {' '.join(cmd)}")
    return subprocess.Popen(cmd)


def start_android_recording(
    serial: str | None,
    remote_path: str,
    bitrate: int,
    duration: float | None,
) -> subprocess.Popen[bytes]:
    """Start an Android recording process backed by adb screenrecord."""
    ensure_android_device_available(serial)

    adb_cmd = adb_base(serial)
    run_checked(
        adb_cmd + ["shell", "rm", "-f", remote_path],
        "Could not clear the previous Android recording path.",
    )

    cmd = adb_cmd + ["shell", "screenrecord"]
    if bitrate > 0:
        cmd.extend(["--bit-rate", str(bitrate)])

    effective_duration = ANDROID_MAX_DURATION if duration is None else duration
    if effective_duration <= 0:
        sys.exit("Duration must be greater than 0.")
    if effective_duration > ANDROID_MAX_DURATION:
        sys.exit(
            "Android screenrecord is limited to 180 seconds per recording. "
            "Use a shorter duration or split the flow into segments."
        )

    cmd.extend(["--time-limit", str(max(1, math.ceil(effective_duration)))])
    cmd.append(remote_path)

    print(f"Starting Android recording: {' '.join(cmd)}")
    return subprocess.Popen(cmd)


def stop_process(process: subprocess.Popen[bytes], label: str) -> int:
    """Try to stop a long-running process gracefully, then force if needed."""
    if process.poll() is not None:
        return process.returncode or 0

    try:
        process.send_signal(signal.SIGINT)
    except ProcessLookupError:
        return process.poll() or 0

    try:
        return process.wait(timeout=15)
    except subprocess.TimeoutExpired:
        print(f"{label} did not stop on SIGINT, sending terminate.")
        process.terminate()

    try:
        return process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        print(f"{label} still running, killing it.")
        process.kill()
        return process.wait(timeout=5)


def pull_android_recording(serial: str | None, remote_path: str, output_path: Path) -> None:
    """Pull the Android recording to the local output path and clean up."""
    adb_cmd = adb_base(serial)

    run_checked(
        adb_cmd + ["pull", remote_path, str(output_path)],
        "Could not pull the Android recording from the device.",
    )

    run_checked(
        adb_cmd + ["shell", "rm", "-f", remote_path],
        "The Android recording was pulled, but cleanup on the device failed.",
    )


def normalize_run_command(command: list[str] | None) -> list[str] | None:
    """Validate the optional wrapped command."""
    if command is None:
        return None
    if not command:
        sys.exit("`--run` was provided without a command.")
    return command


def monitor_until_command_exits(
    recording_process: subprocess.Popen[bytes],
    wrapped_process: subprocess.Popen[bytes],
) -> tuple[int, bool]:
    """Wait for the wrapped command and detect whether recording ended first."""
    recording_finished_early = False

    while True:
        wrapped_returncode = wrapped_process.poll()
        recording_returncode = recording_process.poll()

        if recording_returncode is not None and wrapped_returncode is None:
            recording_finished_early = True

        if wrapped_returncode is not None:
            return wrapped_returncode, recording_finished_early

        time.sleep(0.25)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Record iOS Simulator or Android Emulator flows to mp4.",
    )
    parser.add_argument(
        "platform",
        choices=["ios", "android"],
        help="Recording backend to use",
    )
    parser.add_argument(
        "-o",
        "--output",
        help="Output file (default: outputs/mobile-flow-recording/<platform>-flow_<timestamp>.mp4)",
    )
    parser.add_argument(
        "--duration",
        type=float,
        help="Recording length in seconds. On Android the limit is 180 seconds.",
    )
    parser.add_argument(
        "--pre-delay",
        type=float,
        default=1.0,
        help="Seconds to wait after recording starts before running the wrapped command (default: 1.0)",
    )
    parser.add_argument(
        "--post-delay",
        type=float,
        default=0.5,
        help="Seconds to wait after the wrapped command exits before stopping the recording (default: 0.5)",
    )
    parser.add_argument(
        "--run",
        nargs=argparse.REMAINDER,
        help="Command to run while recording. Put this option last.",
    )
    parser.add_argument(
        "--device",
        default="booted",
        help="iOS Simulator device selector or UDID (default: booted)",
    )
    parser.add_argument(
        "--ios-codec",
        default="h264",
        choices=["h264", "hevc"],
        help="Codec for xcrun simctl recordVideo (default: h264)",
    )
    parser.add_argument(
        "--serial",
        help="Android device serial to pass to adb -s",
    )
    parser.add_argument(
        "--android-bit-rate",
        type=int,
        default=8_000_000,
        help="Android screenrecord bitrate in bits per second (default: 8000000)",
    )

    args = parser.parse_args()
    ensure_supported_backend(args.platform)
    wrapped_command = normalize_run_command(args.run)
    output_path = build_output_path(args.platform, args.output)

    if args.duration is not None and args.duration <= 0:
        sys.exit("Duration must be greater than 0.")

    recording_process: subprocess.Popen[bytes] | None = None
    remote_path: str | None = None
    wrapped_returncode = 0
    recording_finished_early = False

    try:
        if args.platform == "ios":
            recording_process = start_ios_recording(
                device=args.device,
                output_path=output_path,
                codec=args.ios_codec,
            )
        else:
            remote_path = remote_android_path(output_path)
            recording_process = start_android_recording(
                serial=args.serial,
                remote_path=remote_path,
                bitrate=args.android_bit_rate,
                duration=args.duration,
            )

        if wrapped_command:
            if args.pre_delay > 0:
                time.sleep(args.pre_delay)

            print(f"Running wrapped command: {' '.join(wrapped_command)}")
            wrapped_process = subprocess.Popen(wrapped_command)
            wrapped_returncode, recording_finished_early = monitor_until_command_exits(
                recording_process=recording_process,
                wrapped_process=wrapped_process,
            )

            if args.post_delay > 0:
                time.sleep(args.post_delay)

        elif args.duration is not None:
            time.sleep(args.duration)
        else:
            if args.platform == "android":
                print("Recording until Ctrl+C or until Android reaches its 180 second limit.")
            else:
                print("Recording until Ctrl+C.")
            recording_process.wait()

    except KeyboardInterrupt:
        print("\nStopping recording.")
    finally:
        if recording_process is not None:
            record_returncode = stop_process(recording_process, "Recording process")
        else:
            record_returncode = 0

        if args.platform == "android" and remote_path is not None and recording_process is not None:
            pull_android_recording(args.serial, remote_path, output_path)

    if wrapped_returncode != 0:
        sys.exit(f"Wrapped command failed with exit code {wrapped_returncode}.")

    if record_returncode != 0:
        sys.exit(f"Recording command failed with exit code {record_returncode}.")

    if recording_finished_early and args.platform == "android":
        print(
            "Warning: Android recording stopped before the wrapped command completed. "
            "This usually means the 180 second screenrecord limit was reached."
        )

    print(f"Done! Output saved to: {output_path}")


if __name__ == "__main__":
    main()
