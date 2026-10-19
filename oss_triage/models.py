"""Data models for issues, pull requests, candidates, and signals.

These are plain, network-free structures. ``from_github`` classmethods know how
to read a GitHub REST payload (the ``GET /repos/{o}/{r}/issues`` and
``/pulls`` shapes), so the engine can be fed either live payloads or JSON
fixtures.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


# ---------------------------------------------------------------------------
# Enums / small vocabulary
# ---------------------------------------------------------------------------
class DifficultyLevel(str, Enum):
    TRIVIAL = "trivial"
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"
    UNKNOWN = "unknown"

    @classmethod
    def from_score(cls, score: float) -> "DifficultyLevel":
        # score: 0 (easy) .. 100 (hard)
        if not isinstance(score, (int, float)):
            return cls.UNKNOWN
        if score < 20:
            return cls.TRIVIAL
        if score < 45:
            return cls.EASY
        if score < 70:
            return cls.MEDIUM
        return cls.HARD


# A small curated set of labels maintainers use (labels can be arbitrary in
# GitHub; this just gives the default heuristics something to key off).
GFI_LABELS = {
    "good first issue", "beginner friendly", "first-timers-only",
    "help wanted", "good-first-issue", "beginner",
}
HARD_LABELS = {"hard", "advanced", "needs-design", "discussion"}


# ---------------------------------------------------------------------------
# Generic "labelled thing"
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Signal:
    """One piece of evidence used to compute a score.

    Carries the *why* so a dashboard can be transparent: every score is a sum of
    named, weighted, auditable signals.
    """
    name: str
    weight: float
    detail: str = ""

    def as_row(self) -> dict:
        return {"name": self.name, "weight": round(self.weight, 3),
                "detail": self.detail}


@dataclass(frozen=True)
class Labeled:
    raw: str
    normalized: str

    @staticmethod
    def parse(labels: Any) -> list["Labeled"]:
        out: list[Labeled] = []
        for item in labels or []:
            raw = item.get("name", item if isinstance(item, str) else "")
            out.append(Labeled(raw=raw, normalized=raw.lower()))
        return out


# ---------------------------------------------------------------------------
# Issue
# ---------------------------------------------------------------------------
@dataclass
class Issue:
    number: int
    title: str
    body: str
    state: str = "open"
    labels: list[Labeled] = field(default_factory=list)
    comments: int = 0
    created_at: str = ""
    html_url: str = ""
    user: dict = field(default_factory=dict)
    # raw GitHub payload is kept so downstream code needn't reparse
    raw: dict = field(default_factory=dict, repr=False)

    @property
    def label_set(self) -> set[str]:
        return {l.normalized for l in self.labels}

    @classmethod
    def from_github(cls, p: dict) -> "Issue":
        labels = Labeled.parse(p.get("labels", []))
        user = p.get("user", {}) or {}
        return cls(
            number=int(p.get("number", 0)),
            title=p.get("title", ""),
            body=(p.get("body") or ""),
            state=p.get("state", "open"),
            labels=labels,
            comments=int((p.get("comments") or 0)),
            created_at=p.get("created_at", "") or "",
            html_url=p.get("html_url", "") or "",
            user=user,
            raw=p,
        )


# ---------------------------------------------------------------------------
# Pull request
# ---------------------------------------------------------------------------
@dataclass
class PullRequest:
    number: int
    title: str
    body: str
    state: str = "open"
    labels: list[Labeled] = field(default_factory=list)
    comments: int = 0
    created_at: str = ""
    html_url: str = ""
    user: dict = field(default_factory=dict)
    # Diff / change facts (populated by github_fetch when available).
    additions: int = 0
    deletions: int = 0
    changed_files: int = 0
    files: list[dict] = field(default_factory=list)
    # The body of each review comment / the PR "reviews" summary, optional.
    reviews: list[dict] = field(default_factory=list)
    # Whether the author is a first-time contributor to this repo.
    first_time: bool = False
    raw: dict = field(default_factory=dict, repr=False)

    @property
    def lines_changed(self) -> int:
        return int(self.additions) + int(self.deletions)

    @property
    def has_tests(self) -> bool:
        names = [str(f.get("filename", "")).lower() for f in self.files]
        return any(
            n.startswith("test") or n.startswith("tests/")
            or n.endswith(".test.") or "__test__" in n or "/specs/" in n
            for n in names)

    @classmethod
    def from_github(cls, p: dict) -> "PullRequest":
        labels = Labeled.parse(p.get("labels", []))
        user = p.get("user", {}) or {}
        return cls(
            number=int(p.get("number", 0)),
            title=p.get("title", ""),
            body=(p.get("body") or ""),
            state=p.get("state", "open"),
            labels=labels,
            comments=int((p.get("comments") or 0)),
            created_at=p.get("created_at", "") or "",
            html_url=p.get("html_url", "") or "",
            user=user,
            additions=int((p.get("additions") or 0)),
            deletions=int((p.get("deletions") or 0)),
            changed_files=int((p.get("changed_files") or 0)),
            raw=p,
        )


# ---------------------------------------------------------------------------
# Candidate contributor
# ---------------------------------------------------------------------------
@dataclass
class Candidate:
    """A prospective contributor profile, in the shape a dashboard can match to
    issues by skill / area.

    ``skills`` is a free-form set of normalized tokens (languages, areas,
    frameworks). Affinity is computed by overlap with an issue's inferred area.
    """
    handle: str
    skills: set[str] = field(default_factory=set)
    past_merges: int = 0
    past_issues: int = 0
    # optional: last active / timezone — used only for tie-breaks.
    note: str = ""

    def normalize_skills(self) -> set[str]:
        return {s.lower() for s in self.skills if s}
