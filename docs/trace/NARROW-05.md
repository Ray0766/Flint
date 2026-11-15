# NARROW-05 · the freeze list closes its entries (@2026-11-15)

From the 2026-11-15 follow-up review, direction 3. `DEC-066`: freezing = no more investment,
entries closed, no code deleted.

## 1. Was the finding still true

Yes, and wider than the review saw.

- `web/components/shell/AppShell.tsx:91-104`: the nav listed `/plaza`, `/workbench`,
  `/favorites`, `/design`, `/settings/locale`, `/account`, `/demo`; the shell also rendered the
  region and language dropdowns (`LocaleControls`).
- What `/workbench` and `/account` carry (the review had not checked), read from the screens:
  - `/workbench` offers the five human templates and nothing else
    (`web/lib/sectionTables.generated.ts:20`, `TEMPLATE_IDS = generic/startup/engineering/grant/thesis`);
    the vibe_pack route is `/projects/[id]/proposal`. So `/workbench` is frozen item 7;
  - `/account` is an identity screen (principal, profile, scope, memberships), not on the list.
    It carries the link to `/billing` (frozen item 2). The screen stays; the link closes.
- Entries the review did not list: the plaza card's three buttons (favorite → 收藏;
  "add to workbench" → `/workbenches/{id}`, the graph workbench, `DEC-042`; share → 分享) and
  the plaza's region switch (nine regions).
- Sources: `flint/sources/registry.py:48` defaults every source on. But the daily ingest
  (`flint/jobs/ingest.py:77`) hard-codes all four sources and never asks the registry, and it
  only ever replays fixtures. The one piece of code that fetches Weibo and Google Trends live is
  `fixtures/_record_cn_real.py` (owner-present recorder, refuses without `--owner-is-here`).
- No check went red when a frozen item got a card in the ledger.

## 2. Plan, and what I counted as progress

1. every entry into a frozen item gone from what renders, with the screens still reachable by
   URL and their code and tests intact;
2. Weibo and Google Trends off by default and skipped by the live recorder even when authorised;
3. a ledger check that is red when a frozen item gets a `started` after the freeze;
4. all of it seen in a real browser at 1920×1080 and 390×844.

## 3. What changed

- `web/lib/frozen.ts` (new): one table of switches, one per frozen item, all on.
  Unfreezing an item = one edit there (after an owner ruling);
- `AppShell.tsx`: renders `SHELL_NAV_ITEMS` (`NAV_ITEMS` minus frozen hrefs; the table itself
  keeps every route) and drops `LocaleControls`;
- `app/account/page.tsx`: billing link; `app/plaza/page.tsx`: region switch, and the empty
  state no longer lists other regions (it would point at a control that is gone);
  `HotspotCardActions.tsx`: the three buttons, and no empty row when all three are closed;
- `AnimeNav.tsx` + `redesign.css`: the phone tab bar divided the width by a fixed 7. With three
  tabs left it covered 167 px of 390 and the page showed through. It now divides by
  `--tab-count`. This is a fix for a regression I caused, not UI polish;
- `flint/sources/registry.py`: `FROZEN_SOURCE_IDS = {"weibo", "gtrends"}`, default off;
  an explicit flag still turns one on. `fixtures/_record_cn_real.py` writes them into the
  receipt as `frozen` and does not fetch them;
- `tests/v041/test_freeze_ledger.py` (new): see section 4.

Tests changed because the behaviour they pinned changed on purpose:

- `tests/m1/test_m1_010.py`: the default is now "on except the two frozen";
- `tests/m1/test_m1_015.py`: isolation across four sources; the fixture turns the two frozen
  sources on explicitly so it keeps testing isolation;
- `web/__tests__/app/shell.test.tsx`: compares rendered links with `SHELL_NAV_ITEMS`;
- `nav02`, `nav03`, `HotspotCardActions.test`, `cardActions.test`: these test the code behind
  the closed buttons (navigation after "add to workbench", receipts, click bubbling). The code
  stays, so they mock the freeze table off and keep testing it. Whether the entries are closed
  is `frozen_entries.test.tsx`'s job.

## 4. Proof

Front end, `web/__tests__/app/frozen_entries.test.tsx`, with the four source files stashed
back to before: `3 failed | 2 passed` (the two passing ones test the table itself). After:
`5 passed`. Whole suite: `Test Files 89 passed (89) · Tests 892 passed (892)`.

Sources, `tests/v041/test_frozen_sources.py`: collection error before `FROZEN_SOURCE_IDS`
existed; after, with every suite that touches the registry or the recorder:

```
pytest tests/v041/test_frozen_sources.py tests/m1/test_m1_010.py tests/m1/test_m1_015.py
       tests/v041/test_cn_real_ingest.py tests/v041/test_cn03_preflight.py
       tests/v041/test_cn06_e2e_real.py tests/v041/test_new_sources.py
       tests/v04/region/test_registry.py tests/v04/region/test_ingest_fields.py
       tests/v04/schema/test_i3_registry.py tests/v041/test_legal_status_recorded.py
150 passed, 1 skipped
```

Ledger, `tests/v041/test_freeze_ledger.py`: 4 passed on the real ledger. With one line
`{"task_id": "PAY-04", "event": "started", ...}` appended to the real ledger (then restored):

```
AssertionError: a frozen item got a card after DEC-066: ['PAY-04 (支付与计费) @ 2026-11-15T06:00:00+00:00']
2 failed, 2 passed
```

How it decides: a `started` after `NARROW-01`'s own `started` (the card that landed
`DEC-066`), for a card whose id carries a prefix the ledger used for a frozen item
(the table in the test is my reading of the ledger, not an owner ruling) or whose note names
the item. `EXEMPT` holds this card, which names frozen items because it closes them.

Real browser (the running `next dev` on :3000, which hot-reloaded the change), built-in
browser pane:

| | 1920×1080 | 390×844 |
|---|---|---|
| nav hrefs | `/plaza`, `/account`, `/demo` | same, three bottom tabs of 130 px each, `scrollWidth 390`, active label 40/40 px (whole) |
| region/language dropdowns | gone (`.app-shell__locale` absent); theme switch still there | gone |
| plaza | `data-plaza-state="ready"`, card actions 0 | 55 cards, card actions 0 |
| `/account` | identity shown, `[data-billing-entry]` absent | not re-checked |
| `/favorites` typed in | still renders "收藏图书馆" (screen kept) | not re-checked |

## 5. Not done, and why

- Routes are not blocked: typing `/favorites`, `/design`, `/billing`, `/settings/locale`,
  `/workbench`, `/workbenches/{id}`, `/share/{token}` still opens them. Closing entries was the
  brief; blocking URLs would go further than `DEC-066` says.
- In-page links I did not chase: anything inside a frozen screen (they are now unreachable from
  the shell); the audience selector on `/projects/[id]/proposal` still offers the five human
  templates next to vibe_pack. That selector sits on the chain, and closing half of it is a
  change to the chain's own screen, so I left it for a ruling.
- The daily ingest still lists all four sources and replays their fixtures. No live ingest
  path is wired; when one is, it has to ask the registry.
- `CLAUDE.md` S1 still says 「入口今天还开着（侧栏在 `web/`，源的启用在 `flint/`），关入口另开卡」.
  After this card that sentence is false. I may not edit `CLAUDE.md` beyond the S3 line, so it
  waits for the owner.

## 6. Rework after the full gate (2026-11-15, later)

The full unit run outside iCloud (`NARROW-03` section 7) found two things this card broke,
which my targeted runs had not covered:

| judge | why red | fix |
|---|---|---|
| `test_redesign_layer.py::test_every_token_the_layer_reads_is_defined_somewhere` | `--tab-count` was only set inline on the nav; the layer must read only tokens the token layer defines | `:root:root { --tab-count: 7 }` (the old fixed count) and `--tab-count` registered in `NEW_TOKENS`; `AnimeNav` still sets the real number on the nav (`2b37373`) |
| `test_gauge_map_b2.py` ×2 | the B2 gauge map counts every file under `web/__tests__/app` for the `npm test -- --run app` gauge, and the copy on disk predated `frozen_entries.test.tsx` | regenerated with `tools/gauge_map.py`, 4 lines added, file kept CRLF (`6dc9656`) |

Both judges were seen red on the real defect before the fix; after it they pass with the rest
of the unit stage (`4410 passed`). Real browser after the change (running `next dev`,
hot-reloaded): 390×844, root `--tab-count` 7, nav 3, three tabs of 130 px at x 0/130/260,
`scrollWidth 390`; 1920×1080, the three nav items stacked in the side bar.
