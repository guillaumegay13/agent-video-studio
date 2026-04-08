#!/usr/bin/env python3
"""
Generate a video from a text prompt using inference.sh models.
"""

import argparse
import json
import os
import subprocess
import sys
import tempfile


def run(cmd, error_msg=None):
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        msg = error_msg or f"Command failed: {' '.join(str(c) for c in cmd)}"
        print(f"ERROR: {msg}", file=sys.stderr)
        print(result.stderr or result.stdout, file=sys.stderr)
        sys.exit(1)
    return result


def main():
    parser = argparse.ArgumentParser(description="Generate video from text prompt via inference.sh")
    parser.add_argument("--prompt", required=True, help="Text prompt")
    parser.add_argument("--model", default="google/veo-3-1-lite", help="Model ID (default: google/veo-3-1-lite)")
    parser.add_argument("--aspect-ratio", default="9:16", choices=["9:16", "16:9", "1:1"], help="Aspect ratio")
    parser.add_argument("--resolution", default="720p", choices=["720p", "1080p"], help="Resolution")
    parser.add_argument("--duration", type=int, default=4, help="Duration in seconds (min 4)")
    parser.add_argument("--negative-prompt", help="Negative prompt (not supported by all models)")
    parser.add_argument("--trim", type=float, help="Trim output to N seconds")
    parser.add_argument("--no-audio", action="store_true", help="Strip audio from output")
    parser.add_argument("-o", "--output", required=True, help="Output file path")
    args = parser.parse_args()

    if args.duration < 4:
        print("WARNING: minimum duration is 4s, setting to 4", file=sys.stderr)
        args.duration = 4

    # Build input
    video_input = {
        "prompt": args.prompt,
        "aspect_ratio": args.aspect_ratio,
        "resolution": args.resolution,
        "duration": args.duration,
    }
    if args.negative_prompt:
        video_input["negative_prompt"] = args.negative_prompt

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(video_input, f)
        input_file = f.name

    print(f"Generating video with {args.model}...")
    result = run(["infsh", "app", "run", args.model, "-f", "run", "--input", input_file],
                 "Video generation failed")
    os.unlink(input_file)

    # Extract video URL
    video_url = None
    for line in result.stdout.splitlines():
        if "https://" in line and ".mp4" in line:
            video_url = line.strip().strip('"').strip("'")
            break

    if not video_url:
        # Try parsing JSON output
        try:
            data = json.loads(result.stdout)
            videos = data.get("videos", [])
            if videos:
                video_url = videos[0]
        except Exception:
            pass

    if not video_url:
        print("ERROR: Could not find video URL in output:", file=sys.stderr)
        print(result.stdout, file=sys.stderr)
        sys.exit(1)

    print(f"Downloading from {video_url}...")
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
        tmp = f.name
    run(["curl", "-sL", video_url, "-o", tmp], "Failed to download video")

    # Post-process
    output = args.output
    needs_processing = args.no_audio or args.trim

    if needs_processing:
        ffmpeg_cmd = ["ffmpeg", "-v", "error", "-i", tmp]
        if args.no_audio:
            ffmpeg_cmd += ["-an"]
        if args.trim:
            ffmpeg_cmd += ["-t", str(args.trim)]
        ffmpeg_cmd += ["-c:v", "copy", output, "-y"]
        run(ffmpeg_cmd, "Failed to post-process video")
        os.unlink(tmp)
    else:
        os.rename(tmp, output)

    print(f"Done! Saved to: {output}")


if __name__ == "__main__":
    main()
