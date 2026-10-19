"""Command-line entry point: demo / file / repo modes, all guarded."""
import argparse
import json
import os
import sys
from . import __version__
from .github_fetch import GHClient, GHError, load_json
from .scorer import triage, match_issue
from .ai_signal import triage_pr
from .models import Issue, PullRequest, Candidate
from .reports import dashboard_html, triage_to_json


class OutputGuardError(Exception):
    """Raised when an output path would escape the working directory."""
    pass


def guard_output(path, allow_outside=False):
    """Resolve a path, refusing traversal out of the CWD unless allowed."""
    if allow_outside:
        return os.path.abspath(path)
    cwd = os.getcwd()
    resolved = os.path.abspath(path)
    if os.path.commonpath([cwd, resolved]) != cwd:
        raise OutputGuardError(
            "refusing to write outside the working directory: %s" % path
        )
    return resolved


def run_demo(args=None):
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ex = os.path.join(base, "examples")
    issues = [Issue.from_github(o) for o in load_json(os.path.join(ex, "issues.json"))]
    prs = [PullRequest.from_github(o) for o in load_json(os.path.join(ex, "pulls.json"))]
    cands = [
        Candidate(handle=d.get("handle", "unknown"),
                  skills=d.get("skills", []),
                  past_merges=int(d.get("past_merges", 0)))
        for d in load_json(os.path.join(ex, "contributors.json"))
    ]
    results = triage(issues)
    matches = []
    for r in results:
        ranked = match_issue(r, cands)
        if ranked:
            matches.append((r.number, ranked[0][0].handle, round(ranked[0][1], 2)))
    verdicts = [triage_pr(p) for p in prs]
    _human(results, verdicts, cands, "example/oss-triage-issues", matches=matches)
    return 0


def _human(issues, verdicts, cands, name, matches=None):
    print()
    print("== %s ==" % name)
    print("%-7s %-7s %-4s %-6s %s" % ("issue", "diff", "gfi", "state", "title"))
    for i in issues:
        print("#%-5d %-7s %-4d %-6s %s" %
              (i.number, i.difficulty_level.value,
               int(i.gfi_confidence), i.state, i.title[:44]))
    if cands:
        print("\n-- contributors (%d) --" % len(cands))
        for c in cands:
            print("   %-9s skills=%s merges=%d" %
                  (c.handle, ",".join(c.skills or []), int(c.past_merges or 0)))
    if matches:
        print("\n-- best matches --")
        for num, who, aff in matches:
            print("   #%d -> %s (affinity %.2f)" % (num, who, aff))
    if verdicts:
        print("\n-- pull requests (verdicts; every one is human-reviewed) --")
        for p in verdicts:
            tag = "REVIEW" if p.needs_review else "ok"
            print("#%-5d [%-6s] risk=%2d %-40s %s" %
                  (p.number, tag, p.risk, ("" if p.reason == "no notable signals" else p.reason),
                   ("first-timer" if p.first_time else "")))
    return 0


def _cands_from(raws):
    out = []
    for d in raws:
        out.append(Candidate(
            handle=d.get("handle", "unknown"),
            skills=d.get("skills", []),
            past_merges=int(d.get("past_merges", 0))))
    return out


def cmd_file(args):
    issues = [Issue.from_github(o) for o in load_json(args.issues)]
    verdicts = []
    cands = None
    if args.prs:
        prs = [PullRequest.from_github(o) for o in load_json(args.prs)]
        verdicts = [triage_pr(p) for p in prs]
    if args.contributors:
        cands = _cands_from(load_json(args.contributors))
    results = triage(issues)
    matches = []
    if cands:
        for r in results:
            ranked = match_issue(r, cands)
            if ranked:
                matches.append((r.number, ranked[0][0].handle, round(ranked[0][1], 2)))
    _human(results, verdicts, cands, os.path.basename(args.issues), matches=matches)
    if getattr(args, "dashboard", None):
        _write(args.dashboard, dashboard_html(results, verdicts, cands,
                                             include_matches=bool(matches)), args)
    if getattr(args, "json", None):
        _write(args.json, json.dumps(triage_to_json(results, verdicts, cands), indent=2),
               args)
    return 0


def cmd_repo(args):
    client = GHClient(args.owner, args.repo)
    state = args.state or "open"
    results = triage(client.issues(state=state))
    verdicts = []
    if args.prs:
        for p in client.pulls(state=state):
            detail = client.pr_detail(p.number) if args.full else p
            verdicts.append(triage_pr(detail))
    _human(results, verdicts, None, args.owner + "/" + args.repo)
    if getattr(args, "dashboard", None):
        _write(args.dashboard, dashboard_html(results, verdicts), args)
    if getattr(args, "json", None):
        _write(args.json, json.dumps(triage_to_json(results, verdicts), indent=2), args)
    return 0


def cmd_guard(args):
    try:
        target = guard_output(args.path, getattr(args, "allow_outside", False))
    except OutputGuardError as e:
        print("blocked:", str(e))
        return 3
    print("ok: " + str(target))
    return 0


def _write(path, text, args):
    target = guard_output(path, getattr(args, "allow_outside", False))
    with open(target, "w", encoding="utf-8") as f:
        f.write(text)
    print("wrote %s (%d bytes)" % (target, len(text)))
    return target


def build_parser():
    p = argparse.ArgumentParser(
        prog="oss-triage",
        description="Good-first-issue matching and AI-generated PR verdicts.")
    p.add_argument("--version", action="version", version=__version__)
    sub = p.add_subparsers(dest="cmd")
    d = sub.add_parser("demo", help="run on the bundled example fixtures")
    d.set_defaults(func=run_demo)
    f = sub.add_parser("file", help="triage from local JSON fixtures")
    f.add_argument("issues", help="JSON file of GitHub issue objects")
    f.add_argument("--prs", metavar="PULLS.json",
                   help="optional JSON of pull requests to review")
    f.add_argument("--contributors", metavar="CANDS.json",
                   help="optional list of prior contributors to match")
    f.add_argument("--json", metavar="OUT.json",
                   help="also write structured JSON to OUT.json")
    f.add_argument("--dashboard", metavar="OUT.html",
                   help="also write an HTML dashboard to OUT.html")
    f.add_argument("--allow-outside", action="store_true",
                   help="permit writing outside the current directory")
    f.set_defaults(func=cmd_file)
    r = sub.add_parser("repo", help="fetch live from GitHub (opt-in network)")
    r.add_argument("owner", help="GitHub owner (user or org)")
    r.add_argument("repo", help="repository name")
    r.add_argument("--state", help="issue/PR state (default: open)")
    r.add_argument("--prs", action="store_true", help="also triage pull requests")
    r.add_argument("--full", action="store_true",
                   help="fetch full PR body + files (more API calls)")
    r.add_argument("--json", metavar="OUT.json",
                   help="also write structured JSON to OUT.json")
    r.add_argument("--dashboard", metavar="OUT.html",
                   help="also write an HTML dashboard to OUT.html")
    r.add_argument("--allow-outside", action="store_true",
                   help="permit writing outside the current directory")
    r.set_defaults(func=cmd_repo)
    g = sub.add_parser("guard", help="smoke-test the output-path guard")
    g.add_argument("path", help="candidate output path to validate")
    g.add_argument("--allow-outside", action="store_true")
    g.set_defaults(func=cmd_guard)
    return p


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "cmd", None):
        parser.print_help()
        return 1
    if args.cmd == "demo":
        return args.func(args)
    if args.cmd in ("file", "repo"):
        try:
            return args.func(args)
        except GHError as e:
            print("GitHub error: " + str(e), file=sys.stderr)
            return 2
    return args.func(args)
