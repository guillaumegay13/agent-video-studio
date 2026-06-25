"""Discover rendered clips and map each to its source metadata JSON."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

CLIP_INDEX_RE = re.compile(r"clip_(\d+)_")


class ClipMappingError(Exception):
    pass


@dataclass
class Clip:
    index: int
    video_path: Path
    metadata: dict


def _clip_index(name: str) -> int | None:
    m = CLIP_INDEX_RE.search(name)
    return int(m.group(1)) if m else None


def _newest_metadata(directory: Path, index: int) -> dict:
    candidates = sorted(
        directory.glob(f"clip_{index}_score_*.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not candidates:
        raise ClipMappingError(
            f"No metadata JSON (clip_{index}_score_*.json) found for clip index {index} "
            f"in {directory}"
        )
    return json.loads(candidates[0].read_text())


def discover_clips(directory: Path) -> list[Clip]:
    """Return publishable clips. Prefers *_final_subtitled.mp4; falls back to raw
    score clips only when no subtitled variant exists for that index."""
    directory = Path(directory)
    subtitled = sorted(directory.glob("clip_*_final_subtitled.mp4"))
    by_index: dict[int, Path] = {}
    for path in subtitled:
        idx = _clip_index(path.name)
        if idx is not None:
            by_index[idx] = path

    # Fall back to raw score clips for indices with no subtitled variant.
    for path in sorted(directory.glob("clip_*_score_*.mp4")):
        idx = _clip_index(path.name)
        if idx is not None and idx not in by_index:
            by_index[idx] = path

    clips: list[Clip] = []
    for idx in sorted(by_index):
        clips.append(Clip(index=idx, video_path=by_index[idx],
                          metadata=_newest_metadata(directory, idx)))
    if not clips:
        raise ClipMappingError(f"No clips found in {directory}")
    return clips
