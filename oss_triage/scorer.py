"""Score issues: difficulty (hardness) and good-first-issue confidence.

A score is a transparent sum over a neutral baseline plus named, weighted
signals. This makes every recommendation explainable -- the dashboard shows the
signals, not just a number.

All functions are pure and operate on Issue (or plain dicts via
Issue.from_github); no network, no I/O.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .models import Issue, Signal, DifficultyLevel, Candidate
from . import signals


# Clamp so scores stay in [0, 100].
def _clamp(x: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, x))


@dataclass
class IssueTriage:
    number: int
    title: str
    difficulty: float
    difficulty_level: DifficultyLevel
    gfi_confidence: float
    is_good_first_issue: bool
    signals: list = field(default_factory=list)
    gfi_signals: list = field(default_factory=list)
    skills: set = field(default_factory=set)
    doc_links: list = field(default_factory=list)
    html_url: str = ""
    state: str = "open"

    @property
    def recommendation(self) -> str:
        if self.is_good_first_issue and self.difficulty <= 45:
            return "Strong candidate: reachable and actionable for a newcomer."
        if self.gfi_confidence >= 60:
            return "Worth a look; add a doc link / acceptance criteria."
        if self.difficulty_level in (DifficultyLevel.HARD,
                                    DifficultyLevel.MEDIUM):
            return "Skip for newcomers: scope is significant."
        return "Open, but unclear value or effort."

    def as_dict(self) -> dict:
        return {
            "number": self.number,
            "title": self.title,
            "html_url": self.html_url,
            "state": self.state,
            "difficulty": round(self.difficulty, 1),
            "difficulty_level": self.difficulty_level.value,
            "gfi_confidence": round(self.gfi_confidence, 1),
            "is_good_first_issue": self.is_good_first_issue,
            "skills": sorted(self.skills),
            "doc_links": self.doc_links,
            "signals": [s.as_row() for s in self.signals],
            "gfi_signals": [s.as_row() for s in self.gfi_signals],
            "recommendation": self.recommendation,
        }


def score_issue(issue: Issue) -> IssueTriage:
    """Compute a full triage for a single issue.

    difficulty: 0 (trivial) .. 100 (hard).
    gfi_confidence: 0 .. 100 (confidence it suits a new contributor).
    """
    cs = signals.complexity_signals(issue)
    gs = signals.gfi_signals(issue)
    diff_raw = signals.base_score() + sum(s.weight for s in cs)
    gfi_raw = signals.base_score() + sum(s.weight for s in gs)
    difficulty = _clamp(diff_raw)
    gfi = _clamp(gfi_raw)

    # A good-first-issue is *reachable*: not too hard AND has a positive
    # newcomer signal OR an explicit gfi label.
    has_explicit = any(s.name == "gfi-label" for s in gs)
    pos_signal = any(s.weight > 0 for s in gs)
    is_gfi = difficulty <= 45 and (has_explicit or pos_signal)

    return IssueTriage(
        number=issue.number,
        title=issue.title,
        difficulty=difficulty,
        difficulty_level=DifficultyLevel.from_score(difficulty),
        gfi_confidence=gfi,
        is_good_first_issue=is_gfi,
        signals=cs,
        gfi_signals=gs,
        skills=signals.infer_skills(issue),
        doc_links=signals.extract_doc_links(issue.body, issue.html_url),
        html_url=issue.html_url,
        state=issue.state,
    )


def triage(issues, only_good_first: bool = True) -> list:
    results = [score_issue(i) for i in issues]
    if only_good_first:
        results.sort(key=lambda t: (
            not t.is_good_first_issue,
            -t.gfi_confidence,
            t.number,
        ))
    return results


# --- candidate matching -----------------------------------------------------
def _overlap(a: set, b: set) -> float:
    """Jaccard affinity (0..1). 0 when either set is empty, so an empty
    profile never looks like a perfect match."""
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


def match_issue(issue_triaged, candidates) -> list:
    """Rank contributors by skill affinity to one triaged issue.

    Returns (candidate, affinity) pairs sorted by affinity desc, ties broken by
    past_merges desc.
    """
    ranked = []
    for c in candidates:
        affinity = _overlap(c.normalize_skills(), issue_triaged.skills)
        merges = getattr(c, "past_merges", 0)
        ranked.append((c, affinity, merges))
    ranked.sort(key=lambda p: (-p[1], -p[2]))
    return [(c, affinity) for (c, affinity, _m) in ranked]


rank_for_candidate = match_issue
