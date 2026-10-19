"""Unit tests for the oss_triage engine (no network, stdlib unittest).

These mirror what the CLI actually does: parse, signal-extract, score, triage
issues, run the PR verdicts, and exercise the output guard. No network, no
disk writes.
"""
import os
import unittest

from oss_triage.models import (Issue, PullRequest, Candidate, Signal,
                          DifficultyLevel, Labeled)
from oss_triage import signals as S
from oss_triage import scorer as SC
from oss_triage import ai_signal as AI
from oss_triage import github_fetch as GF
from oss_triage.cli import guard_output, OutputGuardError


def _labels(*names):
    return [{"name": n} for n in names]


class ParseTests(unittest.TestCase):
    def test_issue_from_github(self):
        d = {"number": 1, "title": "x", "state": "open",
               "labels": _labels("good first issue", "bug"),
               "body": "repro A\nrepro B\nrepro C"}
        iss = Issue.from_github(d)
        self.assertEqual(iss.number, 1)
        self.assertIn("good first issue", [l.normalized for l in iss.labels])
        self.assertIn("bug", [l.normalized for l in iss.labels])

    def test_no_number_defaults_to_zero(self):
        self.assertEqual(Issue.from_github({}).number, 0)

    def test_labeled_parse(self):
        out = Labeled.parse([{"name": "good first issue"}, {"name": "Bug"}])
        self.assertEqual(out[0].normalized, "good first issue")
        self.assertEqual(out[1].normalized, "bug")

    def test_candidate_has_no_languages_field(self):
        c = Candidate(handle="alice", skills=["bug"], past_merges=3)
        self.assertEqual(c.handle, "alice")
        self.assertNotIn("languages", c.__dataclass_fields__)


class SignalTests(unittest.TestCase):
    def test_gfi_signals_present(self):
        iss = Issue.from_github({"number": 1, "title": "add feature x",
             "labels": _labels("good first issue"), "body": "repro a\nb\nc"})
        names = [s.name for s in S.gfi_signals(iss)]
        self.assertIn("gfi-label", names)

    def test_complexity_signals_are_signal_objects(self):
        iss = Issue.from_github({"number": 2, "title": "refactor core parser",
             "body": "rewrite the whole compiler"})
        sigs = S.complexity_signals(iss)
        self.assertTrue(all(isinstance(s, Signal) for s in sigs))


class ScorerTests(unittest.TestCase):
    def test_gfi_is_easy(self):
        iss = Issue.from_github({"number": 112, "title": "fix off-by-one",
             "labels": _labels("good first issue", "bug"),
             "body": "repro a\nb\nc"})
        r = SC.score_issue(iss)
        self.assertEqual(r.difficulty_level, DifficultyLevel.EASY)
        self.assertTrue(r.is_good_first_issue)
        self.assertGreater(r.gfi_confidence, 50)

    def test_hard_is_not_easy(self):
        iss = Issue.from_github({"number": 7, "title": "refactor auth to jwt",
             "body": "rewrite the auth subsystem"})
        r = SC.score_issue(iss)
        self.assertNotEqual(r.difficulty_level, DifficultyLevel.EASY)

    def test_triage_batch(self):
        a = Issue.from_github({"number": 1, "title": "x",
             "labels": _labels("good first issue"), "body": "a\nb\nc"})
        cands = [Candidate(handle="alice", skills=["bug"])]
        res = SC.triage([a], cands)
        self.assertEqual(len(res), 1)
        self.assertTrue(hasattr(res[0], "difficulty_level"))


class AISignalTests(unittest.TestCase):
    def test_clean_pr_not_flagged(self):
        pr = PullRequest(number=12, title="Add parser tests",
            body="Adds unit tests for the pagination bug.",
            additions=5, deletions=0, changed_files=1,
            files=[{"filename": "tests/test_parser.py"}], first_time=False)
        v = AI.triage_pr(pr, threshold=50.0)
        self.assertFalse(v.needs_review, v.reason)
        self.assertLess(v.risk, 50.0)

    def test_threshold_trips_flag(self):
        pr = PullRequest(number=9, title="random changes",
            body="here are a few changes i think might fix the issue "
                   "also tried to make it faster by doing something different",
            additions=300, deletions=100, changed_files=6,
            files=[{"filename": "src/a.py"}, {"filename": "core/b.py"}],
            first_time=True)
        high = AI.triage_pr(pr, threshold=50.0)
        low = AI.triage_pr(pr, threshold=10.0)
        self.assertFalse(high.needs_review)
        self.assertTrue(low.needs_review, low.reason)

    def test_triage_is_deterministic(self):
        pr = PullRequest(number=7, title="t", body="ok",
            additions=2, deletions=0, changed_files=1,
            files=[{"filename": "a.py"}])
        self.assertEqual(AI.triage_pr(pr).risk, AI.triage_pr(pr).risk)

    def test_verdict_has_reason(self):
        v = AI.triage_pr(PullRequest(number=5, title="t", body="ok"))
        self.assertTrue(hasattr(v, "needs_review"))
        self.assertIsInstance(v.reason, str)


class GuardTests(unittest.TestCase):
    def test_blocks_traversal(self):
        with self.assertRaises(OutputGuardError):
            guard_output("../../etc/passwd")

    def test_allows_local(self):
        out = guard_output("out.html")
        self.assertTrue(out.startswith(os.getcwd()))

    def test_allow_outside_bypasses(self):
        out = guard_output("/etc/passwd", allow_outside=True)
        self.assertEqual(out, os.path.abspath("/etc/passwd"))


class GithubFetchTests(unittest.TestCase):
    def test_redact_masks_secrets(self):
        s = "token=ghtoken123 secret=abcd Authorization: Bearer xyz http://x/y"
        red = GF._redact(s)
        for needle in ("token123", "abcd", "Bearer", "http://x/y"):
            self.assertNotIn(needle, red)

    def test_https_guard_rejects_plain_http(self):
        with self.assertRaises(GF.GHError):
            GF.GHClient("o", "r", base="http://insecure.example")


if __name__ == "__main__":
    import sys
    sys.exit(unittest.main())
