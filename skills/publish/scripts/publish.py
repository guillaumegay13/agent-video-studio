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


def build_metadata(service, caption):
    """Map a Caption to Buffer per-platform metadata for one service."""
    if service == "youtube":
        return {"youtube": {"title": caption.youtube_title, "privacy": "public",
                            "madeForKids": False}}
    if service == "tiktok":
        return {"tiktok": {"title": caption.tiktok_title}}
    if service == "instagram":
        return {"instagram": {"type": "reel", "shouldShareToFeed": True}}
    return {}
