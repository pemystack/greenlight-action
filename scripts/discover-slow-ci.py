"""
CI Discovery Bot — finds public repos with slow CI and generates outreach.

Searches GitHub for repos with test workflows that take >8 minutes,
generates a personalized message for each, and outputs a curated list.

Usage:
    python scripts/discover-slow-ci.py [--post]

    Without --post: prints the list (dry run)
    With --post:    opens a Discussion on each repo (if Discussions enabled)
                    or creates an Issue (if not)
"""

from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone

import requests

GH_TOKEN = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN", "")
HEADERS = {
    "Authorization": f"Bearer {GH_TOKEN}",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}

MIN_CI_MINUTES = 8
MIN_STARS = 30
MAX_STARS = 10000
MAX_RESULTS = 10
SEEN_FILE = os.environ.get("SEEN_FILE", "data/discovered-repos.json")

# Test frameworks we support
FRAMEWORKS = ["playwright", "jest", "pytest", "cypress", "espresso", "junit"]


def _gh(url: str, method: str = "GET", **kwargs) -> dict | list | None:
    resp = requests.request(method, f"https://api.github.com/{url}", headers=HEADERS, **kwargs)
    if resp.status_code == 403 and "rate limit" in resp.text.lower():
        print(f"  [rate-limited] sleeping 60s...")
        time.sleep(60)
        resp = requests.request(method, f"https://api.github.com/{url}", headers=HEADERS, **kwargs)
    if not resp.ok:
        return None
    return resp.json()


def _load_seen() -> set[str]:
    if os.path.exists(SEEN_FILE):
        with open(SEEN_FILE) as f:
            return set(json.load(f))
    return set()


def _save_seen(seen: set[str]) -> None:
    os.makedirs(os.path.dirname(SEEN_FILE) or ".", exist_ok=True)
    with open(SEEN_FILE, "w") as f:
        json.dump(sorted(seen), f, indent=2)


def find_repos_with_tests(language: str, page: int = 1) -> list[dict]:
    """Find active repos with test-related CI workflows."""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=14)).strftime("%Y-%m-%d")
    q = f"stars:{MIN_STARS}..{MAX_STARS} language:{language} pushed:>{cutoff}"
    data = _gh(f"search/repositories?q={q}&sort=updated&per_page=20&page={page}")
    if not data:
        return []
    return data.get("items", [])


def get_slow_ci_runs(repo_full_name: str) -> list[dict]:
    """Find CI workflow runs that took >MIN_CI_MINUTES."""
    data = _gh(f"repos/{repo_full_name}/actions/runs?per_page=15")
    if not data:
        return []

    slow = []
    for run in data.get("workflow_runs", []):
        name = (run.get("name") or "").lower()
        # Only look at test/CI runs
        if not any(kw in name for kw in ["test", "ci", "e2e", "check", "build"]):
            continue

        started = run.get("run_started_at")
        updated = run.get("updated_at")
        if not started or not updated:
            continue

        start = datetime.fromisoformat(started.replace("Z", "+00:00"))
        end = datetime.fromisoformat(updated.replace("Z", "+00:00"))
        minutes = (end - start).total_seconds() / 60

        if minutes >= MIN_CI_MINUTES:
            slow.append({
                "name": run["name"],
                "minutes": round(minutes),
                "conclusion": run.get("conclusion"),
                "url": run.get("html_url"),
            })

    return slow


def detect_test_framework(repo_full_name: str) -> str | None:
    """Check which test framework the repo uses via workflow files."""
    data = _gh(f"search/code?q=repo:{repo_full_name}+path:.github/workflows+extension:yml&per_page=5")
    if not data:
        return None

    # Check workflow file contents for framework keywords
    for item in data.get("items", []):
        # The search API doesn't return file content, but the name/path hints help
        name = (item.get("name") or "").lower()
        path = (item.get("path") or "").lower()
        for fw in FRAMEWORKS:
            if fw in name or fw in path:
                return fw

    return None


def generate_message(repo: dict, slow_runs: list[dict], framework: str | None) -> str:
    """Generate a personalized outreach message."""
    repo_name = repo["full_name"]
    avg_min = round(sum(r["minutes"] for r in slow_runs) / len(slow_runs))
    max_min = max(r["minutes"] for r in slow_runs)

    fw_line = ""
    if framework:
        fw_line = f" It supports {framework.capitalize()} out of the box."

    return f"""### Speed up your CI with AI-powered test selection

Hi! I noticed your CI test runs average **{avg_min} minutes** (up to {max_min} min on recent runs).

[Pemystack Greenlight](https://github.com/pemystack/greenlight-action) can cut that by **60-80%** by analyzing each PR's code changes and running only the tests relevant to the diff.{fw_line}

**One-line setup** — add this to your workflow:

```yaml
- uses: pemystack/greenlight-action@v1
  with:
    anthropic_api_key: ${{{{ secrets.ANTHROPIC_API_KEY }}}}
    github_token: ${{{{ secrets.GITHUB_TOKEN }}}}
```

It works alongside your existing test runner — no migration needed. Free and open source.

Happy to answer questions. Built by [@leader-ke](https://github.com/leader-ke), Senior QA Engineer with 10+ years in test automation.
"""


def main() -> None:
    post_mode = "--post" in sys.argv
    seen = _load_seen()
    discoveries: list[dict] = []

    print(f"Searching for repos with CI > {MIN_CI_MINUTES}min ({MIN_STARS}-{MAX_STARS} stars)...\n")

    for lang in ["python", "typescript", "javascript"]:
        print(f"  [{lang}]")
        repos = find_repos_with_tests(lang)
        time.sleep(2)  # respect rate limits

        for repo in repos:
            name = repo["full_name"]
            if name in seen:
                continue

            slow = get_slow_ci_runs(name)
            if not slow:
                continue

            framework = detect_test_framework(name)
            time.sleep(1)

            msg = generate_message(repo, slow, framework)
            discoveries.append({
                "repo": name,
                "stars": repo["stargazers_count"],
                "avg_ci_min": round(sum(r["minutes"] for r in slow) / len(slow)),
                "max_ci_min": max(r["minutes"] for r in slow),
                "framework": framework,
                "slow_runs": len(slow),
                "message": msg,
            })

            seen.add(name)
            print(f"    ✓ {name} — {slow[0]['minutes']}min CI, {repo['stargazers_count']} stars")

            if len(discoveries) >= MAX_RESULTS:
                break

        if len(discoveries) >= MAX_RESULTS:
            break

    _save_seen(seen)

    if not discoveries:
        print("\nNo new repos with slow CI found this run.")
        return

    print(f"\n{'='*60}")
    print(f"Found {len(discoveries)} repos with slow CI:\n")

    for d in discoveries:
        print(f"  {d['repo']} ({d['stars']} stars) — {d['avg_ci_min']}min avg CI")
        if d["framework"]:
            print(f"    Framework: {d['framework']}")
        print(f"    URL: https://github.com/{d['repo']}")
        print()

    # Save to JSON for review
    output_file = os.environ.get("OUTPUT_FILE", "data/ci-discoveries.json")
    os.makedirs(os.path.dirname(output_file) or ".", exist_ok=True)
    with open(output_file, "w") as f:
        json.dump(discoveries, f, indent=2)
    print(f"Saved to {output_file}")

    if post_mode:
        print("\n[post mode] Opening discussions/issues...")
        for d in discoveries:
            _post_outreach(d)
            time.sleep(5)  # be respectful


def _post_outreach(discovery: dict) -> None:
    """Open a Discussion (preferred) or Issue on the target repo."""
    repo = discovery["repo"]
    title = f"Speed up CI by 60-80% with AI test selection"
    body = discovery["message"]

    # Try Discussion first (less intrusive)
    # Check if Discussions are enabled
    repo_data = _gh(f"repos/{repo}")
    if repo_data and repo_data.get("has_discussions"):
        # Get discussion categories
        cats = _gh(f"repos/{repo}/discussions/categories")
        if cats:
            # Find "Ideas" or "General" category
            cat_id = None
            for cat in cats:
                if cat["name"].lower() in ("ideas", "general", "feedback"):
                    cat_id = cat["id"]
                    break
            if cat_id:
                # GraphQL mutation needed for discussions — skip for now
                print(f"  [skip] {repo} has Discussions but GraphQL needed")
                return

    # Fall back to Issue
    result = _gh(f"repos/{repo}/issues", method="POST", json={"title": title, "body": body})
    if result and "html_url" in result:
        print(f"  ✓ Opened issue: {result['html_url']}")
    else:
        print(f"  ✗ Failed to open issue on {repo}")


if __name__ == "__main__":
    main()
