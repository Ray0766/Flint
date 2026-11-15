# NARROW-06 · text that stopped being true (@2026-11-15)

From the 2026-11-15 follow-up review, direction 4.

## 1. Were the findings still true

| finding | on `4a897ad` | why it is false |
|---|---|---|
| `flint/sources/candidates.py:68` 「本产品是商用 MVP（S1）」 | yes | `DEC-066`: open source, self-use |
| the same claim in `assets/source_registry_seed.yaml:96` (not in the review) | yes | same |
| `README.md:71` 「`start-demo.sh` … 还没有在 macOS 实机上跑过」 | yes | `docs/trace/MAC-01.md` §7.1: ran end to end on this Mac (Apple M3, `Mac15,13`), exit 0, on 2026-11-14; the running backend is PID 99562, the one in `.run/backend.pid` |
| `README.md:72` vs `docs/macOS-安装.md:63` on the model | yes: README says only keyless endpoints and the closed-API work "尚未落到代码上"; the setup doc quotes the 2026-11-14 ruling and says the demo "没有接" the three loaders | both stale after `NARROW-04` |
| `docs/macOS-安装.md:28-30` 「Python 版本有一处未决」 (not in the review) | yes | `DEC-068` |
| `AGENTS.md` S1 and digest (not in the review) | still the pre-`DEC-066` goal | it mirrors `CLAUDE.md` for other agents |

## 2. Plan, and what I counted as progress

Fix the live surfaces (code, seed data, README, setup doc, the agents mirror); leave dated
records alone (handoff, steward reports, old plans, traces say what was true then). Progress =
a judge that names each claim and goes red if it comes back.

## 3. What changed

- `candidates.py` and the seed: the Reddit reason now says the commercial framing was what
  blocked it, that `DEC-066` changed the goal, and that whether the non-commercial free tier
  now fits is the owner's call. I did not answer that question;
- `README.md`: the Mac run with a link to the trace; the model paragraph describes
  `FLINT_DEMO_PROVIDER` / `harness/demo_model.py`;
- `docs/macOS-安装.md`: Python 3.13 per `DEC-068`; the model section rewritten as a table of the
  four values, what each reads, and that the wiring was proven by replay only;
- `AGENTS.md`: now identical to `CLAUDE.md` below the title line.

## 4. Proof

`tests/v041/test_stale_text.py`, 5 tests: `5 failed` before the edits, `5 passed` after.
With the suites that read the same files:

```
pytest tests/v041/test_stale_text.py tests/v041/test_start_demo_sh.py tests/v041/test_source_seed.py
       tests/v041/test_new_sources.py tests/v041/test_launch_compliance_doc.py
79 passed     (first try: 2 failed — my own wording quoted 「商用 MVP」; reworded)
```

## 5. Not done, waiting on the owner

- `CLAUDE.md` 非目标 line still says 「V1 边界外」, and S1's 「入口今天还开着…关入口另开卡」 is false
  after `NARROW-05`. Both are `CLAUDE.md` text I was told not to rewrite. `AGENTS.md` mirrors
  whatever `CLAUDE.md` says, so it inherits both.
- Dated documents that still say 商用 MVP (`docs/HANDOFF-交接摘要.md:9`,
  `docs/搜热点-升级方案.md:90`, `docs/源站清单-v041.md:40,69`, a steward report): left as records.
