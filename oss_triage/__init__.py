"""oss_triage: triage help for open-source maintainers.

It does two things:

1. **Issue triage** -- score open issues by *difficulty* and *good-first-issue*
    potential, link each to the docs that make it approachable, and rank the ones
    a new contributor is most likely to land.

2. **Pull-request triage** -- surface *low-effort / likely-copy-paste /
    "AI-slop"* PRs that need a human, by measuring signals like diff breadth,
    test coverage, relatedness to an issue, and tell-tale boilerplate.

Design constraints:

* Zero third-party runtime dependencies. The engine works on plain dictionaries
    (GitHub REST JSON, or fixtures) so it is fully unit-testable offline.
* No network unless you opt in. The GitHub REST layer (``github_fetch``) is an
    optional stdlib ``urllib`` client; tokens come from the environment and are
    never logged.
* Heuristics are *advisors for human triage*, not verdicts. Every output is
    labeled as a heuristic score, never a final call.
"""
from __future__ import annotations

__version__ = "0.1.0"

from .models import (
    Issue,
    PullRequest,
    DifficultyLevel,
    Candidate,
    Signal,
    Labeled,
)

__all__ = [
    "Issue",
    "PullRequest",
    "DifficultyLevel",
    "Candidate",
    "Signal",
    "Labeled",
    "__version__",
]
