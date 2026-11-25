"""Required check: a portal PR needs an approval from someone other than the person who submitted it.

GitHub blocks PR authors from approving their own PRs, but portal PRs are authored by the portal's
GitHub App. The portal writes the submitter's identity hash into a trailer on the commit it creates,
and GitHub signs that commit. This check reads the trailer only from a verified commit authored by
the App, maps approvers through platform/reviewers.json on main, and passes when at least one mapped
approver of the current head commit is not the submitter. Standard library only.
"""
from __future__ import annotations

import base64
import json
import os
import re
import sys
import urllib.request

TRAILER_RE = re.compile(r"^Portal-Submitter: (sha256:[0-9a-f]{64})$", re.M)
HASH_RE = re.compile(r"sha256:[0-9a-f]{64}")


def submitter_of(commits: list[dict], bot: str) -> tuple[str | None, str]:
    """Returns the submitter hash from the App's verified commits, or None and the reason."""
    found = set()
    for c in commits:
        if (c.get("author") or {}).get("login") != bot:
            continue
        if not c["commit"].get("verification", {}).get("verified"):
            return None, f"Commit {c['sha'][:12]} claims to be from {bot} but is not verified."
        found.update(TRAILER_RE.findall(c["commit"]["message"]))
    if len(found) != 1:
        return None, f"Expected one Portal-Submitter trailer on a verified {bot} commit, found {len(found)}."
    return found.pop(), ""


def evaluate(pr: dict, commits: list[dict], reviews: list[dict], reviewers: dict[str, str], bot: str) -> tuple[bool, str]:
    if pr["user"]["login"] != bot:
        return True, "Not a portal PR. GitHub already stops authors approving their own PRs."
    submitter, reason = submitter_of(commits, bot)
    if not submitter:
        return False, reason
    latest: dict[str, dict] = {}
    for review in reviews:
        if review.get("user") and review.get("state") in ("APPROVED", "CHANGES_REQUESTED", "DISMISSED"):
            latest[review["user"]["login"]] = review
    approvers = sorted(login for login, r in latest.items()
                       if r["state"] == "APPROVED" and r.get("commit_id") == pr["head"]["sha"])
    independent = [a for a in approvers if reviewers.get(a) and reviewers[a] != submitter]
    if independent:
        return True, f"Independent approval from {', '.join(independent)}."
    own = [a for a in approvers if reviewers.get(a) == submitter]
    unmapped = [a for a in approvers if not reviewers.get(a)]
    notes = []
    if own:
        notes.append(f"{', '.join(own)} submitted this change, so their approval does not count")
    if unmapped:
        notes.append(f"{', '.join(unmapped)} is not in platform/reviewers.json")
    return False, "Needs an approval of the current commit from a reviewer who did not submit it. " + "; ".join(notes)


def _api(path: str, token: str):
    req = urllib.request.Request(f"https://api.github.com/repos/{os.environ['REPO']}/{path}", headers={
        "Accept": "application/vnd.github+json", "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2022-11-28"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())


def _pages(path: str, token: str) -> list:
    items, page = [], 1
    while True:
        batch = _api(f"{path}?per_page=100&page={page}", token)
        items.extend(batch)
        if len(batch) < 100 or page >= 10:
            return items
        page += 1


def load_reviewers(raw: bytes) -> dict[str, str]:
    data = json.loads(raw).get("reviewers", {})
    if not isinstance(data, dict) or not all(isinstance(k, str) and HASH_RE.fullmatch(str(v)) for k, v in data.items()):
        raise ValueError("platform/reviewers.json must map GitHub logins to sha256 identity hashes.")
    return data


def main() -> int:
    token, number, bot = os.environ["GH_TOKEN"], os.environ["PR_NUMBER"], os.environ["PORTAL_BOT"]
    pr = _api(f"pulls/{number}", token)
    if pr["base"]["ref"] != "main":
        print("Not a PR to main.")
        return 0
    content = _api("contents/platform/reviewers.json?ref=main", token)["content"]
    ok, message = evaluate(pr, _pages(f"pulls/{number}/commits", token), _pages(f"pulls/{number}/reviews", token),
                           load_reviewers(base64.b64decode(content)), bot)
    print(message)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
