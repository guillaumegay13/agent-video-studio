"""Minimal Buffer GraphQL client for the publish skill.

Endpoint: https://api.buffer.com  (Authorization: Bearer <token>)
Distinguishes three failure classes:
  - BufferError:     top-level GraphQL `errors` (auth, malformed query)
  - MutationError:   inline business error from the createPost union
  - CapabilityError: a MutationError that signals reminder-only publishing
"""
from __future__ import annotations

import time

ENDPOINT = "https://api.buffer.com"
CAP_HINTS = ("notification", "reminder", "reminders", "manual posting",
             "manual publishing", "does not support automatic")


class BufferError(Exception):
    pass


class MutationError(Exception):
    pass


class CapabilityError(MutationError):
    pass


class BufferClient:
    def __init__(self, token: str, _post=None):
        self.token = token
        if _post is None:
            import requests
            self._post = lambda url, **kw: requests.post(url, **kw)
        else:
            self._post = _post

    def _gql(self, query: str, variables: dict | None = None) -> dict:
        for attempt in range(4):
            resp = self._post(
                ENDPOINT,
                headers={"Authorization": f"Bearer {self.token}",
                         "Content-Type": "application/json"},
                json={"query": query, "variables": variables or {}},
                timeout=60,
            )
            if getattr(resp, "status_code", 200) == 429:
                time.sleep(2 ** attempt)
                continue
            resp.raise_for_status()
            payload = resp.json()
            if payload.get("errors"):
                msg = "; ".join(e.get("message", "?") for e in payload["errors"])
                raise BufferError(msg)
            return payload["data"]
        raise BufferError("rate limited after retries")

    def get_org_id(self) -> str:
        data = self._gql("query { account { organizations { id name } } }")
        orgs = data["account"]["organizations"]
        if not orgs:
            raise BufferError("no organizations on this account")
        return orgs[0]["id"]

    def list_channels(self, org_id: str) -> list[dict]:
        data = self._gql(
            "query($i: ChannelsInput!){ channels(input:$i){ id service name "
            "displayName isDisconnected isLocked isQueuePaused } }",
            {"i": {"organizationId": org_id}},
        )
        return data["channels"]

    def list_scheduled_due_ats(self, org_id: str, channel_id: str) -> list[str]:
        """Return dueAt strings of scheduled/sending posts for a channel
        (the scheduling source of truth). Verified live: channelIds/status live
        under PostsInput.filter, and posts() returns {edges:[{node:Post}]}."""
        data = self._gql(
            "query($i: PostsInput!){ posts(input:$i, first:100){ "
            "edges{ node{ id dueAt status } } } }",
            {"i": {"organizationId": org_id,
                   "filter": {"channelIds": [channel_id]}}},
        )
        edges = data.get("posts", {}).get("edges", [])
        return [e["node"]["dueAt"] for e in edges
                if e["node"].get("status") in ("scheduled", "sending")
                and e["node"].get("dueAt")]

    def post_status(self, post_id: str) -> str:
        data = self._gql(
            "query($i: PostInput!){ post(input:$i){ id status } }",
            {"i": {"id": post_id}},
        )
        return data["post"]["status"]

    def create_post(self, channel_id, text, video_url, thumbnail_url, due_at,
                    scheduling_type, metadata) -> str:
        video_asset: dict = {"url": video_url}
        if thumbnail_url:
            video_asset["thumbnailUrl"] = thumbnail_url
        variables = {"input": {
            "channelId": channel_id,
            "schedulingType": scheduling_type,
            "mode": "customScheduled",
            "dueAt": due_at,
            "text": text,
            "assets": [{"video": video_asset}],
            "metadata": metadata or {},
        }}
        data = self._gql(
            "mutation($input: CreatePostInput!){ createPost(input:$input){ "
            "__typename ... on PostActionSuccess { post { id } } "
            "... on MutationError { message } } }",
            variables,
        )
        result = data["createPost"]
        if result.get("__typename") == "PostActionSuccess":
            return result["post"]["id"]
        message = result.get("message", "unknown mutation error")
        if any(h in message.lower() for h in CAP_HINTS):
            raise CapabilityError(message)
        raise MutationError(message)
