"""Fills TEMPLATE.md with live numbers from the GitHub API and writes README.md.

Runs daily from .github/workflows/update.yml; needs GITHUB_TOKEN in the environment.
"""
import json
import os
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

USER = "Gnottero"
ROOT = Path(__file__).resolve().parent.parent


def graphql(query: str, **variables) -> dict:
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": query, "variables": variables}).encode(),
        headers={"Authorization": f"bearer {os.environ['GITHUB_TOKEN']}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req) as r:
        body = json.load(r)
    if "errors" in body:
        raise SystemExit(body["errors"])
    return body["data"]["user"]


def stars_and_created() -> tuple[int, datetime]:
    user = graphql(
        """query($login: String!) { user(login: $login) {
             createdAt
             repositories(first: 100, privacy: PUBLIC, isFork: false, ownerAffiliations: OWNER) {
               nodes { stargazerCount }
             }
           } }""",
        login=USER,
    )
    stars = sum(r["stargazerCount"] for r in user["repositories"]["nodes"])
    return stars, datetime.fromisoformat(user["createdAt"].replace("Z", "+00:00"))


def total_commits(since: datetime) -> int:
    # contributionsCollection spans at most one year, so ask for each year separately.
    now = datetime.now(timezone.utc)
    windows = []
    start = since
    while start < now:
        end = min(start.replace(year=start.year + 1), now)
        windows.append((start, end))
        start = end
    fields = "\n".join(
        f'y{i}: contributionsCollection(from: "{a.isoformat()}", to: "{b.isoformat()}") {{ totalCommitContributions }}'
        for i, (a, b) in enumerate(windows)
    )
    user = graphql(f"query($login: String!) {{ user(login: $login) {{ {fields} }} }}", login=USER)
    return sum(v["totalCommitContributions"] for v in user.values())


if __name__ == "__main__":
    stars, created = stars_and_created()
    commits = total_commits(created)
    readme = (ROOT / "TEMPLATE.md").read_text()
    readme = readme.replace("{{COMMITS}}", f"{commits:,}").replace("{{STARS}}", f"{stars:,}")
    (ROOT / "README.md").write_text(readme)
    print(f"commits={commits} stars={stars}")
