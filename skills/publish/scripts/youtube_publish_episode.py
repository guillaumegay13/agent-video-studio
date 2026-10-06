#!/usr/bin/env python3
"""Upload a full-length episode to YouTube, with its custom thumbnail.

Defaults to private so the upload can be reviewed in YouTube Studio first;
pass --publish-at to schedule the public release instead.

    python3 skills/publish/scripts/youtube_publish_episode.py \
        --video episode.mp4 --title "..." --description-file description.txt \
        --thumbnail thumbnail.png --tags "IA,podcast" --dry-run
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.config import load_config
from scripts import youtube_uploader as yt

LEDGER = Path(__file__).resolve().parents[1] / "outputs" / "publish" / "episodes.json"
TITLE_MAX = 100
DESCRIPTION_MAX_BYTES = 5000


def validate_metadata(title: str, description: str) -> list[str]:
    """Return YouTube metadata errors (empty when valid). Pure, unit-testable."""
    errors = []
    if not title.strip():
        errors.append("title is empty")
    if len(title) > TITLE_MAX:
        errors.append(f"title is {len(title)} chars (max {TITLE_MAX})")
    if len(description.encode("utf-8")) > DESCRIPTION_MAX_BYTES:
        errors.append(f"description exceeds {DESCRIPTION_MAX_BYTES} bytes")
    for field, text in (("title", title), ("description", description)):
        if "<" in text or ">" in text:
            errors.append(f"{field} contains '<' or '>' (rejected by YouTube)")
    return errors


def build_episode_body(title: str, description: str, tags: list[str],
                       privacy: str, publish_at: datetime | None,
                       category_id: str = yt.DEFAULT_CATEGORY_ID) -> dict:
    """videos.insert body for an episode: scheduled when publish_at is set."""
    status = {"privacyStatus": privacy, "selfDeclaredMadeForKids": False}
    if publish_at is not None:
        status = {**status, "privacyStatus": "private",
                  "publishAt": yt.to_rfc3339(publish_at)}
    return {
        "snippet": {"title": title, "description": description,
                    "tags": tags, "categoryId": category_id},
        "status": status,
    }


def upload_episode(service, video_path: Path, body: dict) -> str:
    from googleapiclient.http import MediaFileUpload

    media = MediaFileUpload(str(video_path), mimetype="video/mp4",
                            resumable=True, chunksize=50 * 1024 * 1024)
    request = service.videos().insert(part="snippet,status", body=body, media_body=media)
    response = None
    while response is None:
        progress, response = request.next_chunk()
        if progress:
            print(f"  uploaded {int(progress.progress() * 100)}%", flush=True)
    return response["id"]


def set_thumbnail(service, video_id: str, thumbnail: Path) -> None:
    from googleapiclient.http import MediaFileUpload

    mimetype = "image/png" if thumbnail.suffix.lower() == ".png" else "image/jpeg"
    service.thumbnails().set(videoId=video_id,
                             media_body=MediaFileUpload(str(thumbnail), mimetype=mimetype)).execute()


def record(entry: dict) -> None:
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    entries = json.loads(LEDGER.read_text()) if LEDGER.exists() else []
    entries.append(entry)
    LEDGER.write_text(json.dumps(entries, indent=2, ensure_ascii=False) + "\n")


def parse_args(argv=None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--video", required=True, type=Path)
    p.add_argument("--title", required=True)
    p.add_argument("--description-file", required=True, type=Path)
    p.add_argument("--thumbnail", type=Path)
    p.add_argument("--tags", default="", help="comma-separated")
    p.add_argument("--privacy", choices=["private", "unlisted", "public"], default="private")
    p.add_argument("--publish-at", help="ISO datetime with offset, e.g. 2026-10-08T18:00:00+02:00")
    p.add_argument("--category-id", default=yt.DEFAULT_CATEGORY_ID)
    p.add_argument("--dry-run", action="store_true")
    return p.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    description = args.description_file.read_text(encoding="utf-8").strip()
    tags = [t.strip() for t in args.tags.split(",") if t.strip()]
    publish_at = datetime.fromisoformat(args.publish_at) if args.publish_at else None
    if publish_at is not None and publish_at.tzinfo is None:
        print("--publish-at needs a timezone offset", file=sys.stderr)
        return 2

    errors = validate_metadata(args.title, description)
    for path in filter(None, (args.video, args.thumbnail)):
        if not path.exists():
            errors.append(f"file not found: {path}")
    if errors:
        print("Invalid episode metadata:\n- " + "\n- ".join(errors), file=sys.stderr)
        return 2

    body = build_episode_body(args.title, description, tags, args.privacy,
                              publish_at, args.category_id)
    if args.dry_run:
        print(json.dumps(body, indent=2, ensure_ascii=False))
        print(f"thumbnail: {args.thumbnail}")
        return 0

    service = yt.build_service(load_config())
    print(f"Uploading {args.video.name}...")
    video_id = upload_episode(service, args.video, body)
    print(f"Uploaded: https://youtu.be/{video_id} ({body['status']['privacyStatus']})")
    if args.thumbnail:
        set_thumbnail(service, video_id, args.thumbnail)
        print("Thumbnail set.")
    record({"video_id": video_id, "title": args.title, "file": str(args.video.resolve()),
            "status": body["status"],
            "uploaded_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")})
    return 0


if __name__ == "__main__":
    sys.exit(main())
