"""Renders assets/stats.svg from the GitHub GraphQL API.

Runs daily from .github/workflows/stats.yml; needs GITHUB_TOKEN in the environment.
"""
import json
import os
import urllib.request
from pathlib import Path

USER = "Gnottero"
OUT = Path(__file__).resolve().parent.parent / "assets" / "stats.svg"
# Markup and glue code would drown out the languages I actually write.
IGNORED_LANGS = {"HTML", "CSS", "Dockerfile", "Shell", "Makefile", "Batchfile"}

QUERY = """
query($login: String!) {
  user(login: $login) {
    followers { totalCount }
    repositories(first: 100, privacy: PUBLIC, isFork: false, ownerAffiliations: OWNER) {
      totalCount
      nodes {
        stargazerCount
        languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
          edges { size node { name color } }
        }
      }
    }
    contributionsCollection {
      totalCommitContributions
      totalPullRequestContributions
      contributionCalendar {
        totalContributions
        weeks { contributionDays { contributionLevel } }
      }
    }
  }
}
"""

LEVELS = {"NONE": 0, "FIRST_QUARTILE": 1, "SECOND_QUARTILE": 2, "THIRD_QUARTILE": 3, "FOURTH_QUARTILE": 4}


def fetch() -> dict:
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": {"login": USER}}).encode(),
        headers={"Authorization": f"bearer {os.environ['GITHUB_TOKEN']}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req) as r:
        body = json.load(r)
    if "errors" in body:
        raise SystemExit(body["errors"])
    return body["data"]["user"]


def esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def render(u: dict) -> str:
    repos = u["repositories"]
    cc = u["contributionsCollection"]
    cal = cc["contributionCalendar"]

    langs: dict[str, list] = {}
    for repo in repos["nodes"]:
        for e in repo["languages"]["edges"]:
            name = e["node"]["name"]
            if name in IGNORED_LANGS:
                continue
            langs.setdefault(name, [0, e["node"]["color"] or "#64748b"])[0] += e["size"]
    top = sorted(langs.items(), key=lambda kv: -kv[1][0])[:8]
    total = sum(v[0] for _, v in top) or 1

    tiles = [
        ("Contributions (1y)", cal["totalContributions"]),
        ("Commits (1y)", cc["totalCommitContributions"]),
        ("Public repos", repos["totalCount"]),
        ("Stars earned", sum(r["stargazerCount"] for r in repos["nodes"])),
    ]

    parts = []
    # Stat tiles, 2x2
    for i, (label, value) in enumerate(tiles):
        x, y = 48 + (i % 2) * 262, 84 + (i // 2) * 104
        parts.append(
            f'<rect class="tile" x="{x}" y="{y}" width="246" height="92" rx="14"/>'
            f'<text class="sans num" x="{x + 22}" y="{y + 46}">{value:,}</text>'
            f'<text class="sans label" x="{x + 22}" y="{y + 74}">{esc(label)}</text>'
        )

    # Language bar + legend
    bx, bw, x = 620, 532, 620.0
    parts.append(f'<clipPath id="bar"><rect x="{bx}" y="92" width="{bw}" height="12" rx="6"/></clipPath><g clip-path="url(#bar)">')
    for name, (size, color) in top:
        w = bw * size / total
        parts.append(f'<rect x="{x:.1f}" y="92" width="{w + 0.5:.1f}" height="12" fill="{color}"/>')
        x += w
    parts.append("</g>")
    for i, (name, (size, color)) in enumerate(top):
        lx, ly = bx + (i % 2) * 270, 144 + (i // 2) * 36
        parts.append(
            f'<circle cx="{lx + 7}" cy="{ly - 6}" r="7" fill="{color}"/>'
            f'<text class="sans legend" x="{lx + 24}" y="{ly}">{esc(name)}'
            f'<tspan class="pct"> {100 * size / total:.1f}%</tspan></text>'
        )

    # Contribution heatmap
    weeks = cal["weeks"][-53:]
    step, cell = 20.8, 16.5
    for wi, week in enumerate(weeks):
        days = week["contributionDays"]
        # Only the first week can start mid-week; push it down so weekdays line up.
        offset = 7 - len(days) if wi == 0 else 0
        for di, day in enumerate(days, start=offset):
            lvl = LEVELS[day["contributionLevel"]]
            parts.append(
                f'<rect class="l{lvl}" x="{48 + wi * step:.1f}" y="{350 + di * step:.1f}" width="{cell}" height="{cell}" rx="4"/>'
            )

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="532" viewBox="0 0 1200 532" role="img" aria-label="GitHub stats for {USER}">
  <style>
    :root {{
      --panel: #0f1523; --stroke: #1f2937; --tile: #151d2e; --text: #f1f5f9; --muted: #94a3b8;
      --l0: #1a2233; --l1: #3b2a6b; --l2: #5b3bb5; --l3: #7c3aed; --l4: #a78bfa;
    }}
    @media (prefers-color-scheme: light) {{
      :root {{
        --panel: #ffffff; --stroke: #e2e8f0; --tile: #f8fafc; --text: #0f172a; --muted: #64748b;
        --l0: #eef2f7; --l1: #ddd6fe; --l2: #a78bfa; --l3: #7c3aed; --l4: #5b21b6;
      }}
    }}
    .sans {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif; }}
    .panel {{ fill: var(--panel); stroke: var(--stroke); }}
    .tile {{ fill: var(--tile); stroke: var(--stroke); }}
    .h {{ fill: var(--text); font-size: 24px; font-weight: 700; }}
    .num {{ fill: var(--text); font-size: 38px; font-weight: 800; letter-spacing: -.5px; }}
    .label, .legend {{ fill: var(--muted); font-size: 19px; }}
    .legend {{ fill: var(--text); }}
    .pct {{ fill: var(--muted); }}
    .l0 {{ fill: var(--l0); }} .l1 {{ fill: var(--l1); }} .l2 {{ fill: var(--l2); }} .l3 {{ fill: var(--l3); }} .l4 {{ fill: var(--l4); }}
  </style>
  <defs>
    <linearGradient id="g" x1="0" x2="1"><stop offset="0" stop-color="#7c3aed"/><stop offset=".5" stop-color="#2563eb"/><stop offset="1" stop-color="#06b6d4"/></linearGradient>
    <clipPath id="c"><rect x="1" y="1" width="1198" height="530" rx="24"/></clipPath>
  </defs>
  <rect class="panel" x="1" y="1" width="1198" height="530" rx="24"/>
  <g clip-path="url(#c)"><rect width="1200" height="5" fill="url(#g)"/></g>
  <text class="sans h" x="48" y="58">By the numbers</text>
  <text class="sans h" x="620" y="58">Languages</text>
  <text class="sans h" x="48" y="330">Last 12 months</text>
  {chr(10).join(parts)}
</svg>
"""


if __name__ == "__main__":
    OUT.write_text(render(fetch()))
    print("wrote", OUT)
