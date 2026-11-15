# NARROW-04 · the demo stack can run on a keyed hosted model (@2026-11-15)

From the 2026-11-15 follow-up review, direction 2.

## 1. Was the finding still true

Yes, with one correction to the cause.

- `harness/local_model.py:53` builds `LocalProvider` with no `api_key`; both demo processes
  (`harness/demo_server.py` three call sites, `harness/run_worker.py` one) used only that.
- The demo database (read-only `SELECT`):

  ```
  SELECT kind, state, count(*) FROM jobs GROUP BY 1,2
  daily_ingest|done|32 · daily_ingest|queued|1 · proposal|failed|18
  SELECT left(error::text,400), count(*) FROM jobs WHERE kind='proposal' GROUP BY 1
  LocalProviderUnavailable: local endpoint unreachable for qwen3.6:35b-a3b: [Errno 61] Connection refused | 18
  ```

  So the 18 failures are "no local endpoint on this Mac", not "no key". Either way the stack
  had no route to any other model.
- `flint/llm/production.py` has `load_anthropic_tier` (:284), `load_deepseek_tier` (:384),
  `load_openai_tier` (:390); nothing under `harness/` that the demo runs called them.

## 2. Plan, and what I counted as progress

The vendor is mine to pick, so the code picks none: one environment switch,
`FLINT_DEMO_PROVIDER`, unset meaning exactly the old behaviour. Progress =

1. with a vendor and its variables set, both demo processes build a provider that carries
   the key on the wire, with model name and prices from the environment;
2. shown against real recorded responses from all three vendors, with a made-up key, through
   a transport that refuses any unrecorded URL, so nothing can leave the machine;
3. unset or `local` unchanged, and a typo refused instead of falling back.

## 3. What changed

- `harness/demo_model.py` (new): `build_demo_provider(env=None, *, transport=None)`.
  `local` → `build_local_provider()` unchanged; `anthropic` → `PaidTierProvider`;
  `deepseek` → `DeepSeekProvider` (its own cache-hit pricing); `openai` → `CloudOpenAIProvider`.
  It never reads a key itself: the existing loaders do, and name a missing variable without
  echoing a value. It lives outside `local_model.py` because
  `tests/v041/test_combo_wire.py::test_the_shared_provider_is_free_local_and_reads_no_api_key`
  pins that file to "no key anywhere", and that boundary still holds for the local tier;
- `harness/demo_server.py`, `harness/run_worker.py`: build from it; combo's model name is now
  `provider.model` instead of a separate constant;
- `start-demo.sh` step 2 says which vendor was picked (it still names no key variable:
  `test_start_demo_sh.py::test_never_touches_a_key`); `.env.example` documents the switch;
- `tests/v041/test_combo_wire.py`: the "one definition" judge now pins `build_demo_provider`
  as the one place, with the same intent.

## 4. Proof

`tests/v041/test_demo_model.py`, 11 tests. Before the module existed and before the two
processes were wired: `11 failed`. After the module only: `2 failed, 9 passed` (the two
process tests). After wiring: `11 passed`.

The recordings replayed are `fixtures/topic_runs/claude-sonnet-5/combo.json`
(`POST https://api.anthropic.com/v1/messages`), `fixtures/topic_runs/deepseek-chat/combo.json`
(`POST https://api.deepseek.com/chat/completions`) and
`fixtures/topic_runs/gpt-4o-mini/combo.json` (`POST https://api.openai.com/v1/chat/completions`),
recorded earlier by `harness/topic_caliber.py`.

Mutations, each run once and restored:

| injected bug | result |
|---|---|
| bearer header dropped from the OpenAI-compatible client | `2 failed, 9 passed` (deepseek, openai) |
| Anthropic output price read from the input variable | `1 failed, 10 passed` (cost check) |
| unknown vendor falls back to `local` | `1 failed, 10 passed` |

I did not inject "transport not passed through": that mutation would send a real request.

```
pytest tests/v041/test_demo_model.py tests/v041/test_combo_wire.py tests/v041/test_start_demo_sh.py
48 passed, 14 skipped
ruff check . → All checks passed!
mypy --strict flint eval harness → Success: no issues found in 372 source files
```

## 5. Not done, and why

- No real request, no real key (told so). The wiring is proven up to the HTTP exchange the
  vendor recorded earlier; a live vendor can still differ (model ids, parameters the model
  refuses, rate limits).
- The running demo stack was not restarted; it picks this up on its next start.
- `PaidTierProvider` sends `thinking: {"type": "disabled"}`; `docs/v0.4-问题单.md:450` already
  notes that some Claude models reject that. Which model to use is the owner's call.
- The 18 failed jobs stay in the demo database (no writes there).

## 6. Waiting on the owner

Vendor, model, the two prices, and the key, in `.env` (`FLINT_DEMO_PROVIDER` plus that
vendor's block in `.env.example`); then a restart of the stack and one real run, with me
or without.
