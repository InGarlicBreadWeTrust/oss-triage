# Security

oss-triage is a **read-only triage advisor**. It scores issues and pull requests
from GitHub JSON and never mutates a repository, writes to disk outside the
output path, or executes anything a user hands it. This page is the threat
model and the list of deliberate design guards.

## Trust model

| Input | Trusted? | Why it is safe |
| --- | --- | --- |
| Issue / PR JSON (fixtures or API) | No | Parsed into dataclasses. No `eval`, `exec`, `compile`, `subprocess`, `os.system`. |
| `--output` / `--json` / `--dashboard` target | Yes, guarded by `guard_output` | Must resolve inside the current working directory unless `--allow-outside` is passed explicitly. |
| `GITHUB_TOKEN` env var | Yes | Read from the environment only; never written to logs, reports, or error strings. `github_fetch._redact` masks tokens in any rendered error. |
| Live GitHub fetch (`repo` mode) | Opt-in | Uses HTTPS only; `GHClient` rejects a non-HTTPS base URL. |

## Design principles

1. **No code execution.** The module never evaluates, compiles, forks, or
   imports anything derived from user-supplied content.
2. **Token hygiene.** A GitHub token is read from `GITHUB_TOKEN`, used as a
   `Bearer` credential, and scrubbed from any error that reaches the user.
   There is intentionally no logging and no token on disk.
3. **Output path containment.** Writing artifacts (`--json`, `--dashboard`)
   resolves the target and refuses to escape the current working directory
   (a `../../etc/passwd` target is rejected with exit code 3) unless the user
   explicitly passes `--allow-outside`.
4. **HTTPS only.** The optional network client refuses `http://` base URLs so a
   token can never be sent in the clear.
5. **Advisors, not verdicts.** Every score is labelled a *heuristic score*.
   A flagged PR never blocks a human; it only sets `needs_review`.

## Known limitations

- Heuristics are tunable and can be confused; treat any flag as a prompt for a
  human reviewer, never as a final decision.
- The bundled signal list is not exhaustive; a cleverly worded AI-generated PR
  can stay under the 50-point threshold. The threshold exists to route to human
  eyes, not to gate merges.
- No live fetch runs unless you explicitly choose `repo` mode and set a token.

## Reporting issues

Open a new issue with the version (`oss-triage --version`), the command you ran,
and a redacted copy of any input that triggered the problem. Do **not** paste a
live `GITHUB_TOKEN`.

---

## Independent security audit (2026-10-21)

**Performed by:** `InGarlicBreadWeTrust` · **Type:** static source + dependency
review · **Result:** no vulnerabilities found.

**Method:** static review of every `.py` source, the `pyproject.toml` build
config, and the dependency graph; grep for the runtime-risk surface
(`subprocess`, `os.system`, `eval`/`exec`/`compile`, `pickle`/`marshal`,
`ctypes`, sockets/network).

**Findings for `oss-triage`:**
- No `subprocess`, `os.system`, `exec`, `eval`, `compile`, `pickle`, `marshal`,
  or `ctypes` present.
- The **only** network surface is the intentional, opt-in GitHub read: it is
  **HTTPS-only** (`GHClient` rejects a non-HTTPS base), a token is read from
  `GITHUB_TOKEN` and **scrubbed from every error path** by `_redact`, and
  no user data is ever *sent* — only public repo/issue/PR metadata is
  *fetched*.
- No hardcoded secrets or credentials.
- Output-path containment via `guard_output` (refuses to escape the CWD unless
  `--allow-outside`), covered by `test_output_traversal` / `test_guard_outside`.
- Build system is stock `setuptools` build-meta with no custom hooks.

**Verdict:** strong posture; no vulnerability found. No code changes required.
