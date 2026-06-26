"""Direct YouTube uploads via the Data API v3.

Replaces the Buffer + Cloudinary path for YouTube-only publishing: no public
media host is needed because we upload the file straight to YouTube and let it
schedule the public release with `status.publishAt`.
"""
from __future__ import annotations

from datetime import datetime, timezone

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    # readonly lets us list/verify scheduled videos and stack after manual schedules
    "https://www.googleapis.com/auth/youtube.readonly",
]
TOKEN_URI = "https://oauth2.googleapis.com/token"
# 22 = "People & Blogs": valid in every region and a safe default for talk clips.
DEFAULT_CATEGORY_ID = "22"


def to_rfc3339(dt: datetime) -> str:
    """Format a datetime as the UTC RFC3339 string YouTube's publishAt expects."""
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_insert_body(title: str, description: str, tags: list[str],
                      publish_at: datetime, category_id: str = DEFAULT_CATEGORY_ID) -> dict:
    """Construct the videos.insert request body for a scheduled upload.

    The video is uploaded private with a publishAt timestamp; YouTube flips it to
    public automatically at that moment. Pure function — no network — so the
    metadata mapping is unit-testable.
    """
    return {
        "snippet": {
            "title": title,
            "description": description,
            "tags": tags,
            "categoryId": category_id,
        },
        "status": {
            "privacyStatus": "private",
            "publishAt": to_rfc3339(publish_at),
            "selfDeclaredMadeForKids": False,
        },
    }


def build_service(cfg):
    """Build an authenticated YouTube Data API client from the stored refresh token."""
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    if not cfg.youtube_refresh_token:
        raise RuntimeError("YOUTUBE_REFRESH_TOKEN missing — run youtube_auth.py first.")

    creds = Credentials(
        token=None,
        refresh_token=cfg.youtube_refresh_token,
        client_id=cfg.youtube_client_id,
        client_secret=cfg.youtube_client_secret,
        token_uri=TOKEN_URI,
        scopes=SCOPES,
    )
    return build("youtube", "v3", credentials=creds, cache_discovery=False)


def upload_video(service, video_path, title, description, tags, publish_at,
                 category_id: str = DEFAULT_CATEGORY_ID) -> str:
    """Resumable-upload a clip as a scheduled (private→public at publishAt) video.

    Returns the new YouTube video id. Raises googleapiclient.errors.HttpError on
    API failures (the caller distinguishes quotaExceeded to stop cleanly)."""
    from googleapiclient.http import MediaFileUpload

    body = build_insert_body(title, description, tags, publish_at, category_id)
    media = MediaFileUpload(str(video_path), mimetype="video/mp4",
                            resumable=True, chunksize=-1)
    request = service.videos().insert(part="snippet,status", body=body, media_body=media)

    response = None
    while response is None:
        _status, response = request.next_chunk()
    return response["id"]


def list_scheduled_videos(service) -> list[dict]:
    """Return the channel's scheduled uploads (private with a future publishAt).

    Walks the channel's uploads playlist, then reads each video's status. Requires
    the youtube.readonly scope. Each item: {id, title, publishAt}."""
    channels = service.channels().list(part="contentDetails", mine=True).execute()
    items = channels.get("items", [])
    if not items:
        return []
    uploads = items[0]["contentDetails"]["relatedPlaylists"]["uploads"]

    video_ids: list[str] = []
    page_token = None
    while True:
        pl = service.playlistItems().list(
            part="contentDetails", playlistId=uploads, maxResults=50,
            pageToken=page_token).execute()
        video_ids += [it["contentDetails"]["videoId"] for it in pl.get("items", [])]
        page_token = pl.get("nextPageToken")
        if not page_token:
            break

    scheduled = []
    for i in range(0, len(video_ids), 50):
        batch = video_ids[i:i + 50]
        vids = service.videos().list(part="snippet,status",
                                     id=",".join(batch)).execute()
        for v in vids.get("items", []):
            status = v.get("status", {})
            if status.get("privacyStatus") == "private" and status.get("publishAt"):
                scheduled.append({
                    "id": v["id"],
                    "title": v["snippet"]["title"],
                    "publishAt": status["publishAt"],
                })
    scheduled.sort(key=lambda s: s["publishAt"])
    return scheduled


def is_quota_error(err) -> bool:
    """True if an HttpError is YouTube's daily-quota rejection (HTTP 403 quotaExceeded)."""
    status = getattr(getattr(err, "resp", None), "status", None)
    return status == 403 and b"quotaExceeded" in getattr(err, "content", b"") or \
        "quotaExceeded" in str(err)
