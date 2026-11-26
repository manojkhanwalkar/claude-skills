#!/usr/bin/env python3
"""Gather a SOX ITGC evidence pack for one GitHub repository, read-only.

Usage (from inside the repository, or with --repo):
    python3 -I sox_evidence.py --since 2026-01-01 [--until 2026-12-31] [--repo OWNER/NAME]
        [--out DIR] [--environment NAME] [--emergency-label hotfix] [--incident-label incident]
        [--bot LOGIN] [--max-lookups 200]

It calls only GET endpoints through the `gh` CLI (which holds the token; this script never sees
or prints it) and writes, into --out:
    <area>.json       raw evidence per ITGC area (access, change, deploy, operations, evidence)
    summary.md        exceptions (with a SOX item ID and severity), the access listing and gaps
    MANIFEST.sha256   SHA-256 of every file above, so later tampering shows

Exit status: 0 when the pack was written (even with exceptions), 2 on bad arguments, or when gh
is missing, not signed in or can't read the repository (nothing is written then). This is evidence for an engineering check, not an audit opinion.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import pathlib
import re
import subprocess
import sys
import urllib.parse

REPO_RE = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+")
DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")
LABEL_RE = re.compile(r"[\w .:/-]{1,50}")
GH_TIMEOUT_S = 60
GH_PAGINATED_TIMEOUT_S = 300  # one timeout covers every page of a --paginate call
RUNS_CAP, INCIDENTS_CAP, PRS_CAP = 1000, 500, 1000  # API / gh list limits; reaching one is a gap
# gh's review authors carry only a login, so bots are known by name ("[bot]" logins are always bots).
KNOWN_BOTS = {"github-actions", "dependabot", "copilot-pull-request-reviewer", "renovate", "mergify",
              "claude", "coderabbitai", "sourcery-ai", "codecov", "sonarcloud"}
SEVERITY_ORDER = {"High": 0, "Medium": 1, "Low": 2, "Info": 3}


class GhError(RuntimeError):
    """A gh call failed: not found, no permission, timeout or bad output."""


class Gh:
    """Runs read-only `gh` commands with a timeout and parses their JSON (one retry layer: none)."""

    def __init__(self, runner=subprocess.run):
        self._run = runner

    def _call(self, args: list[str], timeout: int = GH_TIMEOUT_S):
        try:
            proc = self._run(["gh", *args], capture_output=True, text=True, timeout=timeout)
        except subprocess.TimeoutExpired as exc:
            raise GhError(f"timed out after {timeout}s") from exc
        except FileNotFoundError as exc:
            raise GhError("gh is not installed or not on PATH") from exc
        if proc.returncode != 0:
            # gh prints the HTTP status in stderr ("HTTP 404"); keep one line, never the token.
            lines = (proc.stderr or "").strip().splitlines()
            raise GhError((lines[-1] if lines else "gh failed")[:200])
        try:
            return json.loads(proc.stdout or "null")
        except json.JSONDecodeError as exc:
            raise GhError("gh returned output that is not JSON") from exc

    def api(self, path: str, paginate: bool = False):
        """GET a REST path; with paginate, return every page's items as one list."""
        args = ["api", "-X", "GET", path]
        if not paginate:
            return self._call(args)
        pages = self._call([*args, "--paginate", "--slurp"], timeout=GH_PAGINATED_TIMEOUT_S) or []
        items: list = []
        for page in pages:
            if isinstance(page, list):
                items.extend(page)
            elif isinstance(page, dict):
                # Search-style pages wrap the list: {"total_count": n, "workflow_runs": [...]}.
                items.extend(next((v for v in page.values() if isinstance(v, list)), []))
        return items

    def cli(self, args: list[str]):
        return self._call(args)


class Pack:
    """Collects evidence, exceptions and gaps while the areas are gathered."""

    def __init__(self):
        self.evidence: dict[str, dict] = {}
        self.exceptions: list[dict] = []
        self.gaps: list[str] = []

    def flag(self, sox_id: str, severity: str, item: str, detail: str):
        self.exceptions.append({"id": sox_id, "severity": severity, "item": item, "detail": detail})

    def gather(self, area: str, key: str, fetch, default=None):
        """Run fetch(); on GhError record a gap and return default, so one 403 never stops the pack."""
        try:
            value = fetch()
        except GhError as exc:
            self.gaps.append(f"{area}/{key}: not gathered ({exc})")
            value = default
        self.evidence.setdefault(area, {})[key] = value
        return value


# ---------- pure analysis (unit-tested without gh) ----------

def branch_controls(protection: dict | None, rules: list | None) -> dict:
    """Merge classic branch protection and the rulesets that apply into one view of the controls."""
    p = protection or {}
    reviews = p.get("required_pull_request_reviews") or {}
    c = {
        "pr_required": bool(reviews),
        "approvals": reviews.get("required_approving_review_count", 0) if reviews else 0,
        "dismiss_stale": bool(reviews.get("dismiss_stale_reviews")),
        "last_push_approval": bool(reviews.get("require_last_push_approval")),
        "code_owners": bool(reviews.get("require_code_owner_reviews")),
        "status_checks": bool((p.get("required_status_checks") or {}).get("contexts")
                              or (p.get("required_status_checks") or {}).get("checks")),
        "classic": bool(protection),
        "enforce_admins": bool((p.get("enforce_admins") or {}).get("enabled")),
        "force_push_blocked": bool(protection) and not (p.get("allow_force_pushes") or {}).get("enabled"),
        "deletion_blocked": bool(protection) and not (p.get("allow_deletions") or {}).get("enabled"),
    }
    for rule in rules or []:
        kind, params = rule.get("type"), rule.get("parameters") or {}
        if kind == "pull_request":
            c["pr_required"] = True
            c["approvals"] = max(c["approvals"], params.get("required_approving_review_count", 0))
            c["dismiss_stale"] |= bool(params.get("dismiss_stale_reviews_on_push"))
            c["last_push_approval"] |= bool(params.get("require_last_push_approval"))
            c["code_owners"] |= bool(params.get("require_code_owner_review"))
        elif kind == "required_status_checks":
            c["status_checks"] = True
        elif kind == "non_fast_forward":
            c["force_push_blocked"] = True
        elif kind == "deletion":
            c["deletion_blocked"] = True
    return c


def check_branch_controls(pack: Pack, branch: str, c: dict):
    item = f"branch {branch}"
    if not c["pr_required"] or c["approvals"] < 1:
        pack.flag("SOX-CM1/CM2", "High", item, "no pull request with at least one approval required")
    if not c["status_checks"]:
        pack.flag("SOX-CM3", "High", item, "no required status checks")
    if not c["force_push_blocked"] or not c["deletion_blocked"]:
        pack.flag("SOX-CM1", "High", item, "force pushes or branch deletion allowed")
    if c["classic"] and not c["enforce_admins"]:
        # Rulesets bind admins unless they are bypass actors, which are flagged separately.
        pack.flag("SOX-AC7", "Medium", item, "admins can bypass branch protection")
    if c["pr_required"] and not (c["dismiss_stale"] or c["last_push_approval"]):
        pack.flag("SOX-CM2", "Medium", item,
                  "approval need not cover the final commit (no stale dismissal or last-push approval)")


def access_listing(collaborators: list | None) -> dict:
    """Who can administer, maintain (and so change settings) or merge, by login."""
    out = {"admin": [], "maintain": [], "write": []}
    for user in collaborators or []:
        perms = user.get("permissions") or {}
        login = user.get("login", "?")
        if perms.get("admin"):
            out["admin"].append(login)
        elif perms.get("maintain"):
            out["maintain"].append(login)
        elif perms.get("push"):
            out["write"].append(login)
    return {k: sorted(v) for k, v in out.items()}


def is_bot(login: str | None, bots: set[str]) -> bool:
    name = (login or "").lower()
    return name.endswith("[bot]") or name in bots


def _approvals(pr: dict, bots: set[str]) -> list[dict]:
    author = (pr.get("author") or {}).get("login")
    return [r for r in pr.get("reviews") or []
            if r.get("state") == "APPROVED"
            and (r.get("author") or {}).get("login") not in (None, author)
            and not is_bot((r.get("author") or {}).get("login"), bots)]


def check_change(pack: Pack, prs: list[dict], emergency_labels: set[str],
                 bots: set[str] = frozenset(KNOWN_BOTS)) -> list[dict]:
    """Per merged PR: independent approval, approval of the final commit, emergency retro review."""
    rows = []
    for pr in prs:
        labels = {lbl.get("name", "").lower() for lbl in pr.get("labels") or []}
        emergency = bool(labels & emergency_labels)
        approvals = _approvals(pr, set(bots))
        merged_at = pr.get("mergedAt") or ""
        before = [r for r in approvals if (r.get("submittedAt") or "") <= merged_at]
        after = [r for r in approvals if (r.get("submittedAt") or "") > merged_at]
        head = pr.get("headRefOid")
        final = [r for r in before if (r.get("commit") or {}).get("oid") in (None, head)]
        item = f"PR #{pr.get('number')}"
        if emergency:
            if not before and not after:
                pack.flag("SOX-CM7", "High", item, "emergency change with no approval or retrospective review")
        elif not before:
            pack.flag("SOX-CM8", "High", item, "merged without an approval by someone other than the author")
        elif not final:
            pack.flag("SOX-CM8", "Medium", item, "approved, but not on the commit that was merged")
        rows.append({
            "number": pr.get("number"), "author": (pr.get("author") or {}).get("login"),
            "merged_by": (pr.get("mergedBy") or {}).get("login"), "merged_at": merged_at,
            "merge_commit": (pr.get("mergeCommit") or {}).get("oid"),
            "approvers": sorted({(r.get("author") or {}).get("login") for r in before}),
            "retro_approvers": sorted({(r.get("author") or {}).get("login") for r in after}),
            "emergency": emergency,
        })
    return rows


def check_environment(pack: Pack, env: dict) -> dict:
    """Who can deploy to an environment, and whether the deploy needs someone else's approval."""
    name = env.get("name", "?")
    reviewers, prevent_self = [], False
    for rule in env.get("protection_rules") or []:
        if rule.get("type") == "required_reviewers":
            prevent_self = bool(rule.get("prevent_self_review"))
            for r in rule.get("reviewers") or []:
                who = r.get("reviewer") or {}
                reviewers.append(who.get("login") or who.get("slug") or "?")
    branch_policy = env.get("deployment_branch_policy")
    item = f"environment {name}"
    if not reviewers:
        pack.flag("SOX-CM4/SOD1", "Medium", item, "no required reviewers before a deploy")
    elif not prevent_self:
        pack.flag("SOX-SOD1", "Medium", item, "the person who starts a deploy can approve it")
    if not branch_policy:
        pack.flag("SOX-CM4", "Medium", item, "any branch can deploy (no deployment branch policy)")
    return {"name": name, "reviewers": sorted(reviewers), "prevent_self_review": prevent_self,
            "branch_policy": branch_policy}


def check_runs(pack: Pack, runs: list[dict]) -> list[dict]:
    """Failures per workflow; a scheduled workflow whose latest run failed is an unfixed job failure."""
    by_wf: dict[str, dict] = {}
    for run in sorted(runs, key=lambda r: r.get("created_at") or ""):
        wf = by_wf.setdefault(run.get("name") or "?", {"runs": 0, "failures": 0, "scheduled": False, "last": None})
        wf["runs"] += 1
        failed = run.get("conclusion") in ("failure", "timed_out", "startup_failure")
        wf["failures"] += failed
        if run.get("event") == "schedule":
            wf["scheduled"] = True
            wf["last"] = run.get("conclusion")
    rows = []
    for name, wf in sorted(by_wf.items()):
        if wf["scheduled"] and wf["last"] in ("failure", "timed_out", "startup_failure"):
            pack.flag("SOX-OPS1", "Medium", f"workflow {name}", "latest scheduled run failed")
        rows.append({"workflow": name, **wf})
    return rows


def minimise_pr(pr: dict) -> dict:
    """Keep only logins for people (gh also returns names), so the pack holds no more PII than needed."""
    def who(obj):
        return {"login": (obj or {}).get("login")}
    out = dict(pr, author=who(pr.get("author")), mergedBy=who(pr.get("mergedBy")))
    out["reviews"] = [dict(r, author=who(r.get("author"))) for r in pr.get("reviews") or []]
    return out


def minimise_commit(c: dict) -> dict:
    """Keep what the checks use; drop the author's name and email that the commits API returns."""
    return {"sha": c.get("sha"), "parents": [{"sha": p.get("sha")} for p in c.get("parents") or []],
            "verified": bool(((c.get("commit") or {}).get("verification") or {}).get("verified")),
            "author": (c.get("author") or {}).get("login"), "date": ((c.get("commit") or {}).get("committer")
                                                                      or {}).get("date")}


def minimise_run(r: dict) -> dict:
    """Keep what the checks use; drop the head commit's author name and email."""
    return {k: r.get(k) for k in ("id", "name", "event", "conclusion", "status", "created_at", "head_sha",
                                  "head_branch", "html_url")} | {"actor": (r.get("actor") or {}).get("login")}


def mainline(commits: list[dict]) -> list[dict]:
    """The first-parent chain from the newest listed commit: what was pushed or merged onto the branch.

    Commits that reached the branch as the second parent of a merge are checked through that merge."""
    by_sha = {c.get("sha"): c for c in commits}
    chain, sha = [], commits[0].get("sha") if commits else None
    while sha in by_sha and len(chain) < len(by_sha):
        chain.append(by_sha[sha])
        parents = by_sha[sha].get("parents") or []
        sha = parents[0].get("sha") if parents else None
    return chain


def retention_gap(retention_days: int | None, since: dt.date, today: dt.date) -> int:
    """Days at the start of the period whose workflow logs GitHub has already deleted."""
    if retention_days is None:
        return 0
    oldest_kept = today - dt.timedelta(days=retention_days)
    return max(0, (oldest_kept - since).days)


# ---------- gathering ----------

def gather_all(gh: Gh, repo: str, since: str, until: str, environment: str | None,
               emergency: set[str], incident_labels: list[str], max_lookups: int,
               today: dt.date, bots: set[str] = frozenset(KNOWN_BOTS)) -> Pack:
    """Gather every area. Raises GhError when the repository itself can't be read (signed out, no access)."""
    pack = Pack()
    meta = gh.api(f"repos/{repo}") or {}
    pack.evidence["repo"] = {"meta": meta}
    branch = meta.get("default_branch") or "main"

    # Access management (SOX-AC): who can administer, merge, bypass and deploy.
    collabs = pack.gather("access", "collaborators",
                          lambda: gh.api(f"repos/{repo}/collaborators?affiliation=all&per_page=100", True), [])
    pack.evidence["access"]["listing"] = access_listing(collabs)
    keys = pack.gather("access", "deploy_keys", lambda: gh.api(f"repos/{repo}/keys?per_page=100", True), [])
    for key in keys or []:
        if not key.get("read_only"):
            pack.flag("SOX-AC7", "Medium", f"deploy key {key.get('title', key.get('id'))}",
                      "write access without a named person; review and rotate or make read-only")
    pack.gather("access", "teams", lambda: gh.api(f"repos/{repo}/teams?per_page=100", True), [])

    # Change management (SOX-CM): settings, the population of merged PRs, direct pushes.
    pack.evidence["change"] = {}
    protection, assessable = None, True
    try:
        protection = gh.api(f"repos/{repo}/branches/{branch}/protection")
    except GhError as exc:
        # "Branch not protected" is evidence; any other error (no admin, signed out) means unknown.
        if "not protected" not in str(exc).lower():
            assessable = False
            pack.gaps.append(f"change/branch_protection: not gathered ({exc}); branch controls not "
                             "assessed (reading classic protection needs admin)")
    pack.evidence["change"]["branch_protection"] = protection
    rules = pack.gather("change", "branch_rules",
                        lambda: gh.api(f"repos/{repo}/rules/branches/{branch}?per_page=100", True), None)
    if rules is None:
        assessable = assessable and bool(protection)
    controls = branch_controls(protection, rules)
    pack.evidence["change"]["controls"] = controls
    if assessable:
        check_branch_controls(pack, branch, controls)
    for rs_id in sorted({r.get("ruleset_id") for r in rules or [] if r.get("ruleset_id")}):
        rs = pack.gather("change", f"ruleset_{rs_id}", lambda i=rs_id: gh.api(f"repos/{repo}/rulesets/{i}"), {}) or {}
        for actor in rs.get("bypass_actors") or []:
            pack.flag("SOX-AC7", "Medium", f"ruleset {rs.get('name', rs_id)}",
                      f"bypass allowed for {actor.get('actor_type')} {actor.get('actor_id')} ({actor.get('bypass_mode')})")

    prs = pack.gather("change", "merged_prs", lambda: gh.cli([
        "pr", "list", "--repo", repo, "--base", branch, "--state", "merged", "--limit", str(PRS_CAP),
        "--search", f"merged:{since}..{until}",
        # headRefOid, not commits: commits x reviews for 1000 PRs exceeds GraphQL's node limit.
        "--json", "number,title,author,reviews,mergedBy,mergedAt,mergeCommit,labels,headRefOid,url"]), []) or []
    prs = [minimise_pr(p) for p in prs]
    pack.evidence["change"]["merged_prs"] = prs
    pr_rows = check_change(pack, prs, emergency, bots)
    pack.evidence["change"]["merged_pr_rows"] = pr_rows
    if len(prs) >= PRS_CAP:
        pack.gaps.append(f"change/merged_prs: {PRS_CAP} PRs listed (the cap); split the period")
    pr_by_commit = {r["merge_commit"]: r["number"] for r in pr_rows if r["merge_commit"]}

    commits = pack.gather("change", "default_branch_commits", lambda: gh.api(
        f"repos/{repo}/commits?sha={branch}&since={since}T00:00:00Z&until={until}T23:59:59Z&per_page=100",
        True), []) or []
    commits = [minimise_commit(c) for c in commits]
    pack.evidence["change"]["default_branch_commits"] = commits
    lookups = 0

    def pr_for(sha: str):
        nonlocal lookups
        if sha in pr_by_commit:
            return pr_by_commit[sha]
        if lookups >= max_lookups:
            return "unchecked"
        lookups += 1
        try:
            pulls = gh.api(f"repos/{repo}/commits/{sha}/pulls")
        except GhError as exc:
            pack.gaps.append(f"change/commit {sha[:12]}: PR lookup failed ({exc})")
            return "unchecked"
        merged = [p["number"] for p in pulls or [] if p.get("merged_at")]
        pr_by_commit[sha] = merged[0] if merged else None
        return pr_by_commit[sha]

    unsigned = sum(not c["verified"] for c in commits)
    # Only the first-parent chain: a feature-branch commit reached main through its merge commit, which
    # is checked here like any other (a local `git merge` pushed to main has no PR and is flagged).
    for c in mainline(commits):
        sha = c.get("sha", "")
        if pr_for(sha) is None:
            pack.flag("SOX-CM8", "High", f"commit {sha[:12]}", f"on {branch} with no merged pull request")
    if lookups >= max_lookups:
        pack.gaps.append(f"change/commits: stopped PR lookups at {max_lookups}; raise --max-lookups")
    pack.evidence["change"]["unsigned_commits"] = unsigned
    if commits and unsigned:
        pack.flag("SOX-EVD3", "Info", f"branch {branch}",
                  f"{unsigned} of {len(commits)} commits not signature-verified")

    # Deployment (SOX-CM4, CM9, SOD1): who can deploy, and what was deployed from where.
    envs = pack.gather("deploy", "environments", lambda: gh.api(f"repos/{repo}/environments?per_page=100", True), [])
    env_rows = [check_environment(pack, e) for e in envs or []
                if environment is None or e.get("name") == environment]
    pack.evidence["deploy"]["environment_rows"] = env_rows
    if not env_rows:
        pack.gaps.append("deploy: no matching GitHub environment; gather who can deploy from the deploy tool")
    for env in env_rows:
        quoted = urllib.parse.quote(env["name"], safe="")
        deps = pack.gather("deploy", f"deployments_{env['name']}", lambda q=quoted: gh.api(
            f"repos/{repo}/deployments?environment={q}&per_page=100", True), []) or []
        for d in deps:
            if not (since <= (d.get("created_at") or "")[:10] <= until):
                continue
            if pr_for(d.get("sha", "")) is None:
                pack.flag("SOX-CM9", "High", f"deployment {d.get('id')} to {env['name']}",
                          f"deployed commit {d.get('sha', '')[:12]} has no merged pull request")
    pack.gather("deploy", "releases", lambda: gh.api(f"repos/{repo}/releases?per_page=100", True), [])

    # Operations (SOX-OPS): job failures and incident records.
    runs = pack.gather("operations", "workflow_runs", lambda: gh.api(
        f"repos/{repo}/actions/runs?created={since}..{until}&per_page=100", True), []) or []
    runs = [minimise_run(r) for r in runs]
    pack.evidence["operations"]["workflow_runs"] = runs
    if len(runs) >= RUNS_CAP:
        pack.gaps.append(f"operations/workflow_runs: the API returns at most {RUNS_CAP} runs per query; "
                         "run the pack per month for complete job evidence")
    pack.evidence["operations"]["workflow_rows"] = check_runs(pack, runs)
    incidents: list = []
    for label in incident_labels:
        found = pack.gather("operations", f"incidents_{label}", lambda lbl=label: gh.cli([
            "issue", "list", "--repo", repo, "--state", "all", "--label", lbl, "--limit", str(INCIDENTS_CAP),
            "--search", f"created:{since}..{until}",
            "--json", "number,title,state,createdAt,closedAt,closedByPullRequestsReferences,url"]), []) or []
        if len(found) >= INCIDENTS_CAP:
            pack.gaps.append(f"operations/incidents_{label}: {INCIDENTS_CAP} issues listed (the cap); split the period")
        incidents += found
    for issue in incidents:
        if issue.get("state") == "CLOSED" and not issue.get("closedByPullRequestsReferences"):
            pack.flag("SOX-OPS3", "Low", f"incident #{issue.get('number')}", "closed with no linked fixing PR")
    pack.gaps.append("operations: backups and restore tests are not in GitHub; collect them from the "
                     "cloud account (e.g. DynamoDB PITR status, backup job logs)")

    # Audit evidence (SOX-EVD): can it still be produced?
    retention = pack.gather("evidence", "log_retention",
                            lambda: gh.api(f"repos/{repo}/actions/permissions/artifact-and-log-retention"), {}) or {}
    lost = retention_gap(retention.get("days"), dt.date.fromisoformat(since), today)
    if lost:
        pack.flag("SOX-EVD2", "Medium", "workflow logs",
                  f"logs are kept {retention.get('days')} days, so the first {lost} days of the period "
                  "are gone; export logs at least that often")
    return pack


# ---------- output ----------

def render_summary(pack: Pack, repo: str, since: str, until: str, generated: str) -> str:
    ex = sorted(pack.exceptions, key=lambda e: (SEVERITY_ORDER.get(e["severity"], 9), e["id"]))
    counts = {s: sum(e["severity"] == s for e in ex) for s in SEVERITY_ORDER}
    lines = [f"# SOX ITGC evidence pack — {repo}", "",
             f"_Period: {since} to {until} · Generated: {generated} · Read-only GitHub API evidence; "
             "not an audit opinion._", "",
             "Exceptions: " + " · ".join(f"{s} {n}" for s, n in counts.items()), "",
             "## Exceptions", "", "| Severity | SOX item | Item | Detail |", "|---|---|---|---|"]
    lines += [f"| {e['severity']} | {e['id']} | {e['item']} | {e['detail']} |" for e in ex] or ["| – | – | none | – |"]
    listing = pack.evidence.get("access", {}).get("listing", {})
    lines += ["", "## Access listing (for the periodic access review)", "",
              "| Role | Logins |", "|---|---|"]
    lines += [f"| {role} | {', '.join(who) or '–'} |" for role, who in listing.items()]
    envs = pack.evidence.get("deploy", {}).get("environment_rows", [])
    lines += ["", "## Who can deploy", "", "| Environment | Required reviewers | Prevent self-review | Branch policy |",
              "|---|---|---|---|"]
    lines += [f"| {e['name']} | {', '.join(e['reviewers']) or '–'} | {e['prevent_self_review']} | "
              f"{'set' if e['branch_policy'] else 'none'} |" for e in envs] or ["| – | – | – | – |"]
    prs = pack.evidence.get("change", {}).get("merged_pr_rows", [])
    lines += ["", f"## Change population ({len(prs)} merged PRs)", "",
              "| PR | Author | Approvers | Merged by | Merged at | Emergency |", "|---|---|---|---|---|---|"]
    lines += [f"| #{p['number']} | {p['author']} | {', '.join(p['approvers'] + p['retro_approvers']) or '–'} | "
              f"{p['merged_by']} | {p['merged_at']} | {'yes' if p['emergency'] else ''} |" for p in prs]
    lines += ["", "## Gaps (not gathered)", ""] + [f"- {g}" for g in pack.gaps] + [
        "", "## Keeping this evidence", "",
        "Store this folder in write-once storage (object lock or WORM) for the retention period, and "
        "check it later with `sha256sum -c MANIFEST.sha256`.", ""]
    return "\n".join(lines)


def write_pack(pack: Pack, out: pathlib.Path, summary: str) -> list[pathlib.Path]:
    out.mkdir(parents=True, exist_ok=True)
    files = []
    for area, data in sorted(pack.evidence.items()):
        path = out / f"{area}.json"
        path.write_text(json.dumps(data, indent=1, sort_keys=True, default=str) + "\n")
        files.append(path)
    (out / "exceptions.json").write_text(json.dumps(pack.exceptions, indent=1) + "\n")
    (out / "summary.md").write_text(summary)
    files += [out / "exceptions.json", out / "summary.md"]
    manifest = "".join(f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}\n" for p in files)
    (out / "MANIFEST.sha256").write_text(manifest)
    return files


def parse_args(argv: list[str]) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Gather a read-only SOX ITGC evidence pack from GitHub.")
    ap.add_argument("--repo", help="OWNER/NAME (default: the current directory's repo)")
    ap.add_argument("--since", required=True, help="period start, YYYY-MM-DD")
    ap.add_argument("--until", help="period end, YYYY-MM-DD (default: today)")
    ap.add_argument("--out", help="output folder (default: ~/.claude/security-reports/<repo>/sox-evidence/"
                                  "<since>_<until>, outside the working tree, since the pack names people)")
    ap.add_argument("--environment", help="only this deployment environment (default: all)")
    ap.add_argument("--emergency-label", action="append", default=None,
                    help="label marking emergency changes (repeatable; default: emergency, hotfix)")
    ap.add_argument("--incident-label", action="append", default=None,
                    help="label marking incident issues (repeatable; default: incident)")
    ap.add_argument("--bot", action="append", default=[],
                    help="another login whose approvals don't count (repeatable; [bot] logins and well-known "
                         "bots are always excluded)")
    ap.add_argument("--max-lookups", type=int, default=200, help="cap on per-commit PR lookups")
    args = ap.parse_args(argv)
    args.until = args.until or dt.date.today().isoformat()
    args.emergency_label = args.emergency_label or ["emergency", "hotfix"]
    args.incident_label = args.incident_label or ["incident"]
    for d in (args.since, args.until):
        try:
            dt.date.fromisoformat(d if DATE_RE.fullmatch(d) else "bad")
        except ValueError:
            ap.error(f"not a YYYY-MM-DD date: {d!r}")
    if args.since > args.until:
        ap.error("--since is after --until")
    if args.repo and not REPO_RE.fullmatch(args.repo):
        ap.error(f"not OWNER/NAME: {args.repo!r}")
    if args.environment and not LABEL_RE.fullmatch(args.environment):
        ap.error(f"bad environment name: {args.environment!r}")
    for lbl in args.emergency_label + args.incident_label + args.bot:
        if not LABEL_RE.fullmatch(lbl):
            ap.error(f"bad label: {lbl!r}")
    if args.max_lookups < 0:
        ap.error("--max-lookups must be 0 or more")
    return args


def main(argv: list[str] | None = None, gh: Gh | None = None, today: dt.date | None = None) -> int:
    try:
        args = parse_args(sys.argv[1:] if argv is None else argv)
    except SystemExit as exc:
        return 2 if exc.code else 0
    gh = gh or Gh()
    try:
        repo = args.repo or gh.cli(["repo", "view", "--json", "nameWithOwner"])["nameWithOwner"]
    except (GhError, KeyError, TypeError) as exc:
        print(f"sox_evidence: cannot find the repository with gh ({exc})", file=sys.stderr)
        return 2
    today = today or dt.date.today()
    try:
        pack = gather_all(gh, repo, args.since, args.until, args.environment,
                          {lbl.lower() for lbl in args.emergency_label}, args.incident_label,
                          args.max_lookups, today, KNOWN_BOTS | {b.lower() for b in args.bot})
    except GhError as exc:
        print(f"sox_evidence: cannot read {repo} with gh; check `gh auth status` ({exc})", file=sys.stderr)
        return 2
    out = pathlib.Path(args.out or pathlib.Path.home() / ".claude" / "security-reports" / repo.split("/")[1]
                       / "sox-evidence" / f"{args.since}_{args.until}")
    generated = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    write_pack(pack, out, render_summary(pack, repo, args.since, args.until, generated))
    sev = {s: sum(e["severity"] == s for e in pack.exceptions) for s in SEVERITY_ORDER}
    print(f"Evidence pack: {out}/ · exceptions " + " ".join(f"{s}:{n}" for s, n in sev.items())
          + f" · gaps: {len(pack.gaps)}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
