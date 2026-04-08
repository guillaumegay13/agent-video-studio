#!/usr/bin/env python3
"""Composite a phone screen recording into a device mockup frame.

Takes an empty phone mockup image (with a dark/black screen) and a screen
recording video, and produces a video of the recording playing inside the
phone frame. The screen area is auto-detected from dark pixels in the mockup.
"""

import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image

MOCKUP_CACHE_VERSION = "v3"


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


def get_video_info(path: str) -> dict:
    """Get video dimensions via ffprobe."""
    cmd = [
        "ffprobe", "-v", "quiet", "-print_format", "json",
        "-show_streams", path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        sys.exit(f"ffprobe failed: {result.stderr}")

    data = json.loads(result.stdout)
    video = next(
        (s for s in data["streams"] if s["codec_type"] == "video"), None
    )
    if not video:
        sys.exit("No video stream found.")

    return {
        "width": int(video["width"]),
        "height": int(video["height"]),
    }


def detect_screen_region(mockup_path: str, threshold: int = 30) -> dict:
    """Detect the screen area in the mockup by finding dark pixels.

    Returns a dict with top/left/width/height of the screen bounding box.
    """
    img = Image.open(mockup_path).convert("RGB")
    arr = np.array(img)

    dark = (arr[:, :, 0] < threshold) & \
           (arr[:, :, 1] < threshold) & \
           (arr[:, :, 2] < threshold)

    rows = np.any(dark, axis=1)
    cols = np.any(dark, axis=0)

    if not rows.any() or not cols.any():
        sys.exit("Could not detect a screen area in the mockup (no dark region found).")

    top, bottom = np.where(rows)[0][[0, -1]]
    left, right = np.where(cols)[0][[0, -1]]

    return {
        "top": int(top),
        "left": int(left),
        "width": int(right - left + 1),
        "height": int(bottom - top + 1),
    }


def detect_raw_screen_region_from_dark_mask(dark: np.ndarray) -> dict:
    """Return the full bounding box of dark pixels."""
    rows = np.any(dark, axis=1)
    cols = np.any(dark, axis=0)

    if not rows.any() or not cols.any():
        sys.exit("Could not detect a screen area in the mockup (no dark region found).")

    top, bottom = np.where(rows)[0][[0, -1]]
    left, right = np.where(cols)[0][[0, -1]]

    return {
        "top": int(top),
        "left": int(left),
        "width": int(right - left + 1),
        "height": int(bottom - top + 1),
    }


def detect_safe_screen_region_from_dark_mask(dark: np.ndarray, coverage_ratio: float = 0.98) -> dict:
    """Detect a conservative inner screen rectangle from a dark-pixel mask.

    The raw dark bounding box often includes rounded corners or small cutouts.
    This trims the box to rows and columns that are dark across most of the
    screen, which better matches the usable display area.
    """
    rows = np.any(dark, axis=1)
    cols = np.any(dark, axis=0)

    if not rows.any() or not cols.any():
        sys.exit("Could not detect a screen area in the mockup (no dark region found).")

    top, bottom = np.where(rows)[0][[0, -1]]
    left, right = np.where(cols)[0][[0, -1]]
    mask = dark[top:bottom + 1, left:right + 1]

    row_counts = mask.sum(axis=1)
    col_counts = mask.sum(axis=0)
    max_row = int(row_counts.max())
    max_col = int(col_counts.max())

    safe_rows = np.where(row_counts >= max_row * coverage_ratio)[0]
    safe_cols = np.where(col_counts >= max_col * coverage_ratio)[0]

    if safe_rows.size == 0 or safe_cols.size == 0:
        safe_top, safe_bottom = top, bottom
        safe_left, safe_right = left, right
    else:
        safe_top = top + int(safe_rows[0])
        safe_bottom = top + int(safe_rows[-1])
        safe_left = left + int(safe_cols[0])
        safe_right = left + int(safe_cols[-1])

    return {
        "top": int(safe_top),
        "left": int(safe_left),
        "width": int(safe_right - safe_left + 1),
        "height": int(safe_bottom - safe_top + 1),
    }


def get_cached_mockup_assets(
    mockup_path: str,
    threshold: int = 30,
    screen_detection: str = "raw",
) -> dict:
    """Return cached screen metadata and frame overlay for a mockup.

    The cache key includes the mockup path, threshold, file size, and mtime,
    so the assets are automatically rebuilt when the mockup changes.
    """
    mockup = Path(mockup_path).resolve()
    stat = mockup.stat()
    cache_key = hashlib.sha1(
        f"{MOCKUP_CACHE_VERSION}:{mockup}:{threshold}:{screen_detection}:{stat.st_size}:{stat.st_mtime_ns}".encode("utf-8")
    ).hexdigest()
    cache_dir = Path(tempfile.gettempdir()) / "video_studio_mockup_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)

    frame_path = cache_dir / f"{cache_key}.png"
    meta_path = cache_dir / f"{cache_key}.json"

    if frame_path.exists() and meta_path.exists():
        return {
            **json.loads(meta_path.read_text()),
            "frame_path": str(frame_path),
            "cache_hit": True,
        }

    img = Image.open(mockup).convert("RGBA")
    arr = np.array(img)
    dark = (arr[:, :, 0] < threshold) & \
           (arr[:, :, 1] < threshold) & \
           (arr[:, :, 2] < threshold)

    rows = np.any(dark, axis=1)
    cols = np.any(dark, axis=0)

    if not rows.any() or not cols.any():
        sys.exit("Could not detect a screen area in the mockup (no dark region found).")

    if screen_detection == "safe":
        screen = detect_safe_screen_region_from_dark_mask(dark)
    elif screen_detection == "raw":
        screen = detect_raw_screen_region_from_dark_mask(dark)
    else:
        sys.exit(f"Unsupported screen detection mode: {screen_detection}")

    arr[dark, 3] = 0

    result = Image.fromarray(arr)
    result.save(frame_path)

    meta = {
        "mockup_width": int(img.width),
        "mockup_height": int(img.height),
        "screen": screen,
    }
    meta_path.write_text(json.dumps(meta))

    return {
        **meta,
        "frame_path": str(frame_path),
        "cache_hit": False,
    }


def get_scaled_mockup_assets(assets: dict, output_scale: float) -> dict:
    """Return mockup metadata resized for the requested output scale."""
    if output_scale == 1.0:
        return assets

    mockup_w = max(2, int(round(assets["mockup_width"] * output_scale)))
    mockup_h = max(2, int(round(assets["mockup_height"] * output_scale)))
    mockup_w += mockup_w % 2
    mockup_h += mockup_h % 2

    scaled_screen = {
        "top": int(round(assets["screen"]["top"] * output_scale)),
        "left": int(round(assets["screen"]["left"] * output_scale)),
        "width": max(2, int(round(assets["screen"]["width"] * output_scale))),
        "height": max(2, int(round(assets["screen"]["height"] * output_scale))),
    }

    scale_key = hashlib.sha1(
        f"{assets['frame_path']}:{mockup_w}:{mockup_h}".encode("utf-8")
    ).hexdigest()
    scaled_frame_path = Path(tempfile.gettempdir()) / "video_studio_mockup_cache" / f"{scale_key}.png"

    cache_hit = scaled_frame_path.exists()
    if not cache_hit:
        frame = Image.open(assets["frame_path"]).convert("RGBA")
        resized = frame.resize((mockup_w, mockup_h), Image.LANCZOS)
        resized.save(scaled_frame_path)

    return {
        "mockup_width": mockup_w,
        "mockup_height": mockup_h,
        "screen": scaled_screen,
        "frame_path": str(scaled_frame_path),
        "cache_hit": cache_hit,
    }


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


def run_composite(
    mockup_path: str,
    video_path: str,
    output_path: str,
    bg_color: str = "EAECEE",
    screen_bg_color: str = "000000",
    threshold: int = 30,
    crf: int = 17,
    preset: str = "fast",
    scale: float | None = None,
    fit_mode: str = "contain",
    screen_detection: str = "raw",
    video_codec: str = "auto",
    bitrate: str = "12M",
    scale_filter: str = "bicubic",
    max_output_height: int = 1920,
) -> None:
    """Composite the screen recording into the phone mockup.

    Steps:
    1. Detect and cache the screen region and frame overlay
    2. Scale the video to cover the screen area
    3. Pad the video into the mockup canvas and overlay the phone frame on top
    """
    base_assets = get_cached_mockup_assets(
        mockup_path,
        threshold,
        screen_detection=screen_detection,
    )
    output_scale = 1.0
    if max_output_height > 0 and base_assets["mockup_height"] > max_output_height:
        output_scale = max_output_height / base_assets["mockup_height"]

    assets = get_scaled_mockup_assets(base_assets, output_scale)
    mockup_w = assets["mockup_width"]
    mockup_h = assets["mockup_height"]
    screen = assets["screen"]
    print(f"Mockup size: {mockup_w}x{mockup_h}")
    print(f"Screen region: {screen['width']}x{screen['height']} at ({screen['left']}, {screen['top']})")
    print(f"Output scale: {output_scale:.3f}x")

    video_info = get_video_info(video_path)
    print(f"Video size: {video_info['width']}x{video_info['height']}")

    frame_path = assets["frame_path"]
    print(f"Frame overlay: {frame_path}")
    print(f"Overlay cache: {'hit' if assets['cache_hit'] else 'miss'}")

    # Render into the detected screen area, optionally shrinking/enlarging the
    # usable box while preserving the video aspect ratio.
    screen_w = screen["width"]
    screen_h = screen["height"]
    fit_scale = scale if scale is not None else 1.0
    screen_box_w = max(2, int(round(screen_w * fit_scale)))
    screen_box_h = max(2, int(round(screen_h * fit_scale)))
    screen_box_w += screen_box_w % 2
    screen_box_h += screen_box_h % 2

    # Position: center the rendered screen box inside the detected screen area
    screen_box_x = screen["left"] + (screen_w - screen_box_w) // 2
    screen_box_y = screen["top"] + (screen_h - screen_box_h) // 2

    # Output dimensions must be even
    out_w = mockup_w + (mockup_w % 2)
    out_h = mockup_h + (mockup_h % 2)

    resolved_codec = resolve_video_codec(video_codec)

    # FFmpeg filter chain:
    if fit_mode == "contain":
        screen_filter = (
            f"[0:v]scale={screen_box_w}:{screen_box_h}:"
            f"force_original_aspect_ratio=decrease:flags={scale_filter},"
            f"pad={screen_box_w}:{screen_box_h}:(ow-iw)/2:(oh-ih)/2:"
            f"color=#{screen_bg_color}[screen];"
        )
    elif fit_mode == "cover":
        screen_filter = (
            f"[0:v]scale={screen_box_w}:{screen_box_h}:"
            f"force_original_aspect_ratio=increase:flags={scale_filter},"
            f"crop={screen_box_w}:{screen_box_h}[screen];"
        )
    else:
        sys.exit(f"Unsupported fit mode: {fit_mode}")

    # FFmpeg filter chain:
    # 1. Fit the video into the effective screen box
    # 2. Pad the screen box into the mockup canvas using the mockup background
    # 3. Overlay the phone frame (RGBA with transparent screen) on top
    filter_complex = (
        screen_filter +
        f"[screen]pad={out_w}:{out_h}:{screen_box_x}:{screen_box_y}:"
        f"color=#{bg_color}[canvas];"
        f"[canvas][1:v]overlay=0:0:shortest=1[out]"
    )

    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-loop", "1", "-i", frame_path,
        "-filter_complex", filter_complex,
        "-map", "[out]",
        "-map", "0:a?",
        "-fps_mode:v", "passthrough",
        "-c:a", "copy",
        "-movflags", "+faststart",
    ]

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

    cmd.append(output_path)

    print(f"Encoder: {resolved_codec}")
    print(f"\nRendering...")
    result = subprocess.run(cmd)

    if result.returncode != 0:
        sys.exit("FFmpeg failed.")
    print(f"\nDone! Output saved to: {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Composite a phone screen recording into a device mockup.",
    )
    parser.add_argument("mockup", help="Path to the empty device mockup PNG")
    parser.add_argument("video", help="Path to the screen recording video")
    parser.add_argument(
        "-o", "--output",
        help="Output file (default: <video>_mockup.mp4)",
    )
    parser.add_argument(
        "--bg-color", default="EAECEE",
        help="Background color hex (default: EAECEE, matching typical mockup bg)",
    )
    parser.add_argument(
        "--screen-bg-color", default="000000",
        help="Background color used inside the phone screen when preserving aspect ratio (default: 000000)",
    )
    parser.add_argument(
        "--threshold", type=int, default=30,
        help="Dark pixel threshold for screen detection 0-255 (default: 30)",
    )
    parser.add_argument(
        "--crf", type=int, default=17,
        help="CRF quality for libx264 (lower=better, default: 17)",
    )
    parser.add_argument(
        "--preset", default="fast",
        choices=["ultrafast", "superfast", "veryfast", "faster", "fast",
                 "medium", "slow", "slower", "veryslow"],
        help="Encoding preset for libx264 (default: fast)",
    )
    parser.add_argument(
        "--scale", type=float, default=None,
        help="Scale the effective screen box before fitting the video (default: 1.0)",
    )
    parser.add_argument(
        "--fit-mode", default="contain",
        choices=["contain", "cover"],
        help="How to fit the video inside the phone screen (default: contain)",
    )
    parser.add_argument(
        "--screen-detection", default="raw",
        choices=["raw", "safe"],
        help="How to detect the phone screen area in the mockup (default: raw)",
    )
    parser.add_argument(
        "--video-codec", default="auto",
        choices=["auto", "libx264", "h264_videotoolbox"],
        help="Video encoder to use (default: auto)",
    )
    parser.add_argument(
        "--bitrate", default="12M",
        help="Target bitrate for hardware encoding modes (default: 12M)",
    )
    parser.add_argument(
        "--scale-filter", default="bicubic",
        choices=["fast_bilinear", "bilinear", "bicubic", "lanczos"],
        help="Scaling algorithm used by ffmpeg (default: bicubic)",
    )
    parser.add_argument(
        "--max-output-height", type=int, default=1920,
        help="Cap output height to avoid unnecessary upscaling (default: 1920, use 0 for full mockup resolution)",
    )

    args = parser.parse_args()

    mockup = Path(args.mockup)
    video = Path(args.video)

    if not mockup.exists():
        sys.exit(f"Mockup not found: {mockup}")
    if not video.exists():
        sys.exit(f"Video not found: {video}")

    if args.output:
        output = Path(args.output)
    else:
        output_dir = get_output_root("mockup")
        output = output_dir / f"{video.stem}_mockup.mp4"

    output.parent.mkdir(parents=True, exist_ok=True)

    run_composite(
        mockup_path=str(mockup),
        video_path=str(video),
        output_path=str(output),
        bg_color=args.bg_color,
        screen_bg_color=args.screen_bg_color,
        threshold=args.threshold,
        crf=args.crf,
        preset=args.preset,
        scale=args.scale,
        fit_mode=args.fit_mode,
        screen_detection=args.screen_detection,
        video_codec=args.video_codec,
        bitrate=args.bitrate,
        scale_filter=args.scale_filter,
        max_output_height=args.max_output_height,
    )


if __name__ == "__main__":
    main()
