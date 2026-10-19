"""Pure signal extraction. No scoring, no network -- just turning an Issue or
PullRequest into a list of weighted Signal objects. Keep it pure: it is the
easiest part to unit test and the one most likely to be reused.

Weights are advisory: they encode maintainer intuition (a linked-doc reference
makes an issue easier), not a law of physics. The point is transparency -- every
score is a sum of named, displayed signals.
"""
from __future__ import annotations

import re
from typing import Any

from .models import Issue, Signal, GFI_LABELS, HARD_LABELS

# Markdown / bare URL for "does this issue point people at the docs?"
_URL_RE = re.compile(r"https?://[^\s)\]]+")
_MDLINK_RE = re.compile(r"\[[^\]]+\]\((https?://[^\s)]+)\)")

# Keywords that imply complexity / scope.
_SCOPE_WORDS = {
    "implement", "add", "support", "refactor", "redesign", "rewrite",
    "migrate", "optimize", "performance", "architect", "core", "major",
}
_SIMPLE_WORDS = {
    "typo", "docs", "documentation", "comment", "fix", "small", "minor",
    "cosmetic", "spelling", "example", "rename",
}

# Acceptance-criteria markers imply an issue a newcomer can finish.
_ACCEPTANCE_MARKERS = (
    "steps to reproduce", "expected behavior", "actual behavior",
    "reproduce", "expected:", "acceptance", "checklist", "- [ ]",
)

# A neutral baseline so 0 signal means "not easy", not "max easy".
_BASE = 40


# --- doc links --------------------------------------------------------------
def extract_doc_links(body: str, url: str = "") -> list[str]:
    found = list(_MDLINK_RE.findall(body or ""))
    seen = set(found)
    for m in _URL_RE.findall(body or ""):
        clean = m.rstrip(")")
        if clean not in seen:
            seen.add(clean)
            found.append(clean)
    return found


def has_doc_reference(body: str, url: str = "") -> bool:
    return bool(extract_doc_links(body, url))


# --- skill / area inference -------------------------------------------------
def infer_skills(issue_or_pr) -> set[str]:
    """Best-effort area/skill tokens from labels (language:/area:/...) and
    title. Deliberately conservative -- a small, auditable set."""
    skills: set[str] = set()
    for lab in getattr(issue_or_pr, "labels", []):
        n = lab.normalized
        for prefix in ("language:", "lang:", "area:", "component:",
                        "topic:", "skill:", "platform:", "ecosystem:"):
                if n.startswith(prefix):
                    token = n[len(prefix):].strip()
                    if token:
                        skills.add(token)
    for w in (issue_or_pr.title or "").lower().split():
        w = w.strip(".,:;()\"'")
        if w and w not in _SIMPLE_WORDS and w not in _SCOPE_WORDS and len(w) >= 5:
            skills.add(w)
    return skills


# --- complexity / good-first-issue signals ----------------------------------
def complexity_signals(issue: Issue) -> list[Signal]:
    signals: list[Signal] = []
    for lab in issue.labels:
        if lab.normalized in HARD_LABELS:
            signals.append(Signal(
                "hard-label", 25.0,
                f"label '{lab.raw}' signals advanced work"))
    body = (issue.body or "").lower()
    n_scope = sum(1 for w in _SCOPE_WORDS if w in body)
    signals.append(Signal(
        "scope-words", min(4.0, n_scope * 2.0),
        f"{n_scope} scope-implying word(s) in body"))
    if "architect" in body or "redesign" in body or "rewrite" in body:
        signals.append(Signal(
            "big-bang", 15.0, "body implies design/architecture work"))
    has_criteria = any(m in body for m in _ACCEPTANCE_MARKERS)
    if len(body) > 800 and not has_criteria:
        signals.append(Signal(
            "long-no-criteria", 8.0,
            "long body, no clear acceptance criteria"))
    elif has_criteria:
        signals.append(Signal(
            "has-criteria", -6.0, "clear acceptance criteria / repro present"))
    return signals


def gfi_signals(issue: Issue) -> list[Signal]:
    signals: list[Signal] = []
    for lab in issue.labels:
        if lab.normalized in GFI_LABELS:
            signals.append(Signal(
                "gfi-label", 30.0,
                f"label '{lab.raw}' welcomes newcomers"))
    if issue.comments == 0 and (not issue.body or len(issue.body) < 120):
        signals.append(Signal(
            "thin-body", 3.0,
            "very thin body -- under-specified for a newcomer"))
    if has_doc_reference(issue.body, issue.html_url):
        signals.append(Signal(
            "has-doc-link", 12.0,
            "issue references documentation a newcomer can follow"))
    if any(m in (issue.body or "").lower() for m in _ACCEPTANCE_MARKERS):
        signals.append(Signal(
            "actionable-criteria", 10.0,
            "clear acceptance criteria / repro present"))
    return signals


def base_score() -> int:
    return _BASE
