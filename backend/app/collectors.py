"""Bounded public-API collectors. Events keep transport independent of persistence.

A coverage event describes the query/feed actually read, never global market coverage.
A rate-limit reset beyond the retry budget defers the rest of the run to the scheduler.
"""

from __future__ import annotations

import base64
import re
import time
from datetime import date, datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import Any, Iterator
from urllib.parse import urlparse

import httpx

GITHUB_API = "https://api.github.com"
HN_API = "https://hacker-news.firebaseio.com/v0"
DISCOVERY_QUERIES = (
    '"built with" "Claude Code" in:readme',
    '"built with" Cursor in:readme',
    '"built with" Lovable in:readme',
    '"vibe coded" in:readme',
    "topic:vibe-coded",
    "topic:vibe-coding",
)


class SourceError(RuntimeError):
    def __init__(
        self, message: str, *, status: int | None = None, deferred: bool = False
    ):
        super().__init__(message)
        self.status = status
        self.deferred = deferred


def _retry_delay(response: httpx.Response) -> float:
    value = response.headers.get("retry-after", "")
    if value:
        try:
            return max(0.0, float(value))
        except ValueError:
            try:
                return max(0.0, parsedate_to_datetime(value).timestamp() - time.time())
            except (TypeError, ValueError):
                pass
    try:
        return max(0.0, float(response.headers["x-ratelimit-reset"]) - time.time() + 1)
    except (KeyError, ValueError):
        return 2.0


class _Reader:
    def __init__(
        self, client: httpx.Client | None, headers: dict[str, str] | None = None
    ):
        self.client = client or httpx.Client(timeout=25, follow_redirects=True)
        self.owned_client = client is None
        self.headers = {
            "User-Agent": "VibeScope/0.1 (public-data observation)",
            **(headers or {}),
        }

    def close(self) -> None:
        if self.owned_client:
            self.client.close()

    def get(self, url: str, params: dict | None = None) -> Any:
        for attempt in range(3):
            try:
                response = self.client.get(url, params=params, headers=self.headers)
            except httpx.RequestError as exc:
                if attempt < 2:
                    time.sleep(0.25 * (attempt + 1))
                    continue
                raise SourceError(
                    f"Network request failed ({type(exc).__name__})"
                ) from None
            limited = response.status_code == 429 or (
                response.status_code == 403
                and (
                    response.headers.get("x-ratelimit-remaining") == "0"
                    or "retry-after" in response.headers
                    or "rate limit" in response.text.lower()
                )
            )
            if limited:
                delay = _retry_delay(response)
                if delay > 5 or attempt == 2:
                    raise SourceError(
                        "API rate limit; run deferred until a later schedule",
                        status=response.status_code,
                        deferred=True,
                    )
                time.sleep(max(0.25, delay))
                continue
            if response.status_code >= 500 and attempt < 2:
                time.sleep(0.25 * (attempt + 1))
                continue
            if response.status_code >= 400:
                raise SourceError(
                    f"API returned HTTP {response.status_code}",
                    status=response.status_code,
                )
            try:
                return response.json()
            except ValueError:
                raise SourceError("API returned invalid JSON") from None
        raise SourceError("Request retries exhausted")


def _raw(source: str, source_id: str | int, payload: Any) -> dict:
    return {
        "type": "raw",
        "source": source,
        "source_id": str(source_id),
        "payload": payload,
    }


def _coverage(source: str, status: str, **detail: Any) -> dict:
    return {"type": "coverage", "source": source, "status": status, "detail": detail}


def github_repo_from_url(url: str | None) -> str | None:
    """Only repository-root links, never issue paths or lookalike domains."""
    if not url:
        return None
    parsed = urlparse(url)
    if (
        parsed.scheme not in {"http", "https"}
        or (parsed.hostname or "").lower() != "github.com"
    ):
        return None
    match = re.fullmatch(r"/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)/?", parsed.path)
    if not match:
        return None
    owner, repo = match.groups()
    if repo.endswith(".git"):
        repo = repo[:-4]
    if not repo or owner.lower() in {
        "topics",
        "search",
        "features",
        "settings",
        "marketplace",
        "collections",
        "orgs",
        "users",
    }:
        return None
    return f"{owner}/{repo}".lower()


class GitHubCollector:
    def __init__(
        self, token: str = "", limit: int = 1000, client: httpx.Client | None = None
    ):
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if token:
            headers["Authorization"] = f"Bearer {token}"
        self.reader = _Reader(client, headers)
        self.limit = max(1, min(limit, 1000))
        self._seen: set[int] = set()
        self._partial = False
        self._errors = 0

    def _repository(self, repo: dict) -> Iterator[dict]:
        repo_id = int(repo["id"])
        if repo_id in self._seen:
            return
        self._seen.add(repo_id)
        full_name = repo["full_name"]
        yield _raw("github", repo_id, repo)
        readme = ""
        evidence_url = repo.get("html_url") or f"https://github.com/{full_name}"
        try:
            response = self.reader.get(f"{GITHUB_API}/repos/{full_name}/readme")
            yield _raw("github", f"{repo_id}:readme", response)
            if response.get("encoding") == "base64":
                readme = base64.b64decode(response.get("content", "")).decode(
                    "utf-8", errors="replace"
                )
            else:
                readme = response.get("content", "")
            evidence_url = response.get("html_url") or evidence_url
        except SourceError as exc:
            if exc.status != 404:
                self._partial = True
                self._errors += 1
                yield _coverage(
                    "github",
                    "partial",
                    repository=full_name,
                    stage="readme",
                    reason=str(exc),
                )
                if exc.deferred:
                    raise
                # Do not replace a previously complete record with incomplete content.
                return
        yield {
            "type": "repository",
            "data": {
                "id": repo_id,
                "name": repo.get("name", full_name.split("/")[-1]),
                "full_name": full_name,
                "description": repo.get("description") or "",
                "url": repo.get("html_url") or f"https://github.com/{full_name}",
                "homepage": repo.get("homepage") or None,
                "language": repo.get("language"),
                "stars": int(repo.get("stargazers_count", 0)),
                "forks": int(repo.get("forks_count", 0)),
                "created_at": repo.get("created_at"),
                "pushed_at": repo.get("pushed_at"),
                "readme": readme[:150_000],
                "evidence_url": evidence_url,
            },
        }

    def _search(self, query: str, field: str, start: date, end: date) -> Iterator[dict]:
        if len(self._seen) >= self.limit:
            return
        q = f"{query} {field}:{start.isoformat()}..{end.isoformat()} fork:false archived:false"
        payload = self.reader.get(
            f"{GITHUB_API}/search/repositories",
            {"q": q, "sort": "stars", "order": "desc", "per_page": 100, "page": 1},
        )
        yield _raw("github", f"search:{q}:1", payload)
        total = int(payload.get("total_count", 0))
        incomplete = bool(payload.get("incomplete_results"))
        if (total > 1000 or incomplete) and start < end:
            middle = start + timedelta(days=(end - start).days // 2)
            # A bounded sample must not be exhausted by the oldest partition.
            yield from self._search(query, field, middle + timedelta(days=1), end)
            yield from self._search(query, field, start, middle)
            return
        truncated = total > 1000 or incomplete
        if truncated:
            self._partial = True
        yield _coverage(
            "github",
            "partial" if truncated else "complete",
            query=q,
            total_count=total,
            incomplete_results=incomplete,
            search_result_limit=1000,
        )
        pages = min(10, max(1, (min(total, 1000) + 99) // 100))
        for page in range(1, pages + 1):
            if len(self._seen) >= self.limit:
                self._partial = True
                return
            if page > 1:
                payload = self.reader.get(
                    f"{GITHUB_API}/search/repositories",
                    {
                        "q": q,
                        "sort": "stars",
                        "order": "desc",
                        "per_page": 100,
                        "page": page,
                    },
                )
                yield _raw("github", f"search:{q}:{page}", payload)
                if payload.get("incomplete_results"):
                    self._partial = True
                    yield _coverage(
                        "github", "partial", query=q, page=page, incomplete_results=True
                    )
            items = payload.get("items", [])
            for repo in items:
                if len(self._seen) >= self.limit:
                    self._partial = True
                    return
                try:
                    yield from self._repository(repo)
                except (KeyError, TypeError, ValueError) as exc:
                    self._partial = True
                    self._errors += 1
                    yield _coverage(
                        "github",
                        "partial",
                        stage="normalize",
                        reason=type(exc).__name__,
                    )
            if len(items) < 100:
                break

    def iter_records(self, existing: list[dict], since: date) -> Iterator[dict]:
        self._seen, self._partial, self._errors = set(), False, 0
        try:
            # Known projects retain priority so discovery cannot starve daily snapshots.
            for item in sorted(existing, key=lambda x: int(x["id"]))[: self.limit]:
                try:
                    repo = self.reader.get(f"{GITHUB_API}/repos/{item['full_name']}")
                    yield from self._repository(repo)
                except SourceError as exc:
                    self._partial = True
                    self._errors += 1
                    yield _coverage(
                        "github",
                        "partial",
                        repository=item.get("full_name"),
                        stage="refresh",
                        reason=str(exc),
                    )
                    if exc.deferred:
                        raise
                except (KeyError, TypeError, ValueError) as exc:
                    self._partial = True
                    self._errors += 1
                    yield _coverage(
                        "github",
                        "partial",
                        repository=item.get("full_name"),
                        reason=type(exc).__name__,
                    )
            today = datetime.now(timezone.utc).date()
            for query in DISCOVERY_QUERIES:
                for field in ("created", "pushed"):
                    if len(self._seen) >= self.limit:
                        self._partial = True
                        break
                    try:
                        yield from self._search(query, field, since, today)
                    except SourceError as exc:
                        self._partial = True
                        self._errors += 1
                        yield _coverage(
                            "github",
                            "partial",
                            query=query,
                            field=field,
                            reason=str(exc),
                        )
                        if exc.deferred:
                            raise
        except SourceError as exc:
            self._partial = True
            yield _coverage(
                "github",
                "partial" if self._seen else "failed",
                deferred=exc.deferred,
                reason=str(exc),
            )
        finally:
            self.reader.close()
        yield _coverage(
            "github",
            "partial" if self._partial else "complete",
            stage="summary",
            attempted_repositories=len(self._seen),
            errors=self._errors,
            tracking_limit=self.limit,
            since=since.isoformat(),
            limit_reached=len(self._seen) >= self.limit,
            sampling_policy="author-declaration queries first; newest date partition first; stars descending within partition",
        )


class HNCollector:
    def __init__(
        self, client: httpx.Client | None = None, max_items: int | None = None
    ):
        self.reader = _Reader(client)
        self.max_items = max(1, max_items) if max_items is not None else None

    def iter_records(self, existing_ids: list[int] | None = None) -> Iterator[dict]:
        seen: set[int] = set()
        ids = list(dict.fromkeys(existing_ids or []))
        partial = False
        errors = 0
        oldest: str | None = None
        try:
            for feed, maximum in (("newstories", 500), ("showstories", 200)):
                try:
                    payload = self.reader.get(f"{HN_API}/{feed}.json")
                    if not isinstance(payload, list):
                        raise SourceError("Feed did not return an ID array")
                    yield _raw("hn", feed, payload)
                    ids.extend(payload[:maximum])
                    yield _coverage(
                        "hn",
                        "complete",
                        feed=feed,
                        listed=len(payload[:maximum]),
                        maximum=maximum,
                        scope="latest feed only; no historical completeness claim",
                    )
                except SourceError as exc:
                    partial = True
                    errors += 1
                    yield _coverage("hn", "partial", feed=feed, reason=str(exc))
                    if exc.deferred:
                        raise
            for item_id in ids:
                if self.max_items is not None and len(seen) >= self.max_items:
                    partial = True
                    yield _coverage(
                        "hn",
                        "partial",
                        stage="sample_limit",
                        max_items=self.max_items,
                        reason="Explicit small-sample collection limit reached",
                    )
                    break
                if not isinstance(item_id, int) or item_id in seen:
                    continue
                seen.add(item_id)
                try:
                    item = self.reader.get(f"{HN_API}/item/{item_id}.json")
                    yield _raw("hn", item_id, item)
                    if (
                        not isinstance(item, dict)
                        or item.get("deleted")
                        or item.get("dead")
                        or item.get("type") != "story"
                    ):
                        continue
                    posted = datetime.fromtimestamp(
                        item["time"], timezone.utc
                    ).isoformat()
                    oldest = min(oldest, posted) if oldest else posted
                    yield {
                        "type": "discussion",
                        "data": {
                            "id": int(item["id"]),
                            "title": item.get("title") or "Untitled",
                            "url": item.get("url")
                            or f"https://news.ycombinator.com/item?id={item_id}",
                            "repo_full_name": github_repo_from_url(item.get("url")),
                            "score": int(item.get("score", 0)),
                            "comments": int(item.get("descendants", 0)),
                            "posted_at": posted,
                        },
                    }
                except SourceError as exc:
                    partial = True
                    errors += 1
                    yield _coverage("hn", "partial", item_id=item_id, reason=str(exc))
                    if exc.deferred:
                        raise
                except (KeyError, TypeError, ValueError, OverflowError) as exc:
                    partial = True
                    errors += 1
                    yield _coverage(
                        "hn", "partial", item_id=item_id, reason=type(exc).__name__
                    )
        except SourceError as exc:
            partial = True
            yield _coverage(
                "hn",
                "partial" if seen else "failed",
                deferred=exc.deferred,
                reason=str(exc),
            )
        finally:
            self.reader.close()
        yield _coverage(
            "hn",
            "partial" if partial else "complete",
            stage="summary",
            attempted_items=len(seen),
            errors=errors,
            oldest_posted_at=oldest,
            scope="latest feeds plus previously tracked stories",
        )
