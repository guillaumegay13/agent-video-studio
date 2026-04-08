#!/usr/bin/env python3
"""Stitch two videos together into one export."""

import argparse
import json
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


def probe_media(path: str) -> dict:
    """Read stream and duration metadata with ffprobe."""
    result = subprocess.run(
        [
            "ffprobe", "-v", "quiet",
            "-print_format", "json",
            "-show_streams",
            "-show_format",
            path,
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        sys.exit(f"ffprobe failed: {result.stderr}")

    data = json.loads(result.stdout)
    streams = data.get("streams", [])
    video_stream = next((s for s in streams if s.get("codec_type") == "video"), None)
    audio_stream = next((s for s in streams if s.get("codec_type") == "audio"), None)
    if not video_stream:
        sys.exit(f"No video stream found in: {path}")

    duration = video_stream.get("duration") or data.get("format", {}).get("duration")
    if duration is None:
        sys.exit(f"Could not determine duration for: {path}")

    return {
        "has_audio": audio_stream is not None,
        "duration": float(duration),
        "width": int(video_stream["width"]),
        "height": int(video_stream["height"]),
    }


def has_encoder(name: str) -> bool:
    """Check whether the local ffmpeg build exposes an encoder."""
    result = subprocess.run(
        ["ffmpeg", "-hide_banner", "-encoders"],
        capture_output=True,
        text=True,
    )
    return result.returncode == 0 and name in result.stdout


def resolve_video_codec(container_format: str, codec: str) -> str:
    """Resolve the requested encoder to a concrete ffmpeg codec name."""
    if codec != "auto":
        return codec

    if container_format == "webm":
        return "libvpx-vp9"

    if sys.platform == "darwin" and has_encoder("h264_videotoolbox"):
        return "h264_videotoolbox"

    return "libx264"


def determine_output_format(output: Path | None, requested_format: str | None) -> str:
    """Resolve the final container format."""
    if requested_format:
        return requested_format

    if output and output.suffix.lower() in {".mp4", ".mov", ".webm"}:
        return output.suffix.lower().lstrip(".")

    return "mp4"


def normalize_output_path(
    first: Path,
    second: Path,
    output: str | None,
    container_format: str,
) -> Path:
    """Build the output path and ensure it uses the selected extension."""
    suffix = f".{container_format}"
    if output:
        output_path = Path(output)
        if output_path.suffix.lower() != suffix:
            output_path = output_path.with_suffix(suffix)
        return output_path

    output_dir = get_output_root("video-stitch")
    name = f"{first.stem}__{second.stem}_stitched{suffix}"
    return output_dir / name


def build_segment_video_filter(
    index: int,
    width: int,
    height: int,
    fps: int,
    fit_mode: str,
    bg_color: str,
) -> str:
    """Build the ffmpeg filter for one video segment."""
    if fit_mode == "contain":
        return (
            f"[{index}:v]scale={width}:{height}:force_original_aspect_ratio=decrease:flags=bicubic,"
            f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color=#{bg_color},"
            f"fps={fps},setsar=1,format=yuv420p[v{index}]"
        )

    if fit_mode == "cover":
        return (
            f"[{index}:v]scale={width}:{height}:force_original_aspect_ratio=increase:flags=bicubic,"
            f"crop={width}:{height},fps={fps},setsar=1,format=yuv420p[v{index}]"
        )

    sys.exit(f"Unsupported fit mode: {fit_mode}")


def build_segment_audio_filter(index: int, info: dict) -> str:
    """Build the ffmpeg filter for one audio segment."""
    if info["has_audio"]:
        return f"[{index}:a]aresample=48000,asetpts=N/SR/TB[a{index}]"

    duration = info["duration"]
    return (
        "anullsrc=channel_layout=stereo:sample_rate=48000,"
        f"atrim=duration={duration:.6f},asetpts=N/SR/TB[a{index}]"
    )


def run_stitch(
    first_path: str,
    second_path: str,
    output_path: str,
    container_format: str,
    width: int = 1080,
    height: int = 1920,
    fps: int = 30,
    fit_mode: str = "contain",
    bg_color: str = "000000",
    mute: bool = False,
    video_codec: str = "auto",
    crf: int = 18,
    preset: str = "fast",
    bitrate: str = "10M",
) -> None:
    """Render the stitched output."""
    first_info = probe_media(first_path)
    second_info = probe_media(second_path)
    resolved_codec = resolve_video_codec(container_format, video_codec)

    filter_parts = [
        build_segment_video_filter(0, width, height, fps, fit_mode, bg_color),
        build_segment_video_filter(1, width, height, fps, fit_mode, bg_color),
    ]

    if mute:
        filter_parts.append("[v0][v1]concat=n=2:v=1:a=0[v]")
    else:
        filter_parts.extend([
            build_segment_audio_filter(0, first_info),
            build_segment_audio_filter(1, second_info),
            "[v0][a0][v1][a1]concat=n=2:v=1:a=1[v][a]",
        ])

    cmd = [
        "ffmpeg", "-y",
        "-i", first_path,
        "-i", second_path,
        "-filter_complex", ";".join(filter_parts),
        "-map", "[v]",
    ]

    if not mute:
        cmd.extend(["-map", "[a]"])

    if container_format in {"mp4", "mov"}:
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
            sys.exit(f"Unsupported codec for {container_format}: {resolved_codec}")

        if not mute:
            cmd.extend(["-c:a", "aac", "-b:a", "192k"])

        cmd.extend(["-movflags", "+faststart"])
    elif container_format == "webm":
        if resolved_codec != "libvpx-vp9":
            sys.exit("webm output requires libvpx-vp9 or --video-codec auto")

        cmd.extend([
            "-c:v", "libvpx-vp9",
            "-b:v", "0",
            "-crf", str(crf),
            "-row-mt", "1",
        ])
        if not mute:
            cmd.extend(["-c:a", "libopus", "-b:a", "128k"])
    else:
        sys.exit(f"Unsupported output format: {container_format}")

    if mute:
        cmd.append("-an")

    cmd.append(output_path)

    print(f"Output format: {container_format}")
    print(f"Encoder: {resolved_codec}")
    print(f"Canvas: {width}x{height} @ {fps}fps")

    result = subprocess.run(cmd)
    if result.returncode != 0:
        sys.exit("FFmpeg failed.")
    print(f"\nDone! Output saved to: {output_path}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Stitch two videos together into one export.",
    )
    parser.add_argument("first", help="First video, e.g. the hook")
    parser.add_argument("second", help="Second video, e.g. the main mockup")
    parser.add_argument(
        "-o", "--output",
        help="Output file (default: outputs/video-stitch/<first>__<second>_stitched.<ext>)",
    )
    parser.add_argument(
        "--format", default=None,
        choices=["mp4", "mov", "webm"],
        help="Output container format (default: infer from output or use mp4)",
    )
    parser.add_argument(
        "--width", type=int, default=1080,
        help="Output width (default: 1080)",
    )
    parser.add_argument(
        "--height", type=int, default=1920,
        help="Output height (default: 1920)",
    )
    parser.add_argument(
        "--fps", type=int, default=30,
        help="Output frame rate (default: 30)",
    )
    parser.add_argument(
        "--fit-mode", default="contain",
        choices=["contain", "cover"],
        help="How to fit each clip inside the target canvas (default: contain)",
    )
    parser.add_argument(
        "--bg-color", default="000000",
        help="Background color used for padded areas (default: 000000)",
    )
    parser.add_argument(
        "--mute", action="store_true",
        help="Render the output without audio",
    )
    parser.add_argument(
        "--video-codec", default="auto",
        choices=["auto", "libx264", "h264_videotoolbox", "libvpx-vp9"],
        help="Video encoder to use (default: auto)",
    )
    parser.add_argument(
        "--crf", type=int, default=18,
        help="Quality value for libx264 or libvpx-vp9 (default: 18)",
    )
    parser.add_argument(
        "--preset", default="fast",
        choices=["ultrafast", "superfast", "veryfast", "faster", "fast",
                 "medium", "slow", "slower", "veryslow"],
        help="Encoding preset for libx264 (default: fast)",
    )
    parser.add_argument(
        "--bitrate", default="10M",
        help="Target bitrate for hardware H.264 encoding (default: 10M)",
    )
    args = parser.parse_args()

    first = Path(args.first)
    second = Path(args.second)

    if not first.exists():
        sys.exit(f"File not found: {first}")
    if not second.exists():
        sys.exit(f"File not found: {second}")
    if args.width <= 0 or args.height <= 0 or args.fps <= 0:
        sys.exit("Width, height, and fps must be greater than 0.")

    container_format = determine_output_format(
        Path(args.output) if args.output else None,
        args.format,
    )
    output_path = normalize_output_path(first, second, args.output, container_format)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    run_stitch(
        first_path=str(first),
        second_path=str(second),
        output_path=str(output_path),
        container_format=container_format,
        width=args.width,
        height=args.height,
        fps=args.fps,
        fit_mode=args.fit_mode,
        bg_color=args.bg_color,
        mute=args.mute,
        video_codec=args.video_codec,
        crf=args.crf,
        preset=args.preset,
        bitrate=args.bitrate,
    )


if __name__ == "__main__":
    main()
