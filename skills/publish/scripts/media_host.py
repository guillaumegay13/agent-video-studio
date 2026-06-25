"""Cloudinary video hosting: upload (resource_type=video, chunked), derive
thumbnail URL, and destroy. Public IDs never include the .mp4 extension."""
from __future__ import annotations

from pathlib import Path

CHUNK_THRESHOLD = 100 * 1024 * 1024  # 100 MB -> upload_large


def public_id_for_clip(clip_filename: str, prefix: str = "publish") -> str:
    stem = Path(clip_filename).stem  # drops .mp4
    return f"{prefix}/{stem}"


def thumbnail_url(video_url: str) -> str:
    """Turn a delivery video URL into a still-frame JPEG URL at 1s."""
    base = video_url.rsplit(".", 1)[0]  # strip extension
    # insert the so_1 (start offset 1s) transformation after /upload/
    base = base.replace("/upload/", "/upload/so_1/", 1)
    return base + ".jpg"


def _configure(cfg):
    import cloudinary
    cloudinary.config(
        cloud_name=cfg.cloudinary_cloud_name,
        api_key=cfg.cloudinary_api_key,
        api_secret=cfg.cloudinary_api_secret,
        secure=True,
    )


def upload_clip(path: Path, cfg, prefix: str = "publish") -> dict:
    """Upload a video. Returns {public_id, video_url, thumbnail_url}."""
    import cloudinary.uploader
    _configure(cfg)
    path = Path(path)
    public_id = public_id_for_clip(path.name, prefix)
    uploader = (cloudinary.uploader.upload_large
                if path.stat().st_size > CHUNK_THRESHOLD
                else cloudinary.uploader.upload)
    result = uploader(str(path), resource_type="video", public_id=public_id,
                      overwrite=True)
    video_url = result["secure_url"]
    return {"public_id": result["public_id"], "video_url": video_url,
            "thumbnail_url": thumbnail_url(video_url)}


def destroy_clip(public_id: str, cfg) -> bool:
    import cloudinary.uploader
    _configure(cfg)
    result = cloudinary.uploader.destroy(public_id, resource_type="video",
                                         invalidate=True)
    return result.get("result") == "ok"
