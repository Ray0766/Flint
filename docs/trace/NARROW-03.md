# NARROW-03 · CI gets past the install step for the first time (DEC-068) (@2026-11-15)

From the 2026-11-15 follow-up review, direction 1. Card id is mine; the review did not name one.

## 1. Was the finding still true

Yes, all of it, on `4a897ad`:

- `.github/workflows/ci.yaml:18/29/40/51`: all four jobs on `python-version: "3.11"`;
- `requirements.lock:40` pins `numpy==2.5.1`; run `43598672641` (lint job) died with
  `No matching distribution found for numpy==2.5.1` ("2.5.1 Requires-Python >=3.12");
- `gh run list --limit 4`: the last four pushes all `failure` in 10 to 13 seconds;
- `tests/m2/test_m2_040.py::test_no_guess_failed_without_reason_invariant` is not marked
  `compose`, but the module's autouse `clean_slate` connects to the test database.

## 2. Plan, and what I counted as progress

Owner ruling in the prompt: the lock and my local 3.13 win over the "Python 3.11" in
`CLAUDE.md` S3. Recorded as `DEC-068`.

I cannot push, so "CI ran past install" cannot be seen on GitHub from here. What I counted:

1. every place that pins the interpreter says 3.13, with the judges that pinned 3.11 red first;
2. lint and typecheck (the two jobs after install) green locally on 3.13 semantics;
3. the unit job reproduced locally the way a fresh runner sees it (no database, no Redis,
   no API, no internet, no model cache), and every failure that is not an artefact of my
   reproduction fixed.

## 3. What changed

| commit | what |
|---|---|
| `95fe293` | `ci.yaml` four jobs → 3.13; `pyproject.toml` `requires-python`, mypy `python_version`, ruff `target-version` → 3.13; `test_m1_001` / `test_m1_007` pin 3.13; nine `UP047` hits fixed with PEP 695 type parameters; `DEC-068`; `CLAUDE.md` and `AGENTS.md` S3 |
| this card's second commit | unit job installs Node 24 and runs `npm ci` in `web/`; `compose` markers on the tests that need the database or Redis |

### 3.1 Reproducing the unit job

A clone of `4a897ad` in my scratch directory (tracked files only, so no `web/node_modules`,
no `.env`), run under macOS `sandbox-exec` with a profile that denies all outbound network
except loopback, and denies loopback to 8000 / 3000 / 55432 / 56379 (the demo stack I was
told not to touch). `HF_HOME` pointed at an empty directory.

```
pytest -q -p no:cacheprovider -m "not compose" -rf --tb=line
17 failed, 4355 passed, 430 skipped, 1052 deselected, 1 warning, 19 errors in 1209.77s
```

Sorted:

| kind | tests | real on CI? | fix |
|---|---|---|---|
| needs PG/Redis, not marked `compose` | 19 setup errors in `test_m2_040` (the one the review named), `test_fail_events`, `test_overview_deliverables`, `test_regen_events`; 4 failures in `test_cn_only_scope` ×2, `test_regions_from_backend`, `test_orchestration_doc` | yes (refused connection instead of my `PermissionError`) | mark the database tests `compose`; autouse cleanup fixtures skip the database for non-compose tests, so the static tests in the same files still run in the unit stage |
| drives `npx vitest` / `npx tsc` in `web/` | 10 failures across 8 files | yes: the unit job never installed Node deps | unit job: `actions/setup-node@v4` (24) + `npm ci` in `web/` |
| `tests/m4/test_recorder_timeout.py` | 3 | no | my sandbox rule blocked a loopback port the test opens itself: 3 failed inside the sandbox, `3 passed` outside it |

The borrowed fixture case: `tests/v041/test_regen_events.py` imports `_clean` from
`tests/fe_core/test_regen_job_e2e.py`, which is autouse, so it ran for that file's static
tests too. The base module is `pytestmark = compose` as a whole, so the same guard there
changes nothing for its own tests.

## 4. Proof

```
.venv/bin/mypy --strict flint eval harness          # after the 3.13 switch
Success: no issues found in 371 source files
ruff check .                                         # py313
All checks passed!
pytest tests/m1/test_m1_001.py tests/m1/test_m1_007.py   # judges re-pinned, old config stashed
2 failed, 10 passed            # red against 3.11
12 passed                      # green against 3.13
pytest tests/m1/                # after the unit-job Node step
365 passed
```

The seven database files plus the borrowed base module:

```
sandbox, -m "not compose":  51 passed, 24 deselected      (before the fixture guard: 49 passed, 2 errors)
test DB, -m compose:        24 passed, 51 deselected
```

The Node-driven files, run in the sandbox from the real checkout (which has
`web/node_modules`, i.e. what the runner has after `npm ci`): see section 6.

## 5. Not done, and why

- **Not seen on GitHub.** Pushing is out of my reach. The first real run is the next push.
- `pip install -r requirements.lock` on Linux was not tried. On Linux `torch==2.13.0` pulls the
  CUDA wheels (several GB) four times, once per job. It should install; it will be slow.
  A CPU-only index would cut it down but changes how the lock resolves, so I left it.
- `compose-smoke` was not reproduced (it needs Docker on the runner). The tests I moved into
  it pass against my local test database.
- `compose.yaml` api/worker placeholders and `docker/pdf/Dockerfile` still say
  `python:3.11-slim`. None of them installs the lock; `DEC-068` says so and leaves them.

## 6. Unit-stage rerun of the Node-driven tests

Not cleanly reproduced, and the reason is this machine, not the code.

- Inside the sandbox, the first `npx vitest` the tests launched sat at 0 % CPU for over ten
  minutes (my reading: the sandbox profile blocks something vitest's worker pool needs).
  Killed. The two `tsc` files do not depend on that.
- Outside the sandbox, from the real checkout: `6 failed, 77 passed, 4 skipped`. All six
  failures are the vitest-driven ones, and the one I opened failed at vitest startup:
  `TypeError: pico is not a function at picomatch (node_modules/picomatch/index.js:13)`.
  `ls -lO` shows `node_modules/picomatch/lib/picomatch.js` as `compressed,dataless`: the repo
  sits in an iCloud-synced Desktop and macOS had evicted that file. After it came back,
  `require` returned a function; the next attempt hung on another evicted file
  (`cat` of `picomatch/lib/parse.js`, 0 % CPU for 15 minutes).
- Count of evicted files, measured twice: `web/node_modules` 1794 → 6047 and `.venv` 5588 →
  19041, while I was reading them back. `fileproviderd` had used 1498 CPU minutes.

What does stand: the full front-end suite, which contains every spec file these six wrappers
filter for, ran green in this session before the eviction got worse:
`Test Files 89 passed (89) · Tests 892 passed (892)`. The `tsc` wrappers passed in the same
rerun.
