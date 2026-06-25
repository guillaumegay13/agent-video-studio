---
name: publish
description: Schedule viral short clips to YouTube, TikTok, and Instagram via the Buffer API. Use when the user wants to publish or schedule clips produced by the viral-clips skill, take a raw mp4 all the way to scheduled social posts, auto-caption clips with an LLM, or run a daily short-form publishing cadence. Hosts clips on Cloudinary (Buffer needs a public video URL) and cleans them up after publishing.
---

# Publish

Take a raw mp4 (or an existing viral-clips output folder) to scheduled Buffer posts
on YouTube Shorts, TikTok, and Instagram Reels.

## Prerequisites

- `.env` in this skill folder (copy `.env.example`): `BUFFER_ACCESS_TOKEN`,
  `CLOUDINARY_*`, and an LLM key (`OPENAI_API_KEY` or `ANTHROPIC_API_KEY`).
- `pip install -r requirements.txt`.
- Connect each target channel inside Buffer's web UI first. Only connected channels
  can be scheduled; missing ones are a hard error unless `--allow-missing-channels`.
- TikTok/Instagram personal profiles often publish via `notification` (Buffer sends
  a phone reminder to tap-publish), not silent auto-publish. The run summary reports
  the mode used per channel.

## Commands

```bash
# raw video -> clips -> scheduled posts (one-shot)
python3 skills/publish/scripts/publish.py --raw /path/episode.mp4 \
    --channels youtube,tiktok,instagram --per-day 1 --hour 18 --timezone Europe/Paris

# schedule from an existing viral-clips output folder
python3 skills/publish/scripts/publish.py --clips ../youtube-to-viral-clips/outputs \
    --channels youtube

# preview without posting
python3 skills/publish/scripts/publish.py --clips <dir> --channels youtube --dry-run

# delete Cloudinary assets for posts Buffer has fully published
python3 skills/publish/scripts/publish.py --cleanup
```

## How it works

1. Discover clips and map each `clip_<N>_final_subtitled.mp4` to its
   `clip_<N>_score_*.json` metadata.
2. LLM drafts caption + per-platform title + hashtags (template fallback on error).
3. Upload the clip to Cloudinary once; Buffer fetches the public URL per channel.
4. Compute UTC `dueAt` slots (occupied slots read from Buffer), create one post per
   channel with `customScheduled`. Falls back to `notification` if the channel is
   reminder-only.
5. A local ledger (`outputs/publish/ledger.json`) tracks posts and assets for
   idempotency. `--cleanup` deletes a Cloudinary asset only once every post sharing
   it is `sent`.

## Notes

- Posts are scheduled, never instant — review/cancel in Buffer before `dueAt`.
- Re-running is safe: already-posted (clip, channel) pairs are skipped.
