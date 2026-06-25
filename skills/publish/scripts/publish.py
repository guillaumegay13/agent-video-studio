#!/usr/bin/env python3
"""Publish viral clips to Buffer-connected channels on a schedule."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.config import load_config
from scripts.clips import discover_clips
from scripts.scheduling import compute_slots
from scripts.ledger import Ledger
from scripts.captioner import build_caption
from scripts import media_host
from scripts.buffer_client import BufferClient, CapabilityError, MutationError

def _parse_due_at(value: str):
    """Parse Buffer's ISO-8601 dueAt string into a UTC-aware datetime."""
    from datetime import datetime
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


TARGET_SERVICES = {"youtube", "tiktok", "instagram"}


class ChannelResolutionError(Exception):
    pass


def resolve_channels(requested, channels, allow_missing):
    """Map requested service names to connected, usable channel dicts.

    Returns (resolved_channels, skipped_messages). Missing channels are a hard
    error unless allow_missing. Disconnected/locked/paused channels are skipped."""
    by_service = {c["service"]: c for c in channels}
    resolved, skipped, missing = [], [], []
    for service in requested:
        ch = by_service.get(service)
        if ch is None:
            missing.append(service)
            continue
        if ch.get("isDisconnected") or ch.get("isLocked") or ch.get("isQueuePaused"):
            skipped.append(f"{service}: channel disconnected/locked/paused")
            continue
        resolved.append(ch)
    if missing and not allow_missing:
        raise ChannelResolutionError(
            f"Channels not connected in Buffer: {', '.join(missing)}. "
            f"Connect them in Buffer's UI or pass --allow-missing-channels."
        )
    skipped.extend(missing)
    return resolved, skipped


# YouTube requires a category on every post (Buffer rejects posts without one,
# verified live: "Invalid post: YouTube posts require a category"). 22 = People &
# Blogs is valid in every region; override with --youtube-category.
DEFAULT_YOUTUBE_CATEGORY = "22"


def build_metadata(service, caption, youtube_category=DEFAULT_YOUTUBE_CATEGORY):
    """Map a Caption to Buffer per-platform metadata for one service."""
    if service == "youtube":
        return {"youtube": {"title": caption.youtube_title, "privacy": "public",
                            "madeForKids": False, "categoryId": youtube_category}}
    if service == "tiktok":
        return {"tiktok": {"title": caption.tiktok_title}}
    if service == "instagram":
        return {"instagram": {"type": "reel", "shouldShareToFeed": True}}
    return {}


def schedule_run(clips_dir, resolved_channels, buffer, org_id, cfg, ledger,
                 per_day, start_date, hour, end_hour, tz, max_clips, dry_run):
    """Upload + caption + schedule each clip across resolved channels.

    Idempotent: a (clip, channel) already in the ledger is skipped. Buffer's
    posts query supplies occupied slots per channel."""
    clips = discover_clips(clips_dir)[:max_clips]
    summary = {"planned": 0, "posted": 0, "skipped": [], "modes": {}}

    # Occupied slots per channel come from Buffer (source of truth).
    occupied = {}
    for ch in resolved_channels:
        occupied[ch["id"]] = {
            _parse_due_at(s) for s in buffer.list_scheduled_due_ats(org_id, ch["id"])
        }

    for clip in clips:
        clip_key = f"clip_{clip.index}"
        caption = build_caption(clip.metadata, provider=cfg.caption_provider, cfg=cfg)
        upload = None
        for ch in resolved_channels:
            if ledger.has_post(clip_key, ch["id"]):
                summary["skipped"].append(f"{clip_key}->{ch['service']}: already posted")
                continue
            # Lazily upload once per clip, on first channel that needs it.
            if upload is None:
                if dry_run:
                    upload = {"public_id": f"publish/{clip_key}",
                              "video_url": "(dry-run)", "thumbnail_url": None}
                else:
                    upload = media_host.upload_clip(clip.video_path, cfg)
                ledger.upsert_asset(clip_key, upload["public_id"], upload["video_url"])
            # Allocate the next free slot for this channel.
            slot = compute_slots(count=1, per_day=per_day, start_date=start_date,
                                 hour=hour, end_hour=end_hour, tz=tz,
                                 occupied=occupied[ch["id"]])[0]
            occupied[ch["id"]].add(slot)
            due_at = slot.strftime("%Y-%m-%dT%H:%M:%SZ")
            metadata = build_metadata(ch["service"], caption)
            summary["planned"] += 1
            if dry_run:
                continue
            mode = "automatic"
            try:
                post_id = buffer.create_post(
                    channel_id=ch["id"], text=caption.caption,
                    video_url=upload["video_url"],
                    thumbnail_url=upload["thumbnail_url"], due_at=due_at,
                    scheduling_type=mode, metadata=metadata)
            except CapabilityError:
                mode = "notification"
                try:
                    post_id = buffer.create_post(
                        channel_id=ch["id"], text=caption.caption,
                        video_url=upload["video_url"],
                        thumbnail_url=upload["thumbnail_url"], due_at=due_at,
                        scheduling_type=mode, metadata=metadata)
                except MutationError as exc:
                    summary["skipped"].append(
                        f"{clip_key}->{ch['service']}: notification retry failed: {exc}")
                    continue
            except MutationError as exc:
                summary["skipped"].append(f"{clip_key}->{ch['service']}: {exc}")
                continue
            ledger.record_post(clip_key, ch["id"], post_id, mode, due_at, "posted")
            ledger.save()
            summary["posted"] += 1
            summary["modes"][ch["service"]] = mode
    return summary


def run_pipeline(raw_path: Path, max_clips: int) -> Path:
    """Run the sibling youtube-to-viral-clips pipeline; return its outputs dir."""
    import subprocess
    repo = Path(__file__).resolve().parents[3] / "youtube-to-viral-clips"
    if not repo.exists():
        sys.exit(f"viral-clips pipeline not found at {repo}")
    subprocess.run(
        [sys.executable, "main.py", "--file", str(raw_path),
         "--layout", "split-stack", "--subtitle-style", "Viral Highlight",
         "--clips", str(max_clips)],
        cwd=str(repo), check=True)
    return repo / "outputs"


def main(argv=None):
    p = argparse.ArgumentParser(description="Publish viral clips to Buffer.")
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--raw", type=Path, help="Raw mp4: run pipeline then schedule")
    src.add_argument("--clips", type=Path, help="Existing viral-clips outputs dir")
    src.add_argument("--cleanup", action="store_true", help="Delete sent assets")
    p.add_argument("--channels", default="youtube",
                   help="comma list: youtube,tiktok,instagram")
    p.add_argument("--allow-missing-channels", action="store_true")
    p.add_argument("--max-clips", type=int, default=5)
    p.add_argument("--per-day", type=int, default=1)
    p.add_argument("--start-date", default=None, help="YYYY-MM-DD (default: tomorrow)")
    p.add_argument("--hour", type=int, default=18)
    p.add_argument("--end-hour", type=int, default=22)
    p.add_argument("--timezone", default="UTC")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args(argv)

    from datetime import date, timedelta
    cfg = load_config(require=("BUFFER_ACCESS_TOKEN",) if not args.dry_run else ())
    out_root = Path(__file__).resolve().parents[2] / "outputs" / "publish"
    ledger = Ledger(out_root / "ledger.json")
    buffer = BufferClient(token=cfg.buffer_token)

    if args.cleanup:
        from scripts.cleanup import run_cleanup
        result = run_cleanup(buffer, ledger, cfg)
        print(f"Cleanup: deleted {result['deleted']} assets, "
              f"retained {result['retained']}")
        return

    org_id = buffer.get_org_id()
    channels = buffer.list_channels(org_id)
    requested = [c.strip() for c in args.channels.split(",") if c.strip()]
    resolved, skipped = resolve_channels(requested, channels,
                                         args.allow_missing_channels)
    for s in skipped:
        print(f"  skip: {s}")

    clips_dir = run_pipeline(args.raw, args.max_clips) if args.raw else args.clips
    start = (date.fromisoformat(args.start_date) if args.start_date
             else date.today() + timedelta(days=1))
    summary = schedule_run(
        clips_dir=clips_dir, resolved_channels=resolved, buffer=buffer,
        org_id=org_id, cfg=cfg, ledger=ledger, per_day=args.per_day,
        start_date=start, hour=args.hour, end_hour=args.end_hour,
        tz=args.timezone, max_clips=args.max_clips, dry_run=args.dry_run)
    print(f"Planned {summary['planned']}, posted {summary['posted']}, "
          f"modes {summary['modes']}")


if __name__ == "__main__":
    main()
