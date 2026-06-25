"""Status-driven Cloudinary cleanup.

Delete an asset only when EVERY post sharing its cloudinary_public_id is `sent`.
Assets with any post still scheduled/sending, or in `error`, are retained."""
from __future__ import annotations

from scripts import media_host


def _safe_status(buffer, post_id) -> str:
    try:
        return buffer.post_status(post_id) or "unknown"
    except Exception:
        return "unknown"


def run_cleanup(buffer, ledger, cfg) -> dict:
    deleted, retained = 0, 0
    seen_assets = {p["cloudinary_public_id"] for p in ledger.all_posts()
                   if p["cloudinary_public_id"]}
    for public_id in seen_assets:
        rows = ledger.posts_for_asset(public_id)
        statuses = [_safe_status(buffer, r["post_id"]) for r in rows]
        if rows and all(s == "sent" for s in statuses):
            if media_host.destroy_clip(public_id, cfg):
                for r in rows:
                    ledger.set_state(r["post_id"], "cleaned")
                ledger.remove_asset(public_id)
                deleted += 1
        else:
            retained += 1
    ledger.save()
    return {"deleted": deleted, "retained": retained}
