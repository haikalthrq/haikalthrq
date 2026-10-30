#!/usr/bin/env python3
"""Generate an aggregate, privacy-preserving GitHub coding activity SVG.

Metric: distinct (repository, commit SHA, source path) edits on commits authored
by the profile owner in the previous 12 calendar months, across accessible
repositories and branches. This does not measure working time or proficiency.

Only aggregate language counts appear in the SVG. No repository names,
private paths, commit messages, hashes, or credentials are published.
"""
from __future__ import annotations

import calendar
import collections
from datetime import datetime, timezone
from html import escape
import json
import os
from pathlib import Path
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

OWNER = "haikalthrq"
API = "https://api.github.com"
OUT = Path("assets/coding-activity.svg")
MAX_REQUESTS = 4500
SKIP_PARTS = {
    "node_modules", ".venv", "venv", "vendor", "dist", "build",
    ".next", "coverage", "__pycache__", "target", ".git",
}
LANG = {
    ".py": "Python", ".pyi": "Python", ".ipynb": "Python (notebooks)",
    ".ts": "TypeScript", ".tsx": "TypeScript",
    ".js": "JavaScript", ".jsx": "JavaScript",
    ".mjs": "JavaScript", ".cjs": "JavaScript",
    ".cs": "C#", ".fs": "F#", ".sql": "SQL",
    ".html": "HTML", ".htm": "HTML", ".css": "CSS",
    ".scss": "CSS", ".sass": "CSS",
    ".sh": "Shell", ".bash": "Shell", ".zsh": "Shell",
    ".ps1": "PowerShell", ".psm1": "PowerShell",
    ".lua": "Lua / Luau", ".luau": "Lua / Luau",
    ".cpp": "C++", ".cc": "C++", ".cxx": "C++",
    ".hpp": "C++", ".hh": "C++",
    ".c": "C", ".h": "C / C++",
    ".go": "Go", ".rs": "Rust", ".java": "Java",
    ".kt": "Kotlin", ".kts": "Kotlin",
    ".swift": "Swift", ".dart": "Dart",
    ".r": "R", ".rb": "Ruby", ".php": "PHP",
}
PALETTE = [
    "#58a6ff", "#3fb950", "#d2a8ff", "#ffa657",
    "#f778ba", "#79c0ff", "#ff7b72", "#a5d6ff",
    "#e3b341", "#b1bac4",
]


def since_twelve_months(now: datetime) -> datetime:
    year = now.year - 1
    day = min(now.day, calendar.monthrange(year, now.month)[1])
    return now.replace(year=year, day=day)


def language_of(path: str) -> str | None:
    parts = path.lower().split("/")
    if any(part in SKIP_PARTS for part in parts[:-1]):
        return None
    name = parts[-1]
    if name.endswith((".min.js", ".min.css", ".map", ".generated.ts")):
        return None
    if name in ("dockerfile", "containerfile"):
        return "Dockerfile"
    if name.endswith(".g.cs"):
        return None
    return LANG.get(Path(name).suffix)


class GitHub:
    def __init__(self, token: str):
        self.token = token
        self.calls = 0

    def get(self, path: str, params: dict | None = None, *,
            allow_missing: bool = False):
        self.calls += 1
        if self.calls > MAX_REQUESTS:
            raise RuntimeError("API budget exhausted; refusing an incomplete chart")
        url = API + path
        if params:
            url += "?" + urlencode(params)
        request = Request(url, headers={
            "Authorization": "Bearer " + self.token,
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "haikalthrq-coding-activity",
        })
        for attempt in range(4):
            try:
                with urlopen(request, timeout=30) as response:
                    return json.load(response)
            except HTTPError as exc:
                if allow_missing and exc.code in (404, 409, 422):
                    return None
                if exc.code in (429, 502, 503, 504) and attempt < 3:
                    time.sleep(3 * (attempt + 1))
                    continue
                raise RuntimeError(
                    "GitHub API request failed (HTTP " + str(exc.code) +
                    "); not publishing incomplete data"
                ) from None
            except URLError:
                if attempt < 3:
                    time.sleep(3 * (attempt + 1))
                    continue
                raise RuntimeError("GitHub network error; no chart published") from None
        raise RuntimeError("GitHub request retries exhausted")

    def pages(self, path: str, params: dict | None = None, *,
              allow_missing: bool = False):
        page = 1
        while True:
            options = dict(params or {})
            options.update({"per_page": 100, "page": page})
            result = self.get(path, options, allow_missing=allow_missing)
            if result is None:
                return
            if not isinstance(result, list):
                raise RuntimeError("Unexpected GitHub response; no chart published")
            yield from result
            if len(result) < 100:
                return
            page += 1


def is_modified_fork(api: GitHub, repo: dict) -> bool:
    if not repo.get("fork"):
        return True
    name = repo["name"]
    full = repo["full_name"]
    details = api.get("/repos/" + quote(full, safe="/"), allow_missing=True)
    parent = (details or {}).get("parent") or {}
    parent_name = parent.get("full_name")
    parent_branch = parent.get("default_branch")
    if not parent_name or not parent_branch:
        return False  # Unknown upstream: exclude rather than claim authorship.
    base = parent_name.split("/")[0] + ":" + parent_branch
    head = OWNER + ":" + repo.get("default_branch", "main")
    path = "/repos/" + quote(full, safe="/") + "/compare/" + quote(base, safe="") + "..." + quote(head, safe="")
    comparison = api.get(path, allow_missing=True)
    return isinstance(comparison, dict) and comparison.get("ahead_by", 0) > 0


def collect(api: GitHub, now: datetime) -> tuple[collections.Counter, int, int]:
    start = since_twelve_months(now).isoformat(timespec="seconds").replace("+00:00", "Z")
    end = now.isoformat(timespec="seconds").replace("+00:00", "Z")
    counts: collections.Counter[str] = collections.Counter()
    commit_total = 0
    repo_total = 0
    repos = api.pages("/user/repos", {"affiliation": "owner", "sort": "full_name"})
    for repo in repos:
        if repo.get("owner", {}).get("login", "").lower() != OWNER:
            continue
        if repo.get("name") == OWNER or repo.get("size", 0) == 0:
            continue
        if not is_modified_fork(api, repo):
            continue
        full = repo["full_name"]
        base = "/repos/" + quote(full, safe="/")
        branches = api.pages(base + "/branches", allow_missing=True)
        seen: set[str] = set()
        changed = False
        for branch in branches:
            name = branch.get("name")
            if not name:
                continue
            for summary in api.pages(base + "/commits", {
                "sha": name, "since": start, "until": end, "author": OWNER,
            }, allow_missing=True):
                sha = summary.get("sha")
                if not sha or sha in seen:
                    continue
                seen.add(sha)
                # Get commit details; follow pagination for commits >100 files.
                page = 1
                touched = False
                while True:
                    item = api.get(base + "/commits/" + quote(sha), {
                        "per_page": 100, "page": page,
                    })
                    files = item.get("files", [])
                    if not isinstance(files, list):
                        raise RuntimeError("Invalid commit files; no chart published")
                    for file in files:
                        lang = language_of(file.get("filename", ""))
                        if lang:
                            counts[lang] += 1
                            touched = True
                    if len(files) < 100:
                        break
                    page += 1
                if touched:
                    commit_total += 1
                    changed = True
        if changed:
            repo_total += 1
    return counts, commit_total, repo_total


def make_svg(counts: collections.Counter, now: datetime, commits: int) -> str:
    total = sum(counts.values())
    rows = counts.most_common(9)
    if len(counts) > 9:
        rows.append(("Other", sum(v for _, v in counts.most_common()[9:])))
    height = 164 + max(len(rows), 1) * 40
    start = since_twelve_months(now).strftime("%d %b %Y")
    end = now.strftime("%d %b %Y")
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="720" height="{height}" viewBox="0 0 720 {height}" role="img" aria-labelledby="title desc">',
        '<title id="title">Coding activity by language, last twelve months</title>',
        '<desc id="desc">Counts of source-file edits in authored commits, aggregated across accessible public and private repositories. Files edited in multiple commits count multiple times. Notebook files are classified separately from Python scripts.</desc>',
        '<rect width="720" height="100%" rx="12" fill="#0d1117" stroke="#30363d"/>',
        '<text x="28" y="42" fill="#e6edf3" font-size="22" font-weight="700" font-family="Arial, Helvetica, sans-serif">Coding activity · last 12 months</text>',
        f'<text x="28" y="67" fill="#8b949e" font-size="13" font-family="Arial, Helvetica, sans-serif">{escape(start)} – {escape(end)} · {commits:,} authored commits with code edits</text>',
        '<text x="28" y="91" fill="#8b949e" font-size="12" font-family="Arial, Helvetica, sans-serif">Each file changed in a commit counts once. Not file size, skill level, or coding hours.</text>',
    ]
    if not total:
        parts += [
            '<text x="28" y="147" fill="#c9d1d9" font-size="16" font-family="Arial, Helvetica, sans-serif">No authored source-file edits found in this period.</text>'
        ]
    for i, (lang, count) in enumerate(rows):
        y = 135 + i * 40
        share = count / total if total else 0
        label = escape(lang)
        parts += [
            f'<text x="28" y="{y}" fill="#c9d1d9" font-size="14" font-family="Arial, Helvetica, sans-serif">{label}</text>',
            f'<text x="688" y="{y}" text-anchor="end" fill="#c9d1d9" font-size="14" font-family="Arial, Helvetica, sans-serif">{share * 100:.1f}%  ·  {count:,} edits</text>',
            f'<rect x="28" y="{y+9}" width="660" height="9" rx="4.5" fill="#21262d"/>',
            f'<rect x="28" y="{y+9}" width="{max(0.0, 660 * share):.2f}" height="9" rx="4.5" fill="{PALETTE[i % len(PALETTE)]}"/>',
        ]
    parts += [
        f'<text x="28" y="{height-25}" fill="#8b949e" font-size="12" font-family="Arial, Helvetica, sans-serif">GitHub API · aggregate only · updated {escape(now.strftime("%d %b %Y"))} UTC</text>',
        '</svg>',
    ]
    return "\n".join(parts) + "\n"


def main() -> None:
    token = os.getenv("CODING_ACTIVITY_TOKEN", "").strip()
    if not token:
        raise SystemExit("Set CODING_ACTIVITY_TOKEN as a repository Actions secret (read-only)")
    now = datetime.now(timezone.utc)
    api = GitHub(token)
    counts, commits, repos = collect(api, now)
    svg = make_svg(counts, now, commits)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(svg, encoding="utf-8")
    print("Generated aggregate coding-activity SVG; authored commits with code edits:",
          commits, "repositories:", repos, "API requests:", api.calls)
    # Never log private repository names, file paths, commit messages or token.


if __name__ == "__main__":
    main()
