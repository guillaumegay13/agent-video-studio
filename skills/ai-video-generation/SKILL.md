# AI Video Generation

Generate short videos from text prompts using inference.sh models.

## Available Models

| Model | ID | Aspect Ratios | Duration | Notes |
|---|---|---|---|---|
| Veo 3.1 Lite | `google/veo-3-1-lite` | 9:16, 16:9, 1:1 | 4–8s | Fast (~30-50s), includes audio, min duration 4s |
| Veo 3.1 | `google/veo-3-1` | 9:16, 16:9, 1:1 | 4–8s | Higher quality, slower |
| Veo 3 Fast | `google/veo-3-fast` | 9:16, 16:9, 1:1 | 4–8s | Fast variant |
| Wan 2.7 T2V | `alibaba/wan-2-7-t2v` | 9:16, 16:9, 1:1 | 4–8s | Supports negative_prompt |
| Wan 2.7 I2V | `alibaba/wan-2-7-i2v` | 9:16, 16:9, 1:1 | 4–8s | Image-to-video |
| Grok Video | `xai/grok-imagine-video` | 9:16, 16:9 | varies | xAI model |

## Basic Usage

```bash
# Text-to-video with Veo 3.1 Lite (recommended for vertical short-form)
cat > /tmp/video_input.json << EOF
{
  "prompt": "Your prompt here",
  "aspect_ratio": "9:16",
  "resolution": "720p",
  "duration": 8
}
EOF

infsh app run google/veo-3-1-lite -f run --input /tmp/video_input.json
```

Output includes a video URL — download and strip audio:
```bash
curl -sL "<video_url>" -o /tmp/raw.mp4
ffmpeg -i /tmp/raw.mp4 -an -t 3 -c:v copy output.mp4 -y
```

## Generator Script

```bash
/usr/bin/python3 skills/ai-video-generation/scripts/generate_video.py \
  --prompt "Your prompt here" \
  --model google/veo-3-1-lite \
  --aspect-ratio 9:16 \
  --duration 4 \
  --trim 3 \
  --no-audio \
  -o output.mp4
```

## Pitfalls

- Veo 3.1 Lite minimum duration is 4s (trim after if you need shorter)
- Veo does NOT support `negative_prompt` — omit it or the request fails
- Veo sometimes fails content filtering on audio even for innocent prompts — rephrase if blocked
- Always strip audio before using in a pipeline (models generate audio by default)
- Use `--trim` to get a shorter clip from a longer generation (e.g. trim to 3s for hooks)
- Prompts work best when they describe a single static or simple scene — avoid transitions
- For authentic UGC style: mention "handheld", "lo-fi", "natural light", "candid", avoid "cinematic"
