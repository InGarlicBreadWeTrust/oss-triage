# Privacy

`oss-triage` is an **opt-in, read-only** GitHub triage tool. It is the one tool in
the collection that can reach the network — by explicit design — and this page is
exactly what that does and does not touch.

## In one line
By default it makes **no network calls at all**; if you opt into live GitHub, it
only *reads* public metadata with your own token and never sends your data out.

## What the tool does NOT do
- **No telemetry, analytics, or usage tracking.** Nothing reports what triage you
   run or what you triaged.
- **No upload of your data.** The tool fetches public repo/issue/PR metadata from
   GitHub; it does not send your files, your issues, or any user content anywhere.
- **No data leaves your machine by default.** With no `GITHUB_TOKEN`/live `repo`
   mode, the tool only reads the JSON fixtures on your disk.

## What the tool DOES do
- Reads JSON issue/PR fixtures you point it at, or — when run in **live `repo`
   mode** — fetches public repository/issue/PR metadata over **HTTPS**.
- A GitHub token is read from the `GITHUB_TOKEN` environment variable **only**, is
   sent as a `Bearer` credential to `api.github.com`, and is **scrubbed from every
   error path** by `_redact` (any error string containing "token", "secret",
   "Authorization", or "Bearer" is returned as `<redacted>`), so a token can never
   end up in a log or message.
- Live fetching is **opt-in** and **HTTPS-only**: `GHClient` refuses a non-HTTPS base
    URL outright.
- Outputs only the reports you ask for (`--json`, `--dashboard`), written to paths
   you name and contained by `guard_output` (refuses to write outside the current
   working directory unless `--allow-outside` is explicit).

## Your controls
- Use a scoped, short-lived `GITHUB_TOKEN`; the token lives only in your
   environment for the duration of the run and is never written to disk by the tool.
- Do not paste a live token into reports, issues, or shell history that gets shared.
- Treat `--json`/`--dashboard` outputs as containing public issue/PR metadata; review
   before sharing anything you generate.
- Retention is yours: delete the file and it is gone; the tool keeps no copy, backup,
   or cache.

## Data sharing
Third party is **GitHub only, and only in opt-in live mode**, over HTTPS with your
own token. No other third party, no analytics provider, no accounts beyond your own
GitHub one. No data that is not already public-on-GitHub is ever sent.

---

## Independent privacy audit (2026-10-21)

**Performed by:** `InGarlicBreadWeTrust` · **Type:** static source + dependency
review · **Result:** minimal, opt-in privacy surface; posture strong.

- No telemetry / analytics / usage tracking / background sync.
- The **only** network surface is an opt-in, HTTPS-only read of **public** GitHub
   metadata using the user's own token; **no user data is ever sent**.
- The token is environment-only and scrubbed from every error path by `_redact`;
   nothing token-bearing reaches a log or message.
- Zero runtime dependencies; no third-party services beyond GitHub.

**Verdict:** the privacy surface is the smallest a network-capable tool can have —
   an opt-in, HTTPS-only read with a token that is never persisted or logged. No
   code change required.
