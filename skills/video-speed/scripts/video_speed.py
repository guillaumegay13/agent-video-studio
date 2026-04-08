#!/usr/bin/env python3
"""Change video playback speed while keeping audio in sync."""

import argparse
import subprocess
import sys
from pathlib import Path


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


def has_encoder(name: str) -> bool:
    """Check whether the local ffmpeg build exposes an encoder."""
    result = subprocess.run(
        ["ffmpeg", "-hide_banner", "-encoders"],
        capture_output=True,
        text=True,
    )
    return result.returncode == 0 and name in result.stdout


def resolve_video_codec(codec: str) -> str:
    """Resolve the requested encoder to a concrete ffmpeg codec name."""
    if codec != "auto":
        return codec

    if sys.platform == "darwin" and has_encoder("h264_videotoolbox"):
        return "h264_videotoolbox"

    return "libx264"


def build_atempo_chain(speed: float) -> str:
    """Build an atempo filter chain for the requested speed factor."""
    factors: list[float] = []
    remaining = speed

    while remaining > 2.0:
        factors.append(2.0)
        remaining /= 2.0

    while remaining < 0.5:
        factors.append(0.5)
        remaining /= 0.5

    factors.append(remaining)
    return ",".join(f"atempo={factor:.8f}".rstrip("0").rstrip(".") for factor in factors)


def run_speed_change(
    input_path: str,
    output_path: str,
    speed: float,
    mute: bool = False,
    video_codec: str = "auto",
    crf: int = 18,
    preset: str = "fast",
    bitrate: str = "10M",
) -> None:
    """Render a speed-adjusted video."""
    resolved_codec = resolve_video_codec(video_codec)
    video_filter = f"setpts=PTS/{speed:.8f}"

    cmd = [
        "ffmpeg", "-y",
        "-i", input_path,
        "-filter:v", video_filter,
        "-movflags", "+faststart",
    ]

    if not mute:
        cmd.extend(["-filter:a", build_atempo_chain(speed)])
    else:
        cmd.append("-an")

    if resolved_codec == "libx264":
        cmd.extend([
            "-c:v", "libx264",
            "-crf", str(crf),
            "-preset", preset,
        ])
    elif resolved_codec == "h264_videotoolbox":
        cmd.extend([
            "-c:v", "h264_videotoolbox",
            "-b:v", bitrate,
            "-realtime", "1",
            "-prio_speed", "1",
        ])
    else:
        sys.exit(f"Unsupported video codec: {resolved_codec}")

    if not mute:
        cmd.extend(["-c:a", "aac", "-b:a", "192k"])

    cmd.append(output_path)

    print(f"Encoder: {resolved_codec}")
    print(f"Speed: {speed}x")
    result = subprocess.run(cmd)
    if result.returncode != 0:
        sys.exit("FFmpeg failed.")
    print(f"\nDone! Output saved to: {output_path}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Change a video's playback speed.",
    )
    parser.add_argument("input", help="Input video file")
    parser.add_argument("speed", type=float, help="Playback speed factor, e.g. 1.5 or 2")
    parser.add_argument(
        "-o", "--output",
        help="Output file (default: outputs/video-speed/<name>_x<speed>.<ext>)",
    )
    parser.add_argument(
        "--mute", action="store_true",
        help="Render the output without audio",
    )
    parser.add_argument(
        "--video-codec", default="auto",
        choices=["auto", "libx264", "h264_videotoolbox"],
        help="Video encoder to use (default: auto)",
    )
    parser.add_argument(
        "--crf", type=int, default=18,
        help="CRF quality for libx264 (default: 18)",
    )
    parser.add_argument(
        "--preset", default="fast",
        choices=["ultrafast", "superfast", "veryfast", "faster", "fast",
                 "medium", "slow", "slower", "veryslow"],
        help="Encoding preset for libx264 (default: fast)",
    )
    parser.add_argument(
        "--bitrate", default="10M",
        help="Target bitrate for hardware encoding modes (default: 10M)",
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        sys.exit(f"File not found: {input_path}")

    if args.speed <= 0:
        sys.exit("Speed must be greater than 0.")

    if args.output:
        output_path = Path(args.output)
    else:
        speed_label = str(args.speed).replace(".", "_")
        output_dir = get_output_root("video-speed")
        output_path = output_dir / f"{input_path.stem}_x{speed_label}{input_path.suffix}"

    output_path.parent.mkdir(parents=True, exist_ok=True)

    run_speed_change(
        input_path=str(input_path),
        output_path=str(output_path),
        speed=args.speed,
        mute=args.mute,
        video_codec=args.video_codec,
        crf=args.crf,
        preset=args.preset,
        bitrate=args.bitrate,
    )


if __name__ == "__main__":
    main()
