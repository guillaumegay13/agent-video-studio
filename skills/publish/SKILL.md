---
name: publish
description: Schedule viral short clips to YouTube as Shorts via direct upload to the YouTube Data API. Use when the user wants to publish or schedule clips produced by the viral-clips skill, auto-caption clips with catchy LLM titles, link each Short back to the source episode, or run a daily short-form publishing cadence. Uploads each clip privately with a scheduled publish time — no Buffer, no third-party media host.
---

# Publish

Take viral-clips outputs to scheduled YouTube Shorts. Each clip is uploaded
**private** with a `publishAt` timestamp, so YouTube auto-publishes it on schedule.
The file is uploaded directly to YouTube, so no public media host is involved.

## Prerequisites

- `.env` in this skill folder (copy `.env.example`): `YOUTUBE_CLIENT_ID`,
  `YOUTUBE_CLIENT_SECRET`, `YOUTUBE_REFRESH_TOKEN`, and an LLM key
  (`OPENAI_API_KEY` or `ANTHROPIC_API_KEY`).
- `pip install -r requirements.txt`.
- **One-time auth:** in Google Cloud, create a project, enable *YouTube Data API v3*,
  create an OAuth client of type **Desktop app**, put the client id/secret in `.env`,
  then run `youtube_auth.py` once to authorize and capture the refresh token.

```bash
python3 skills/publish/scripts/youtube_auth.py
```

## Commands

```bash
# Schedule clips from a viral-clips output folder, one Short per day at 18:00 Paris
python3 skills/publish/scripts/youtube_publish.py \
    --clips ../youtube-to-viral-clips/outputs/<run-dir> \
    --max-clips 6 --per-day 1 --hour 18 --timezone Europe/Paris --order score

# Preview the schedule + generated titles without uploading
python3 skills/publish/scripts/youtube_publish.py --clips <dir> --dry-run

# Drop specific clip indices (e.g. a redundant moment)
python3 skills/publish/scripts/youtube_publish.py --clips <dir> --exclude 5

# List videos already scheduled on the channel (needs the readonly scope)
python3 skills/publish/scripts/youtube_publish.py --list
```

## How it works

1. `discover_clips` maps each `viral_clip_<N>_*_subtitled.mp4` to its
   `clip_<N>_score_*.json` metadata.
2. The LLM captioner drafts a catchy, same-language **title** + description +
   hashtags; `#Shorts` and a `🎥 <source episode URL>` link are always included
   (the URL is recovered from the clip metadata).
3. `compute_slots` assigns one UTC `publishAt` per day; runs **stack after**
   already-scheduled clips (read from the local ledger) so re-runs don't double-book.
4. Each clip is uploaded private via `videos.insert` with `status.publishAt`.
   YouTube flips it to public at that time.
5. A local ledger (`outputs/publish/ledger.json`) records each (clip → video id)
   so re-runs skip clips already scheduled.

## Notes

- **Quota:** the Data API default is 10,000 units/day and each upload costs 1,600,
  so ~6 uploads/day max. For more clips, run again the next day — the schedule
  continues stacking and already-uploaded clips are skipped.
- Uploads are private until their `publishAt`; review/edit/cancel any in YouTube
  Studio (Content → Shorts) before they go public.
- Ordering: `--order score` (strongest first) or `--order chrono` (episode order).
