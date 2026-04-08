#!/usr/bin/env python3
"""Add Snapchat-style text overlay to videos without quality loss.

Snapchat style = full-width semi-transparent dark bar with bold white
text centered on it.
"""

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from pilmoji import Pilmoji


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


def get_video_info(input_path: str) -> dict:
    """Get video dimensions using ffprobe."""
    cmd = [
        "ffprobe", "-v", "quiet", "-print_format", "json",
        "-show_streams", input_path,
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


def find_system_font(name: str = "Arial") -> str | None:
    """Try to find a bold system font. Returns path or None."""
    candidates = [
        Path("/System/Library/Fonts/Supplemental") / f"{name} Bold.ttf",
        Path("/System/Library/Fonts/Supplemental") / f"{name}.ttf",
        Path("/System/Library/Fonts") / f"{name}.ttf",
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
        Path("/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"),
        Path("C:/Windows/Fonts/arialbd.ttf"),
        Path("C:/Windows/Fonts/arial.ttf"),
    ]
    for p in candidates:
        if p.exists():
            return str(p)
    return None


def create_overlay_image(
    width: int,
    height: int,
    text: str,
    y_position: str = "center",
    font_path: str | None = None,
    font_size: int | None = None,
    text_color: tuple = (255, 255, 255, 255),
    bar_color: tuple = (0, 0, 0, 140),
) -> str:
    """Create a transparent PNG with the Snapchat-style text bar.

    Text auto-wraps to multiple lines if it doesn't fit in one line,
    just like Snapchat. Font size matches Snapchat's default (~height/30).

    Returns the path to the temp PNG file.
    """
    if font_size is None:
        font_size = max(14, height // 45)

    # Load font
    if font_path and Path(font_path).is_file():
        font = ImageFont.truetype(font_path, font_size)
    else:
        system_font = find_system_font()
        if system_font:
            font = ImageFont.truetype(system_font, font_size)
        else:
            font = ImageFont.load_default(size=font_size)

    # Create transparent image
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Max text width: ~85% of video width (padding on sides like Snapchat)
    max_text_w = int(width * 0.85)

    # Use Pilmoji for emoji-aware text measurement and drawing
    with Pilmoji(img) as moji:
        # Word-wrap: break text into lines that fit within max width
        words = text.split()
        lines = []
        current_line = ""
        for word in words:
            test_line = f"{current_line} {word}".strip()
            tw, th = moji.getsize(test_line, font=font)
            if tw <= max_text_w:
                current_line = test_line
            else:
                if current_line:
                    lines.append(current_line)
                current_line = word
        if current_line:
            lines.append(current_line)

        if not lines:
            lines = [text]

        # Measure each line and total block height
        line_spacing = int(font_size * 0.35)
        line_heights = []
        line_widths = []
        for line in lines:
            lw, lh = moji.getsize(line, font=font)
            line_widths.append(lw)
            line_heights.append(lh)

        total_text_h = sum(line_heights) + line_spacing * (len(lines) - 1)

        # Bar padding above and below text
        pad_y = int(font_size * 0.6)

        # Vertical position of the bar
        if y_position == "top":
            bar_top = height // 8
        elif y_position == "bottom":
            bar_top = height - height // 8 - total_text_h - 2 * pad_y
        else:  # center (slightly below middle, like Snapchat)
            bar_top = (height - total_text_h - 2 * pad_y) // 2 + height // 10

        bar_bottom = bar_top + total_text_h + 2 * pad_y

        # Draw full-width semi-transparent bar
        draw.rectangle(
            [(0, bar_top), (width, bar_bottom)],
            fill=bar_color,
        )

        # Draw each line centered on the bar (with emoji support)
        cursor_y = bar_top + pad_y
        for i, line in enumerate(lines):
            lw = line_widths[i]
            text_x = (width - lw) // 2
            moji.text(
                (text_x, cursor_y), line, font=font, fill=text_color,
            )
            cursor_y += line_heights[i] + line_spacing

    # Save to temp file
    tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    img.save(tmp.name)
    return tmp.name


def run_overlay(
    input_path: str,
    output_path: str,
    text: str,
    y_position: str = "center",
    font_size: int | None = None,
    font_path: str | None = None,
    text_color: tuple = (255, 255, 255, 255),
    bg_opacity: float = 0.55,
    crf: int | None = None,
) -> None:
    """Render the Snapchat-style overlay onto the video."""
    info = get_video_info(input_path)

    bar_alpha = int(bg_opacity * 255)
    bar_color = (0, 0, 0, bar_alpha)

    overlay_path = create_overlay_image(
        width=info["width"],
        height=info["height"],
        text=text,
        y_position=y_position,
        font_path=font_path,
        font_size=font_size,
        text_color=text_color,
        bar_color=bar_color,
    )

    if crf is None:
        crf = 17

    # Composite: overlay PNG on top of video
    cmd = [
        "ffmpeg", "-y",
        "-i", input_path,
        "-i", overlay_path,
        "-filter_complex", "[0:v][1:v]overlay=0:0",
        "-c:v", "libx264",
        "-crf", str(crf),
        "-preset", "slow",
        "-c:a", "copy",
        "-movflags", "+faststart",
        output_path,
    ]

    print(f"Overlay image: {overlay_path}")
    result = subprocess.run(cmd)

    Path(overlay_path).unlink(missing_ok=True)

    if result.returncode != 0:
        sys.exit("FFmpeg failed.")
    print(f"\nDone! Output saved to: {output_path}")


def parse_color(color_str: str) -> tuple:
    """Parse a color string like 'white', '#FF0000', '255,255,0'."""
    named = {
        "white": (255, 255, 255, 255),
        "black": (0, 0, 0, 255),
        "red": (255, 0, 0, 255),
        "yellow": (255, 255, 0, 255),
        "green": (0, 255, 0, 255),
        "blue": (0, 0, 255, 255),
    }
    lower = color_str.lower().strip()
    if lower in named:
        return named[lower]

    if color_str.startswith("#"):
        h = color_str.lstrip("#")
        return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), 255)

    parts = [int(x.strip()) for x in color_str.split(",")]
    if len(parts) == 3:
        return (*parts, 255)
    return tuple(parts)


def main():
    parser = argparse.ArgumentParser(
        description="Add Snapchat-style text overlay to a video.",
    )
    parser.add_argument("input", help="Input video file")
    parser.add_argument("text", help="Overlay text")
    parser.add_argument(
        "-o", "--output",
        help="Output file (default: <input>_overlay.<ext>)",
    )
    parser.add_argument(
        "-y", "--y-position",
        default="center",
        choices=["top", "center", "bottom"],
        help="Vertical position (default: center)",
    )
    parser.add_argument(
        "--font-size", type=int, default=None,
        help="Font size in px (default: auto)",
    )
    parser.add_argument(
        "--font", default=None,
        help="Path to a .ttf font file",
    )
    parser.add_argument(
        "--text-color", default="white",
        help="Text color: name, #hex, or r,g,b (default: white)",
    )
    parser.add_argument(
        "--bg-opacity", type=float, default=0.55,
        help="Background bar opacity 0.0-1.0 (default: 0.55)",
    )
    parser.add_argument(
        "--crf", type=int, default=None,
        help="CRF quality (lower=better, default: 17)",
    )

    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        sys.exit(f"File not found: {input_path}")

    if args.output:
        output_path = Path(args.output)
    else:
        output_dir = get_output_root("snapchat-overlay")
        output_path = output_dir / f"{input_path.stem}_overlay{input_path.suffix}"

    output_path.parent.mkdir(parents=True, exist_ok=True)

    run_overlay(
        input_path=str(input_path),
        output_path=str(output_path),
        text=args.text,
        y_position=args.y_position,
        font_size=args.font_size,
        font_path=args.font,
        text_color=parse_color(args.text_color),
        bg_opacity=args.bg_opacity,
        crf=args.crf,
    )


if __name__ == "__main__":
    main()
