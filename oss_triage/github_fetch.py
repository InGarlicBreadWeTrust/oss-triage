"""Optional GitHub REST client (stdlib only). Offline by default.

The engine triages plain dicts. This module is the ONLY place that ever
reaches the network, and it is off unless you explicitly call it.
See SECURITY.md for the design guarantees.
"""
from __future__ import annotations
import json
import os
import time
import urllib.request
import urllib.error

from .models import Issue, PullRequest

API = "https://api.github.com"
TOKEN_ENV = "GITHUB_TOKEN"
_USER_AGENT = "oss-triage/0.1.0 (+https://github.com/IN-GARLICE-LOCAL/oss-triage)"
_BACKOFF_BASE = 2.0
_MAX_RETRIES = 3


class GHError(RuntimeError):
    pass


def _redact(err) -> str:
    s = str(err)
    for word in ("token", "secret", "Authorization", "Bearer"):
        if word in s:
            return "<redacted>"
    if "http://" in s or "https://" in s:
        return "<redacted: request URL>"
    return s[:200]


def _token() -> str:
    return os.environ.get(TOKEN_ENV, "") or ""


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _as_issues(payload) -> list:
    data = payload
    if isinstance(data, dict) and "results" in data:
        data = data["results"]
    return [Issue.from_github(o) for o in data]


def _as_pulls(payload) -> list:
    data = payload
    if isinstance(data, dict) and "items" in data:
        data = data["items"]
    return [PullRequest.from_github(o) for o in data]


class GHClient:
    def __init__(self, owner, repo, token=None, retries=_MAX_RETRIES,
                base=None):
        self.owner = owner
        self.repo = repo
        if token is None:
            token = _token()
        self._token = token
        self._retries = retries
        base = base or API
        if base != API and not base.startswith("https://api.github.com"):
            raise GHError("only the fixed GitHub API host is allowed")
        self._base = base.rstrip("/")

    def _url(self, path):
        return self._base + "/repos/" + self.owner + "/" + self.repo + path

    def _once(self, path, params):
        url = self._url(path)
        if params:
            q = "&".join("%s=%s" % (k, v) for k, v in params.items())
            url = url + "?" + q
        req = urllib.request.Request(url)
        req.add_header("Accept", "application/vnd.github+json")
        req.add_header("User-Agent", _USER_AGENT)
        if self._token:
            req.add_header("Authorization", "Bearer " + self._token)
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read()
        return json.loads(raw)

    def _do(self, path, params):
        delay = _BACKOFF_BASE
        last = None
        attempt = 0
        while attempt < self._retries:
            attempt = attempt + 1
            try:
                return self._once(path, params)
            except urllib.error.HTTPError as e:
                last = e
                if e.code in (403, 429) and attempt < self._retries:
                    time.sleep(min(int(delay), 30))
                    delay = delay * 2
                    continue
                raise GHError("GitHub http %s; %s" % (e.code, _redact(e)))
            except urllib.error.URLError as e:
                last = e
                if attempt < self._retries:
                    time.sleep(int(delay))
                    delay = delay * 2
                    continue
                raise GHError("network error; " + _redact(e))
        raise GHError("failed after %d attempts; %s" % (self._retries, _redact(last)))

    def issues(self, state="open", per_page=30, direction="asc"):
        params = {"state": state, "per_page": per_page,
                "direction": direction, "sort": "created"}
        data = self._do("/issues", params)
        return [i for i in _as_issues(data) if not i.maybe_pr]

    def pulls(self, state="open", per_page=30):
        params = {"state": state, "per_page": per_page, "sort": "created"}
        return _as_pulls(self._do("/pulls", params))

    def pr_detail(self, number, with_files=True):
        data = self._do("/pulls/" + str(number), None)
        pr = PullRequest.from_github(data, number=number)
        if with_files and pr.changed_files is None:
            files = self._do("/pulls/" + str(number) + "/files", None)
            pr.filenames = [f.get("filename", "") for f in files]
            pr.changed_files = len(files)
        return pr

    def pr_reviews(self, number):
        return self._do("/pulls/" + str(number) + "/reviews", None) or []
