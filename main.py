#!/usr/bin/env python3
"""
gitcstv — generate HLTV-style CS player cards from GitHub data.

Usage:
    python main.py <github_username>
    python main.py --demo

Examples:
    python main.py torvalds
    python main.py --demo -o demo_card.png
"""

import argparse
import os
import sys

from github_client import fetch_github_data
from scoring import build_stats, overall_rank
from card_generator import generate_card


def _sample_data() -> dict:
    """Mock GitHub data for offline demo / CI testing."""
    return {
        "login": "torvalds",
        "name": "Linus Torvalds",
        "avatar_url": "",
        "location": "Portland, OR",
        "bio": "Creator of Linux and Git",
        "company": "Linux Foundation",
        "public_repos": 8,
        "public_gists": 0,
        "followers": 250000,
        "following": 0,
        "created_at": "2008-05-14T20:30:00Z",
        "account_age_days": 18 * 365,
        "repos": {
            "total": 8,
            "total_stars": 180000,
            "total_forks": 50000,
            "max_stars": 170000,
            "avg_stars": 22500,
            "with_stars": 5,
            "star_50": 3,
            "star_100": 2,
            "star_500": 1,
            "star_1000": 1,
            "languages": ["C", "Python", "Shell"],
            "top_language": "C",
            "language_count": 3,
            "top_repos": [
                {"name": "linux", "stars": 170000, "forks": 48000, "language": "C",
                 "description": "Linux kernel source tree", "topics": ["kernel", "os"]},
                {"name": "git", "stars": 9000, "forks": 2000, "language": "C",
                 "description": "Git Source Code Mirror", "topics": ["vcs", "git"]},
                {"name": "subsurface", "stars": 500, "forks": 300, "language": "C",
                 "description": "Dive log program", "topics": ["diving"]},
            ],
            "recent_topics": ["kernel", "os", "vcs", "git", "diving"],
        },
        "events": {
            "total_events": 120,
            "push_count": 80,
            "pr_count": 15,
            "create_count": 10,
            "issue_count": 5,
            "watch_count": 50,
            "fork_count": 30,
            "unique_event_repos": 5,
        },
    }


def main():
    parser = argparse.ArgumentParser(
        description="Generate an HLTV-style CS player card from GitHub data."
    )
    parser.add_argument("username", nargs="?", help="GitHub username")
    parser.add_argument(
        "-o", "--output", default="card.png",
        help="Output image path (default: card.png)",
    )
    parser.add_argument(
        "-t", "--token",
        default=os.environ.get("GITHUB_TOKEN"),
        help="GitHub personal access token (or set GITHUB_TOKEN env var)",
    )
    parser.add_argument(
        "--demo", action="store_true",
        help="Generate a sample card using built-in demo data (no network required)",
    )
    args = parser.parse_args()

    if args.demo:
        raw = _sample_data()
    else:
        if not args.username:
            parser.error("username is required (use --demo for offline testing)")
        try:
            raw = fetch_github_data(args.username, args.token)
        except Exception as e:
            print(f"Failed to fetch GitHub data: {e}", file=sys.stderr)
            print(
                "Tip: use --demo to generate a sample card without network access.",
                file=sys.stderr,
            )
            sys.exit(1)

    stats = build_stats(raw)
    rank = overall_rank(stats["rating"])

    output_path = args.output
    if not os.path.isabs(output_path):
        output_path = os.path.join(os.getcwd(), output_path)

    generate_card(raw, stats, rank, output_path)
    print(f"Card saved to {output_path}")


if __name__ == "__main__":
    main()
