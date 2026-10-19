# oss-triage

Heuristic triage advisor for OSS maintainers. It scores open issues for
**good-first-issue** potential and flags **AI-generated / low-quality pull
requests** for human review. Zero third-party runtime dependencies; the engine
operates on plain GitHub-REST JSON.

> Every output is a **heuristic score**, an *advisor for human triage*, **not a
> verdict**. A flag never blocks a merge -- it only routes a PR to a human.

## Features

- **Issue triage** -- difficulty tiering (trivial / easy / medium / hard /
  unknown) and a good-first-issue confidence score.
- **Contributor matching** -- rank open contributors by skill affinity to each
  issue.
- **PR verdicts** -- an AI-slop / quality filter that flags vague, oversized, or
  first-time-submitted PRs for review.
- **Three modes** -- `demo` (bundled fixtures), `file` (local JSON), `repo`
  (opt-in live fetch via HTTPS only).
- **Self-contained reports** -- machine-readable JSON and a zero-dependency HTML
  dashboard.

## Requirements

Python 3.10+. No install needed to run from a checkout.

## Install

    pip install .             # or: pip install -e .
    # or just run in place:
    python3 -m oss_triage demo

## Usage

    # bundled example fixtures
    oss-triage demo

    # local JSON fixtures
    oss-triage file examples/issues.json --prs examples/pulls.json --contributors examples/contributors.json

    # opt-in live fetch (HTTPS only). Set a read-only token first.
    export GITHUB_TOKEN=ghp_readonly_...      # read-only, repo-scope only
    oss-triage repo owner/repo

    # write artifacts (contained to the current directory unless --allow-outside)
    oss-triage demo --json triage.json --dashboard dashboard.html

    # smoke-test the output-path guard
    oss-triage guard some/path

## Modes

| Mode | What it does | Network |
| --- | --- | --- |
| `demo` | Run on the bundled `examples/*.json`. | none |
| `file` | Triage local GitHub-REST JSON fixtures. | none |
| `repo` | Fetch live issues/PRs from GitHub. **HTTPS only.** | yes (opt-in) |
| `guard` | Smoke-test the output-path containment guard. | none |

## Security

oss-triage never executes user-supplied content, never leaks a GitHub token to
logs or disk, and refuses to write artifacts outside the current working
directory. See `SECURITY.md` for the full threat model.

## Testing

    python3 -m pytest             # or: python3 -m unittest discover -s tests

## License

MIT. See `LICENSE`.
