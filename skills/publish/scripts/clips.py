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


def _subtitled_rank(name: str) -> int:
    """Prefer the standard subtitled render over layout variants like *_seam_*."""
    if "_final_" in name:
        return 0
    if "_score_" in name:
        return 1
    return 2  # e.g. *_seam_subtitled.mp4 — last resort


def _newest_metadata(directory: Path, index: int) -> dict:
    # Match both naming schemes the pipeline has emitted: `clip_<N>_score_*.json`
    # and `viral_clip_<N>_score_*.json`. The leading `*` covers the `viral_` prefix.
    candidates = sorted(
        directory.glob(f"*clip_{index}_score_*.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not candidates:
        raise ClipMappingError(
            f"No metadata JSON (*clip_{index}_score_*.json) found for clip index "
            f"{index} in {directory}"
        )
    return json.loads(candidates[0].read_text())


def discover_clips(directory: Path) -> list[Clip]:
    """Return publishable clips, mapping each to its source metadata JSON by the
    `clip_<N>` index prefix.

    Handles both pipeline naming schemes: `clip_<N>_final_subtitled.mp4` and
    `viral_clip_<N>_score_<s>_subtitled.mp4`. Prefers a subtitled render; within an
    index prefers `_final_`/`_score_` over layout variants (`_seam_`); falls back to
    the raw score clip only when no subtitled variant exists for that index."""
    directory = Path(directory)
    by_index: dict[int, Path] = {}

    # Subtitled finals (any scheme). Group by index, pick the best-ranked variant.
    grouped: dict[int, list[Path]] = {}
    for path in sorted(directory.glob("*_subtitled.mp4")):
        idx = _clip_index(path.name)
        if idx is not None:
            grouped.setdefault(idx, []).append(path)
    for idx, paths in grouped.items():
        paths.sort(key=lambda p: (_subtitled_rank(p.name), p.name))
        by_index[idx] = paths[0]

    # Fall back to raw (non-subtitled) score clips for indices with no subtitled.
    for path in sorted(directory.glob("*_score_*.mp4")):
        if path.name.endswith("_subtitled.mp4"):
            continue
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
