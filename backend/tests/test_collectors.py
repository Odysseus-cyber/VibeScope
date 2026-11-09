import base64
from datetime import date, timedelta

import httpx
import pytest

from app import collectors
from app.collectors import GitHubCollector, HNCollector, github_repo_from_url


def repo(number=1):
    return {
        "id": number,
        "name": f"app-{number}",
        "full_name": f"maker/app-{number}",
        "description": "Task application",
        "html_url": f"https://github.com/maker/app-{number}",
        "stargazers_count": 50,
        "forks_count": 3,
        "created_at": "2026-10-01T00:00:00Z",
        "pushed_at": "2026-11-01T00:00:00Z",
        "language": "Python",
    }


def readme():
    return {
        "encoding": "base64",
        "content": base64.b64encode(b"Built with Claude Code.").decode(),
        "html_url": "https://github.com/maker/app-1/blob/main/README.md",
    }


def test_refresh_then_discovery_are_deduplicated(monkeypatch):
    monkeypatch.setattr(collectors, "DISCOVERY_QUERIES", ("topic:vibe-coded",))
    paths = []

    def handler(request):
        paths.append(request.url.path)
        if request.url.path.endswith("/readme"):
            return httpx.Response(200, json=readme())
        if request.url.path.endswith("/search/repositories"):
            return httpx.Response(
                200,
                json={
                    "total_count": 2,
                    "items": [repo(1), repo(2)],
                    "incomplete_results": False,
                },
            )
        return httpx.Response(200, json=repo(1))

    events = list(
        GitHubCollector(
            client=httpx.Client(transport=httpx.MockTransport(handler))
        ).iter_records([{"id": 1, "full_name": "maker/app-1"}], date(2026, 10, 1))
    )
    records = [e["data"] for e in events if e["type"] == "repository"]
    assert paths[0] == "/repos/maker/app-1"
    assert [r["id"] for r in records] == [1, 2]
    assert records[0]["readme"] == "Built with Claude Code."
    assert records[0]["stars"] == 50
    assert any(e["type"] == "raw" for e in events)


def test_search_fetches_next_page_and_records_incomplete(monkeypatch):
    monkeypatch.setattr(collectors, "DISCOVERY_QUERIES", ("topic:vibe-coded",))
    pages = []

    def handler(request):
        if request.url.path.endswith("/readme"):
            return httpx.Response(404, json={})
        page = int(request.url.params["page"])
        pages.append(page)
        items = [repo(i) for i in range(1, 101)] if page == 1 else [repo(101)]
        return httpx.Response(
            200, json={"total_count": 101, "items": items, "incomplete_results": False}
        )

    events = list(
        GitHubCollector(
            limit=150, client=httpx.Client(transport=httpx.MockTransport(handler))
        ).iter_records([], date.today())
    )
    assert 2 in pages
    assert len([e for e in events if e["type"] == "repository"]) == 101


def test_oversized_search_splits_date_ranges(monkeypatch):
    monkeypatch.setattr(collectors, "DISCOVERY_QUERIES", ("topic:vibe-coded",))
    queries = []
    today = date.today()
    start = today - timedelta(days=1)

    def handler(request):
        q = request.url.params["q"]
        queries.append(q)
        broad = f"{start}..{today}" in q
        return httpx.Response(
            200,
            json={
                "total_count": 1001 if broad else 0,
                "incomplete_results": False,
                "items": [],
            },
        )

    events = list(
        GitHubCollector(
            client=httpx.Client(transport=httpx.MockTransport(handler))
        ).iter_records([], start)
    )
    assert any(f"{start}..{start}" in q for q in queries)
    assert any(f"{today}..{today}" in q for q in queries)
    assert events[-1]["status"] == "complete"


def test_rate_limit_defers_without_hammering_or_exposing_token():
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(
            429, json={"message": "too many"}, headers={"retry-after": "120"}
        )

    events = list(
        GitHubCollector(
            token="secret-test",
            client=httpx.Client(transport=httpx.MockTransport(handler)),
        ).iter_records([], date.today())
    )
    assert len(requests) == 1
    assert any(e.get("detail", {}).get("deferred") for e in events)
    assert events[-1]["status"] == "partial"
    assert "secret-test" not in str(events)


def test_bounded_transient_retry(monkeypatch):
    monkeypatch.setattr(collectors.time, "sleep", lambda _: None)
    count = 0

    def handler(request):
        nonlocal count
        count += 1
        return httpx.Response(503 if count < 3 else 200, json={"ok": True})

    reader = collectors._Reader(httpx.Client(transport=httpx.MockTransport(handler)))
    assert reader.get("https://example.test") == {"ok": True}
    assert count == 3


def test_one_bad_repository_does_not_lose_other_projects(monkeypatch):
    monkeypatch.setattr(collectors, "DISCOVERY_QUERIES", ())

    def handler(request):
        if "/app-1" in request.url.path:
            return httpx.Response(404, json={})
        if request.url.path.endswith("/readme"):
            return httpx.Response(404, json={})
        return httpx.Response(200, json=repo(2))

    events = list(
        GitHubCollector(
            client=httpx.Client(transport=httpx.MockTransport(handler))
        ).iter_records(
            [
                {"id": 1, "full_name": "maker/app-1"},
                {"id": 2, "full_name": "maker/app-2"},
            ],
            date.today(),
        )
    )
    assert [e["data"]["id"] for e in events if e["type"] == "repository"] == [2]
    assert events[-1]["status"] == "partial"


@pytest.mark.parametrize(
    "url,expected",
    [
        ("https://github.com/Maker/App.git?utm=hn", "maker/app"),
        ("https://github.com/maker/app/", "maker/app"),
        ("https://github.com/maker/app/issues/1", None),
        ("https://github.com.evil.test/maker/app", None),
        ("https://github.com/topics/ai", None),
        ("https://example.com/maker/app", None),
        ("javascript:alert(1)", None),
    ],
)
def test_exact_repository_url_association(url, expected):
    assert github_repo_from_url(url) == expected


def test_hn_deduplicates_feeds_and_refreshes_existing():
    calls = []

    def handler(request):
        calls.append(request.url.path)
        if request.url.path.endswith("newstories.json"):
            return httpx.Response(200, json=[1, 2])
        if request.url.path.endswith("showstories.json"):
            return httpx.Response(200, json=[2, 3])
        item_id = int(request.url.path.split("/")[-1].replace(".json", ""))
        if item_id == 3:
            return httpx.Response(200, json={"id": 3, "deleted": True})
        return httpx.Response(
            200,
            json={
                "id": item_id,
                "type": "story",
                "title": "Show HN: App",
                "time": 1700000000,
                "url": (
                    "https://github.com/maker/app"
                    if item_id == 1
                    else "https://example.com"
                ),
                "score": 12,
                "descendants": 5,
            },
        )

    events = list(
        HNCollector(
            client=httpx.Client(transport=httpx.MockTransport(handler))
        ).iter_records([2])
    )
    discussions = [e["data"] for e in events if e["type"] == "discussion"]
    assert [d["id"] for d in discussions] == [2, 1]
    assert discussions[0]["repo_full_name"] is None
    assert discussions[1]["repo_full_name"] == "maker/app"
    assert calls.count("/v0/item/2.json") == 1
    assert events[-1]["status"] == "complete"


def test_sample_limit_prefers_newest_date_partition(monkeypatch):
    monkeypatch.setattr(collectors, "DISCOVERY_QUERIES", ("topic:vibe-coded",))
    today = date.today()
    yesterday = today - timedelta(days=1)
    searched = []

    def handler(request):
        if request.url.path.endswith("/readme"):
            return httpx.Response(200, json=readme())
        q = request.url.params["q"]
        searched.append(q)
        if f"{yesterday}..{today}" in q:
            return httpx.Response(
                200,
                json={"total_count": 1001, "items": [], "incomplete_results": False},
            )
        item = repo(2 if f"{today}..{today}" in q else 1)
        return httpx.Response(
            200, json={"total_count": 1, "items": [item], "incomplete_results": False}
        )

    events = list(
        GitHubCollector(
            limit=1, client=httpx.Client(transport=httpx.MockTransport(handler))
        ).iter_records([], yesterday)
    )
    assert [e["data"]["id"] for e in events if e["type"] == "repository"] == [2]
    assert f"{today}..{today}" in searched[1]
    assert events[-1]["detail"]["limit_reached"] is True
    assert "newest date partition first" in events[-1]["detail"]["sampling_policy"]


def test_hn_explicit_sample_limit_records_partial_coverage():
    def handler(request):
        if request.url.path.endswith("stories.json"):
            return httpx.Response(200, json=[1, 2, 3])
        item_id = int(request.url.path.rsplit("/", 1)[1].split(".")[0])
        return httpx.Response(
            200,
            json={"id": item_id, "type": "story", "time": 1700000000, "title": "App"},
        )

    events = list(
        HNCollector(
            client=httpx.Client(transport=httpx.MockTransport(handler)), max_items=1
        ).iter_records()
    )
    assert len([e for e in events if e["type"] == "discussion"]) == 1
    assert any(e.get("detail", {}).get("stage") == "sample_limit" for e in events)
