#!/usr/bin/env python3
"""Schedule viral clips straight to YouTube as Shorts, one per day.

Direct Data-API upload — no Buffer, no Cloudinary. Each clip is uploaded private
with a `publishAt` timestamp so YouTube releases it publicly on schedule.

    python3 skills/publish/scripts/youtube_publish.py \
        --clips ../youtube-to-viral-clips/outputs/4OlWf_week \
        --max-clips 6 --per-day 1 --hour 18 --timezone Europe/Paris --dry-run
"""
from __future__ import annotations

import argparse
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.config import load_config, ConfigError
from scripts.clips import discover_clips
from scripts.captioner import build_caption, compose_description
from scripts.scheduling import compute_slots
from scripts.ledger import Ledger
from scripts import youtube_uploader as yt

CHANNEL = "youtube"  # ledger channel key for direct YouTube posts


def _score(clip) -> float:
    try:
        return float(clip.metadata.get("score", 0.0))
    except (TypeError, ValueError):
        return 0.0


def select_and_order(clips, order: str, max_clips: int, exclude=()) -> list:
    """Pick which clips to schedule and in what daily order.

    score: strongest virality first (so day 1 leads with the best clip).
    chrono: in episode order (by source start_time).
    exclude: clip indices to drop before selecting (e.g. a redundant moment)."""
    exclude = set(exclude)
    kept = [c for c in clips if c.index not in exclude]
    if order == "chrono":
        ordered = sorted(kept, key=lambda c: c.metadata.get("start_time", 0.0))
    else:  # "score"
        ordered = sorted(kept, key=lambda c: (-_score(c), c.index))
    return ordered[:max_clips]


def shorts_description(caption) -> str:
    """Post body with the #Shorts marker guaranteed present."""
    body = compose_description(caption)
    if "#shorts" not in body.lower():
        body = f"{body}\n\n#Shorts"
    return body


def build_tags(caption) -> list[str]:
    tags = [h.lstrip("#") for h in caption.hashtags if h.strip()]
    if not any(t.lower() == "shorts" for t in tags):
        tags.append("Shorts")
    return tags


def occupied_slots(ledger) -> set:
    """UTC datetimes already taken by previously-scheduled posts.

    Feeding these to compute_slots makes each run stack new clips onto the next
    free days instead of double-booking ones we've already scheduled."""
    taken = set()
    for post in ledger.all_posts():
        due = post.get("due_at")
        if not due:
            continue
        try:
            taken.add(datetime.strptime(due, "%Y-%m-%dT%H:%M:%SZ")
                      .replace(tzinfo=timezone.utc))
        except (TypeError, ValueError):
            continue
    return taken


def run(clips_dir, ledger, cfg, *, max_clips, per_day, start_date, hour,
        end_hour, tz, order, category, dry_run, exclude=(), service=None):
    clips = discover_clips(clips_dir)
    selected = select_and_order(clips, order, max_clips, exclude)
    if not selected:
        print(f"No clips found in {clips_dir}")
        return {"planned": 0, "scheduled": 0, "skipped": []}

    slots = compute_slots(count=len(selected), per_day=per_day, start_date=start_date,
                          hour=hour, end_hour=end_hour, tz=tz,
                          occupied=occupied_slots(ledger))

    summary = {"planned": 0, "scheduled": 0, "skipped": []}
    for clip, slot in zip(selected, slots):
        clip_key = f"clip_{clip.index}"
        if ledger.has_post(clip_key, CHANNEL):
            summary["skipped"].append(f"{clip_key}: already scheduled")
            continue

        caption = build_caption(clip.metadata, provider=cfg.caption_provider, cfg=cfg)
        title = caption.youtube_title
        description = shorts_description(caption)
        tags = build_tags(caption)
        when = slot.astimezone().strftime("%a %d %b %H:%M %Z")
        summary["planned"] += 1

        print(f"\n• {clip_key}  →  publish {when}")
        print(f"  title: {title}")
        print(f"  tags:  {', '.join(tags)}")

        if dry_run:
            continue

        from googleapiclient.errors import HttpError
        try:
            video_id = yt.upload_video(service, clip.video_path, title, description,
                                       tags, slot, category_id=category)
        except HttpError as err:
            if yt.is_quota_error(err):
                print("\n⛔ Daily upload quota hit. Already-scheduled clips are saved; "
                      "re-run tomorrow with the SAME --start-date to finish the rest.")
                break
            summary["skipped"].append(f"{clip_key}: {err}")
            print(f"  ⚠️  upload failed: {err}")
            continue

        ledger.record_post(clip_key, CHANNEL, video_id, "scheduled",
                           yt.to_rfc3339(slot), "scheduled")
        ledger.save()
        summary["scheduled"] += 1
        print(f"  ✅ https://youtu.be/{video_id} (private until {when})")

    return summary


def main(argv=None):
    p = argparse.ArgumentParser(description="Schedule viral clips to YouTube as Shorts.")
    p.add_argument("--clips", type=Path, help="viral-clips outputs dir")
    p.add_argument("--max-clips", type=int, default=6,
                   help="how many clips to schedule (default 6 = daily quota cap)")
    p.add_argument("--per-day", type=int, default=1)
    p.add_argument("--start-date", default=None, help="YYYY-MM-DD (default: tomorrow)")
    p.add_argument("--hour", type=int, default=18)
    p.add_argument("--end-hour", type=int, default=22)
    p.add_argument("--timezone", default="UTC")
    p.add_argument("--order", choices=("score", "chrono"), default="score")
    p.add_argument("--exclude", default="",
                   help="comma list of clip indices to drop, e.g. 5")
    p.add_argument("--category", default=yt.DEFAULT_CATEGORY_ID)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--list", action="store_true",
                   help="list scheduled videos from YouTube and exit (needs readonly)")
    args = p.parse_args(argv)
    exclude = {int(x) for x in args.exclude.split(",") if x.strip()}

    if args.list:
        cfg = load_config(require=("YOUTUBE_REFRESH_TOKEN",))
        scheduled = yt.list_scheduled_videos(yt.build_service(cfg))
        if not scheduled:
            print("No scheduled videos found.")
        for s in scheduled:
            print(f"  {s['publishAt']}  {s['id']}  {s['title']}")
        return

    if not args.clips:
        sys.exit("--clips is required (unless using --list)")

    required = () if args.dry_run else (
        "YOUTUBE_CLIENT_ID", "YOUTUBE_CLIENT_SECRET", "YOUTUBE_REFRESH_TOKEN",
        "OPENAI_API_KEY")
    try:
        cfg = load_config(require=required)
    except ConfigError as exc:
        sys.exit(str(exc))

    out_root = Path(__file__).resolve().parents[1] / "outputs" / "publish"
    out_root.mkdir(parents=True, exist_ok=True)
    ledger = Ledger(out_root / "ledger.json")

    start = (date.fromisoformat(args.start_date) if args.start_date
             else date.today() + timedelta(days=1))

    service = None if args.dry_run else yt.build_service(cfg)
    summary = run(args.clips, ledger, cfg, max_clips=args.max_clips,
                  per_day=args.per_day, start_date=start, hour=args.hour,
                  end_hour=args.end_hour, tz=args.timezone, order=args.order,
                  category=args.category, dry_run=args.dry_run, exclude=exclude,
                  service=service)

    print(f"\nPlanned {summary['planned']}, scheduled {summary['scheduled']}, "
          f"skipped {len(summary['skipped'])}")
    for s in summary["skipped"]:
        print(f"  skip: {s}")


if __name__ == "__main__":
    main()
