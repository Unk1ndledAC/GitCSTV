"""Fetch public GitHub data for a user via the REST API."""

import json
import os
import urllib.error
import urllib.request
from collections import Counter
from datetime import datetime, timezone


def _api_headers(token: str | None) -> dict:
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "gitcstv-card-generator",
    }
    if token:
        headers["Authorization"] = f"token {token}"
    return headers


def _fetch_json(url: str, token: str | None) -> dict | list:
    req = urllib.request.Request(url, headers=_api_headers(token))
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _fetch_paginated(url: str, token: str | None, max_pages: int = 5) -> list:
    """Fetch all pages of a paginated GitHub API endpoint."""
    results = []
    page = 1
    while page <= max_pages:
        paginated_url = f"{url}?per_page=100&page={page}&sort=pushed"
        data = _fetch_json(paginated_url, token)
        if not data:
            break
        results.extend(data)
        if len(data) < 100:
            break
        page += 1
    return results


def _analyze_events(events: list) -> dict:
    """Extract activity patterns from the user's recent public events."""
    by_type = Counter(e.get("type") for e in events)
    unique_repos = len({e.get("repo", {}).get("name") for e in events})

    return {
        "total_events": len(events),
        "push_count": by_type.get("PushEvent", 0),
        "pr_count": by_type.get("PullRequestEvent", 0),
        "create_count": by_type.get("CreateEvent", 0),
        "issue_count": by_type.get("IssuesEvent", 0),
        "watch_count": by_type.get("WatchEvent", 0),
        "fork_count": by_type.get("ForkEvent", 0),
        "unique_event_repos": unique_repos,
    }


def _analyze_repos(repos: list) -> dict:
    """Compute rich repo-level statistics from the user's public repositories."""
    if not repos:
        return {
            "total": 0, "total_stars": 0, "total_forks": 0,
            "max_stars": 0, "avg_stars": 0,
            "with_stars": 0, "star_50": 0, "star_100": 0, "star_500": 0, "star_1000": 0,
            "languages": [], "top_language": "",
            "language_count": 0,
            "top_repos": [], "recent_topics": [],
        }

    # Stars
    starred_repos = [r for r in repos if (r.get("stargazers_count") or 0) > 0]
    total_stars = sum(r.get("stargazers_count", 0) or 0 for r in repos)
    total_forks = sum(r.get("forks_count", 0) or 0 for r in repos)
    max_stars = max((r.get("stargazers_count", 0) or 0 for r in repos), default=0)
    n = len(repos)
    avg_stars = total_stars / n if n > 0 else 0

    # Star brackets (for award determination)
    star_50 = len([r for r in repos if (r.get("stargazers_count") or 0) >= 50])
    star_100 = len([r for r in repos if (r.get("stargazers_count") or 0) >= 100])
    star_500 = len([r for r in repos if (r.get("stargazers_count") or 0) >= 500])
    star_1000 = len([r for r in repos if (r.get("stargazers_count") or 0) >= 1000])

    # Languages
    lang_counter = Counter(r.get("language") for r in repos if r.get("language"))
    languages = [lang for lang, _ in lang_counter.most_common()]
    top_language = languages[0] if languages else ""
    language_count = len(languages)

    # Topics
    all_topics = []
    for r in repos:
        topics = r.get("topics") or []
        all_topics.extend(topics)
    topic_counter = Counter(all_topics)
    recent_topics = [t for t, _ in topic_counter.most_common(6)]

    # Top repos by stars
    sorted_repos = sorted(repos, key=lambda r: r.get("stargazers_count", 0) or 0, reverse=True)
    top_repos = [
        {
            "name": r.get("name", ""),
            "stars": r.get("stargazers_count", 0) or 0,
            "forks": r.get("forks_count", 0) or 0,
            "language": r.get("language") or "",
            "description": r.get("description") or "",
            "topics": r.get("topics") or [],
        }
        for r in sorted_repos[:5]
    ]

    return {
        "total": n,
        "total_stars": total_stars,
        "total_forks": total_forks,
        "max_stars": max_stars,
        "avg_stars": avg_stars,
        "with_stars": len(starred_repos),
        "star_50": star_50,
        "star_100": star_100,
        "star_500": star_500,
        "star_1000": star_1000,
        "languages": languages,
        "top_language": top_language,
        "language_count": language_count,
        "top_repos": top_repos,
        "recent_topics": recent_topics,
    }


def fetch_github_data(username: str, token: str | None = None) -> dict:
    """Return a user's public profile, repo stats, and event activity.

    This is the main entry point. It calls three GitHub API endpoints:
      - /users/{username}
      - /users/{username}/repos (paginated, up to 500)
      - /users/{username}/events/public (paginated, up to 300)
    """
    base = "https://api.github.com"

    profile = _fetch_json(f"{base}/users/{username}", token)
    repos = _fetch_paginated(f"{base}/users/{username}/repos", token, max_pages=5)
    events = _fetch_paginated(f"{base}/users/{username}/events/public", token, max_pages=3)

    created_at = datetime.fromisoformat(profile["created_at"].replace("Z", "+00:00"))
    account_age_days = (datetime.now(timezone.utc) - created_at).days

    avatar_url = profile.get("avatar_url", "")
    if avatar_url:
        avatar_url = avatar_url.split("?")[0] + "?s=400"

    repo_stats = _analyze_repos(repos)
    event_stats = _analyze_events(events)

    return {
        "login": profile.get("login", username),
        "name": profile.get("name") or username,
        "avatar_url": avatar_url,
        "location": profile.get("location") or "",
        "bio": profile.get("bio") or "",
        "company": profile.get("company") or "",
        "public_repos": profile.get("public_repos", 0) or 0,
        "public_gists": profile.get("public_gists", 0) or 0,
        "followers": profile.get("followers", 0) or 0,
        "following": profile.get("following", 0) or 0,
        "created_at": profile.get("created_at", ""),
        "account_age_days": account_age_days,
        "repos": repo_stats,
        "events": event_stats,
    }
