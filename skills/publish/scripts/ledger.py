"""Local idempotency + Cloudinary-asset map. NOT the scheduling source of truth.

Schema (JSON):
{
  "assets": {
     "<cloudinary_public_id>": {"clip_key": "...", "video_url": "..."}
  },
  "posts": [
     {"clip_key","channel_id","post_id","cloudinary_public_id",
      "mode","due_at","state"}   # state: uploaded|posted|published|cleaned
  ]
}
"""
from __future__ import annotations

import contextlib
import fcntl
import json
import os
import tempfile
from pathlib import Path


class Ledger:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._data = self._load()
        self._asset_clip: dict[str, str] = {}

    def _load(self) -> dict:
        if self.path.exists():
            with self.path.open() as f:
                return json.load(f)
        return {"assets": {}, "posts": []}

    def upsert_asset(self, clip_key, cloudinary_public_id, video_url):
        self._data["assets"][cloudinary_public_id] = {
            "clip_key": clip_key, "video_url": video_url,
        }
        self._asset_clip[clip_key] = cloudinary_public_id

    def _public_id_for_clip(self, clip_key):
        for pub_id, meta in self._data["assets"].items():
            if meta["clip_key"] == clip_key:
                return pub_id
        return None

    def record_post(self, clip_key, channel_id, post_id, mode, due_at, state):
        self._data["posts"].append({
            "clip_key": clip_key, "channel_id": channel_id, "post_id": post_id,
            "cloudinary_public_id": self._public_id_for_clip(clip_key),
            "mode": mode, "due_at": due_at, "state": state,
        })

    def has_post(self, clip_key, channel_id) -> bool:
        return any(p["clip_key"] == clip_key and p["channel_id"] == channel_id
                   for p in self._data["posts"])

    def posts_for_asset(self, cloudinary_public_id) -> list[dict]:
        return [p for p in self._data["posts"]
                if p["cloudinary_public_id"] == cloudinary_public_id]

    def all_posts(self) -> list[dict]:
        return list(self._data["posts"])

    def set_state(self, post_id, state):
        for p in self._data["posts"]:
            if p["post_id"] == post_id:
                p["state"] = state

    def remove_asset(self, cloudinary_public_id):
        self._data["assets"].pop(cloudinary_public_id, None)

    @contextlib.contextmanager
    def _lock(self):
        lock_path = self.path.with_suffix(".lock")
        with lock_path.open("w") as lf:
            fcntl.flock(lf, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(lf, fcntl.LOCK_UN)

    def save(self):
        with self._lock():
            fd, tmp = tempfile.mkstemp(dir=str(self.path.parent), suffix=".tmp")
            try:
                with os.fdopen(fd, "w") as f:
                    json.dump(self._data, f, indent=2)
                os.replace(tmp, self.path)
            finally:
                if os.path.exists(tmp):
                    os.unlink(tmp)
