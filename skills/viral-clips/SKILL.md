---
name: viral-clips
description: Extract viral short clips from a YouTube video or local podcast recording using the youtube-to-viral-clips pipeline. Use when Codex needs to detect viral moments with AI, convert a two-speaker podcast into vertical shorts with the split-stack layout, add karaoke word-highlight subtitles, or batch-generate social media clips from long-form video.
---

# Viral Clips

Use the `youtube-to-viral-clips` CLI to turn long-form video into subtitled vertical shorts. The pipeline downloads (or reads a local file), transcribes with Whisper, scores transcript segments for viral potential with an LLM, extracts the best clips, and renders animated subtitles.

The pipeline lives in a sibling repository: `../youtube-to-viral-clips` relative to this repo (clone from https://github.com/guillaumegay13/youtube-to-viral-clips if missing).

## Workflow

1. Take a YouTube URL or local video path from the user.
2. Pick the layout: `--layout split-stack` for two-speaker side-by-side podcast framing, `--layout center-crop` (default) for single-speaker video.
3. Default to `--subtitle-style "Viral Highlight"` for social media shorts; it renders karaoke captions where the spoken word pops in yellow.
4. Choose the AI provider with `--provider` (`openai`, `anthropic`, or `ollama` for local). The provider's API key must be in the environment or the repo's `.env`.
5. Review the generated clips and their `.json` metadata (score, reason, timestamps) in `outputs/`, then surface the top clips to the user with their virality scores.

## Command

```bash
cd ../youtube-to-viral-clips
python3 main.py (--url "<youtube-url>" | --file "<local-video>") [options]
```

Examples:

```bash
# Two-speaker podcast episode to viral shorts
python3 main.py --file "/path/to/episode.mp4" --layout split-stack --subtitle-style "Viral Highlight" --clips 5 --provider openai

# Published YouTube video, single speaker
python3 main.py --url "https://youtube.com/watch?v=VIDEO_ID" --clips 3 --subtitle-style "Viral Highlight"

# Raw clips only, no subtitles
python3 main.py --file "/path/to/episode.mp4" --layout split-stack --no-subtitles
```

## Key Options

- `--clips N`: maximum number of clips to generate (default 5)
- `--min-score N`: minimum virality score 0-10 (default 7.0); lower it if no moments pass
- `--layout`: `center-crop` | `split-stack`
- `--format`: `vertical` (9:16, default) | `horizontal` (16:9)
- `--subtitle-style`: `Classic`, `Bold Yellow`, `Submagic Yellow`, `Minimal`, `TikTok Style`, `Neon`, `Ultra Bold`, `Viral Highlight`, `Viral Bold`
- `--quality`: download quality for YouTube sources (`360p` to `1080p`)
- `--force-transcribe`: ignore the cached transcript

## Output Behavior

- Clips land in `../youtube-to-viral-clips/outputs/` as `viral_clip_<n>_score_<score>.mp4` plus `_subtitled.mp4` variants.
- Each clip has a sibling `.json` with start/end times, score, and the reason the moment was flagged.
- Transcripts are cached in `transcripts/`; re-runs on the same video skip transcription.

## Guidance

- Transcription is the slow step (roughly 0.3x video duration on CPU); warn the user before processing very long episodes.
- If no moments reach the score threshold, the CLI falls back to the top 3 moments instead of failing.
- After generating clips, the other studio skills (`video-stitch`, `snapchat-overlay`, `video-speed`) can post-process them — e.g. stitch a hook in front of a viral clip.
