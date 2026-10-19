"""Output renderers: JSON, Markdown summary, and an HTML dashboard.

Pure, no I/O.  ``dashboard_html`` takes triaged issues, optional PR verdicts, and
optional candidate rankings and renders a single self-contained HTML page
(zero external assets -- safe to open locally or commit to a repo).
"""
from __future__ import annotations
import html

from .scorer import IssueTriage
from .ai_signal import PRVerdict


def triage_to_json(issues, prs=None, candidates=None, version="0.1.0") -> dict:
    out = {"tool": "oss-triage", "version": version,
        "note": "Heuristics for human triage. Scores and flags are "
                    "advisory, not verdicts.",
        "issues": [i.as_dict() for i in issues]}
    if prs is not None:
        out["pull_requests"] = [p.as_dict() for p in prs]
    if candidates is not None:
        cands = []
        for c in candidates:
            cands.append({"handle": c.handle,
                "skills": sorted(c.normalize_skills()),
                "past_merges": c.past_merges})
        out["candidates"] = cands
    return out


def markdown_summary(issues, prs=None) -> str:
    lines = []
    gfi = [i for i in issues if i.is_good_first_issue]
    review = [p for p in (prs or []) if p.needs_review]
    lines.append("## Triage summary")
    lines.append("")
    lines.append(f"- **{len(issues)}** issues scored, "
        f"**{len(gfi)}** flagged as good-first-issue candidates.")
    if prs:
        lines.append(f"- **{len(review)}** of {len(prs)} pull requests "
            "flagged for extra human review.")
    lines.append("")
    if gfi:
        lines.append("### Good-first-issue candidates")
        for i in gfi[:10]:
            lines.append(f"- **#{i.number}** {i.title} "
                f"(difficulty {i.difficulty:.0f}, "
                f"confidence {i.gfi_confidence:.0f}) -- {i.recommendation}")
    if prs and review:
        lines.append("")
        lines.append("### Pull requests to watch")
        for p in review[:10]:
            lines.append(f"- **{p.number}** {p.title} "
                f"(risk {p.risk:.0f}) -- {p.reason}")
    return "\n".join(lines) + "\n"


# --- HTML dashboard ---------------------------------------------------------
def _esc(s) -> str:
    return html.escape(str(s), quote=True)

def _badge(text, kind) -> str:
    cls = {"good": "g", "watch": "w", "neutral": "n"}.get(kind, "n")
    return f'<span class="badge {cls}">{_esc(text)}</span>'

def _issue_row(it: IssueTriage, candidates=None, matches=None) -> str:
    matches_block = ""
    if matches:
        parts = []
        for c, aff in matches[:3]:
            if aff > 0:
                parts.append(f'<span class="cand">{_esc(c.handle)} '
                    f'({aff:.0%})</span>')
            if parts:
                matches_block = '<div class="matches">best matches: ' \
                    + " ".join(parts) + "</div>"
    level = it.difficulty_level.value
    kind = "good"
    if not it.is_good_first_issue:
        kind = "watch" if level in ("hard", "medium") else "neutral"
    rows = []
    for s in (it.signals + it.gfi_signals):
        r = s.as_row() if hasattr(s, "as_row") else s
        if abs(r["weight"]) >= 6:
            rows.append(r["name"])
    names = ", ".join(rows)
    sibs = names if names else "no strong signals"
    return (
        f'<tr class="{kind}">'
            f"<td class='num'>#{_esc(it.number)}</td>"
            f"<td class='title'>{_esc(it.title)}"
            f"<div class='rec'>{_esc(it.recommendation)}</div>"
            f"{matches_block}"
            f"<div class='sigs'>{_esc(sibs)}</div>"
        "</tr>")


def _pr_row(p: PRVerdict) -> str:
    kind = "watch" if p.needs_review else "neutral"
    _rows = []
    for _s in (getattr(p, "signals", []) or []):
        _r = _s.as_row() if hasattr(_s, "as_row") else _s
        _rows.append(_r["name"])
    names = ", ".join(_rows) or "no signals"
    return (
        f'<tr class="{kind}">'
            f"<td class='num'>#{_esc(p.number)}</td>"
            f"<td class='pr'>{_esc(p.title)}"
            f"<div class='rec'>{_esc(p.reason)}</div>"
            f"<div class='sigs'>{_esc(names)}</div>"
        "</tr>")


_CSS = """
body{font:15px/1.5 -apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;
max-width:1040px;margin:24px auto;padding:0 16px;color:#222}
h1{font-size:20px}h2{font-size:16px;margin-top:28px}
.note{background:#eef;border-radius:8px;padding:10px 14px;color:#334}
table{border-collapse:collapse;width:100%;margin-top:10px}
th,td{border:1px solid #dde;padding:8px 10px;vertical-align:top}
th{background:#f6f7f9;text-align:left}
.num{white-space:nowrap;font-variant-numeric:tabular-nums}
.title,.pr{font-weight:600}
.rec{margin-top:4px}.sigs{margin-top:6px;color:#667;font-size:13px}
.cand{display:inline-block;background:#eef3ff;border-radius:6px;
padding:1px 6px;margin:2px 4px 0 0;font-size:12px}
.matches{margin-top:4px;font-size:13px}
.badge{border-radius:6px;padding:1px 8px;font-size:12px}
.g{background:#1b7f4b;color:#fff}.w{background:#b45309;color:#fff}
.n{background:#cbd5e1;color:#111}
tr.good{background:#f6fff9}tr.watch{background:#fff7ed}
code{background:#f3f4f6;padding:1px 4px;border-radius:4px}
"""


def dashboard_html(issues, prs=None, candidates=None,
        repo: str = "", version: str = "0.1.0",
        include_matches: bool = False) -> str:
    matches_map = None
    if include_matches and candidates:
        from .scorer import match_issue
        matches_map = {i.number: match_issue(i, candidates) for i in issues}
    gfi = [i for i in issues if i.is_good_first_issue]
    watch = [p for p in (prs or []) if p.needs_review]
    issue_rows = []
    for i in issues:
        m = matches_map.get(i.number) if matches_map else None
        issue_rows.append(_issue_row(i, candidates, m))
    pr_rows = "".join(_pr_row(p) for p in (prs or []))
    cand_block = ""
    if candidates:
        items = []
        for c in candidates:
            sk = ", ".join(sorted(c.normalize_skills())) or "n/a"
            items.append(f"<li><b>{_esc(c.handle)}</b> "
                f"({c.past_merges} past merges; "
                f"skills: {_esc(sk)})</li>")
        cand_block = "<h2>Contributor candidates " \
            f"({len(candidates)})</h2><ol>" + "".join(items) + "</ol>"
    pr_section = ""
    if prs:
        pr_section = (f"<h2>Pull requests ({len(prs)}; "
            f"{len(watch)} to watch)</h2>"
            f"<table><tr><th>#</th><th>PR</th></tr>"
            + pr_rows + "</table>")
    head = (f"<!doctype html><html><head><meta charset='utf-8'>"
        f"<title>oss-triage dashboard -- {_esc(repo or 'repo')}</title>"
        f"<style>{_CSS}</style></head><body>")
    title = "oss-triage dashboard"
    if repo:
        title += f" - {_esc(repo)}"
    note = ("Heuristics for human triage -- scores and flags are advisory, not "
        f"verdicts. Generated by oss-triage {_esc(version)}.")
    badges = (_badge("gfi: " + str(len(gfi)), "good")
        + _badge("pr-watch: " + str(len(watch)), "watch")
        + _badge("issues: " + str(len(issues)), "neutral"))
    return (head
        + f"<h1>{_esc(title)}</h1>"
        + f"<div class='note'>{note}</div>"
        + f"<p>{badges}</p>"
        + f"<h2>Good-first-issue candidates ({len(gfi)})</h2>"
        + f"<table><tr><th>#</th><th>Issue</th></tr>"
        + "".join(issue_rows) + "</table>"
        + pr_section + cand_block + "</body></html>")
