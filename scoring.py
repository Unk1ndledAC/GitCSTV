"""GitFut-style scoring engine — map GitHub data to CS-style metrics.

Each of the six scoring dimensions (Firepower, Starpower, Longevity,
Impact, Collaboration, Versatility) produces a 0–100 score derived from
log-scaled GitHub metrics. The overall Rating is a weighted composite
mapped to the 0.80–1.30 range typical of HLTV player ratings.
"""

import math


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def _log_scale(x: float, base: float = 10, divisor: float = 5) -> float:
    """Log-scaled normalization to [0, 1]."""
    if x <= 0:
        return 0.0
    return _clamp(math.log(x + 1, base) / divisor, 0.0, 1.0)


# ---------------------------------------------------------------------------
# Scoring dimensions — each returns 0–100
# ---------------------------------------------------------------------------

def _score_firepower(repos: dict, events: dict) -> float:
    """Raw code output & productivity."""
    s1 = _log_scale(events["create_count"], divisor=4)
    s2 = _log_scale(events["push_count"], divisor=5)
    s3 = _log_scale(repos["total"], divisor=3)
    return _clamp(30 + 70 * (s1 * 0.3 + s2 * 0.4 + s3 * 0.3), 0, 100)


def _score_starpower(repos: dict) -> float:
    """Star impact & project popularity."""
    s1 = _log_scale(repos["avg_stars"], divisor=8)
    s2 = _log_scale(repos["max_stars"], divisor=8)
    s3 = _log_scale(repos["total_stars"], divisor=8)
    return _clamp(30 + 70 * (s1 * 0.35 + s2 * 0.35 + s3 * 0.30), 0, 100)


def _score_longevity(data: dict, repos: dict) -> float:
    """Account & project staying power."""
    age_years = data["account_age_days"] / 365.25
    age_s = _clamp(age_years / 12.0, 0.0, 1.0)
    maintenance_s = _clamp(repos["with_stars"] / max(repos["total"], 1), 0.0, 1.0)
    return _clamp(20 + 80 * (age_s * 0.5 + maintenance_s * 0.5), 0, 100)


def _score_impact(data: dict, repos: dict, events: dict) -> float:
    """Community reach & influence."""
    s1 = _log_scale(data["followers"], divisor=6)
    s2 = _log_scale(repos["total_forks"], divisor=6)
    s3 = _log_scale(events["watch_count"], divisor=4)
    s4 = _log_scale(events["pr_count"], divisor=4)
    return _clamp(20 + 80 * (s1 * 0.35 + s2 * 0.30 + s3 * 0.15 + s4 * 0.20), 0, 100)


def _score_collaboration(data: dict, repos: dict, events: dict) -> float:
    """Open-source collaboration."""
    s1 = _log_scale(repos["language_count"], divisor=3)
    s2 = _log_scale(events["pr_count"], divisor=4)
    s3 = _log_scale(events["issue_count"], divisor=4)
    s4 = _log_scale(repos["total_forks"], divisor=5)
    s5 = _log_scale(data["following"], divisor=4)
    return _clamp(15 + 85 * (s1 * 0.25 + s2 * 0.25 + s3 * 0.20 + s4 * 0.15 + s5 * 0.15), 0, 100)


def _score_versatility(repos: dict) -> float:
    """Technology range & breadth."""
    s1 = _log_scale(repos["language_count"], divisor=3)
    s2 = _log_scale(len(repos.get("recent_topics", [])), divisor=3)
    s3 = _log_scale(repos["total"], divisor=3)
    return _clamp(10 + 90 * (s1 * 0.4 + s2 * 0.35 + s3 * 0.25), 0, 100)


# ---------------------------------------------------------------------------
# Awards & achievements
# ---------------------------------------------------------------------------

def _compute_awards(repos: dict) -> dict:
    """Determine MVP/EVP awards from repo star brackets.

    MVP  — repos with >= 1000 stars (major tournament wins)
    EVP  — repos with >= 100 stars  (valuable player performances)
    """
    mvps = []
    evps = []
    top = repos.get("top_repos", [])

    for r in top:
        if r["stars"] >= 1000:
            mvps.append(r["name"])
        elif r["stars"] >= 100:
            evps.append(r["name"])

    return {
        "mvp": mvps[:4],
        "evp": evps[:4],
        "star_1000": repos["star_1000"],
        "star_500": repos["star_500"],
        "star_100": repos["star_100"],
        "star_50": repos["star_50"],
    }


def _compute_events(repos: dict) -> list:
    """Convert top repos into 'tournament placings' with star counts."""
    top = repos.get("top_repos", [])
    events = []
    for i, r in enumerate(top[:4]):
        place = ["1st", "2nd", "3rd"][i] if i < 3 else f"{i+1}th"
        stars_str = f"{r['stars']:,}"
        lang = f"({r['language']})" if r["language"] else ""
        events.append(f"{place} {r['name']} {stars_str} {lang}")
    return events


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_stats(data: dict) -> dict:
    """Compute all CS-style stats, awards, and events from raw GitHub data.

    Returns a dict with:
      - firepower, starpower, longevity, impact_score, collaboration, versatility (0–100)
      - rating (0.80–1.30, HLTV-style composite)
      - awards (MVP/EVP lists)
      - events (top repo placings)
    """
    repos = data["repos"]
    events = data["events"]

    firepower = _score_firepower(repos, events)
    longevity = _score_longevity(data, repos)
    starpower = _score_starpower(repos)
    impact = _score_impact(data, repos, events)
    collaboration = _score_collaboration(data, repos, events)
    versatility = _score_versatility(repos)

    # Overall rating: weighted composite scaled to 0.80–1.30
    composite = (
        firepower * 0.20
        + longevity * 0.15
        + starpower * 0.30
        + impact * 0.20
        + collaboration * 0.10
        + versatility * 0.05
    )
    rating = _clamp(0.80 + composite * 0.005, 0.80, 1.30)

    awards = _compute_awards(repos)
    event_list = _compute_events(repos)

    return {
        "firepower": round(firepower),
        "longevity": round(longevity),
        "starpower": round(starpower),
        "impact_score": round(impact),
        "collaboration": round(collaboration),
        "versatility": round(versatility),
        "rating": round(rating, 2),
        "awards": awards,
        "events": event_list,
    }


def overall_rank(rating: float) -> int:
    """Map a Rating (0.80–1.30) to an HLTV-style top-20 rank."""
    if rating >= 1.27:  return 1
    if rating >= 1.24:  return 2
    if rating >= 1.21:  return 3
    if rating >= 1.18:  return 4
    if rating >= 1.15:  return 5
    if rating >= 1.13:  return 6
    if rating >= 1.11:  return 7
    if rating >= 1.09:  return 9
    if rating >= 1.07:  return 11
    if rating >= 1.05:  return 13
    return 15
