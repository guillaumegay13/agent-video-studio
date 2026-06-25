import pytest
from scripts.buffer_client import (
    BufferClient, BufferError, MutationError, CapabilityError,
)


class FakeResp:
    def __init__(self, payload, status=200):
        self._payload = payload
        self.status_code = status

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400 and self.status_code != 429:
            raise RuntimeError(f"HTTP {self.status_code}")


def make_client(responses):
    calls = {"n": 0}

    def fake_post(url, **kwargs):
        r = responses[calls["n"]]
        calls["n"] += 1
        return r
    return BufferClient(token="t", _post=fake_post), calls


def test_get_org_id():
    client, _ = make_client([
        FakeResp({"data": {"account": {"organizations": [{"id": "org1", "name": "X"}]}}}),
    ])
    assert client.get_org_id() == "org1"


def test_graphql_errors_raise_buffer_error():
    client, _ = make_client([FakeResp({"errors": [{"message": "bad auth"}]})])
    with pytest.raises(BufferError):
        client.get_org_id()


def test_create_post_success_returns_id():
    client, _ = make_client([
        FakeResp({"data": {"createPost": {"__typename": "PostActionSuccess",
                                           "post": {"id": "p1"}}}}),
    ])
    post_id = client.create_post(channel_id="c1", text="hi",
                                 video_url="https://x/c.mp4",
                                 thumbnail_url="https://x/c.jpg",
                                 due_at="2026-07-01T16:00:00Z",
                                 scheduling_type="automatic", metadata={})
    assert post_id == "p1"


def test_create_post_capability_error_raises_capability():
    client, _ = make_client([
        FakeResp({"data": {"createPost": {"__typename": "MutationError",
                  "message": "channel only supports notification publishing"}}}),
    ])
    with pytest.raises(CapabilityError):
        client.create_post(channel_id="c1", text="hi", video_url="https://x/c.mp4",
                           thumbnail_url=None, due_at="2026-07-01T16:00:00Z",
                           scheduling_type="automatic", metadata={})


def test_gql_retries_on_429_then_succeeds(monkeypatch):
    import scripts.buffer_client as bc
    monkeypatch.setattr(bc.time, "sleep", lambda *_: None)
    responses = [
        FakeResp({}, status=429),
        FakeResp({"data": {"account": {"organizations": [{"id": "org9", "name": "Z"}]}}}),
    ]
    client, calls = make_client(responses)
    assert client.get_org_id() == "org9"
    assert calls["n"] == 2  # retried once


def test_non_capability_mutation_error_raises_mutation_error():
    client, _ = make_client([
        FakeResp({"data": {"createPost": {"__typename": "MutationError",
                  "message": "duplicate post detected"}}}),
    ])
    with pytest.raises(MutationError) as exc:
        client.create_post(channel_id="c1", text="hi", video_url="https://x/c.mp4",
                           thumbnail_url=None, due_at="2026-07-01T16:00:00Z",
                           scheduling_type="automatic", metadata={})
    # must be the base MutationError, not the CapabilityError subclass
    assert not isinstance(exc.value, CapabilityError)
