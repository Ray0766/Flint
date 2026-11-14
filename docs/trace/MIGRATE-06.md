# MIGRATE-06 trace — prod_caliber 影响声明 @2026-08-02

## 1 装载

与 MIGRATE-05/07 共用一次装载（见 `MIGRATE-05.md#1`）；本卡另读
`harness/prod_caliber.py` 的 `TOPICS` **实测值**（12 条，非清单转抄）。

## 2 test-first

verify_cmd `--require-refs 12` 先跑 → **红**（文档不存在）→ 落盘 → **exit 0**：
`14 个引用 id 均在仓库中可查`。

## 3 12 个场景 id 是取出来的，不是抄出来的

`import harness.prod_caliber; TOPICS` → 实测 12 条：
六模板（generic / thesis / startup / engineering / grant / vibe_pack）× 两口径（plain / channels）。
`harness/prod_caliber.py` **一个字符未改**（J7 硬约束）。

## 4 self_review

① acceptance 映射：12 场景逐行列出且逐行声明「v0.4 不改其断言」；免费档路线（0.44 vs 0.90）
的数据基础改变写在 `## k7` 并明确指向 **K7**、明确写「NEVER 拿旧数字冒充双语口径下的结论」。
反证：**p1**（把 `golddoc-grant-plain` 改成不存在的 `golddoc-grant-classic`）→
`这些 id 在 harness/assets 里找不到`；**p2**（删掉所有 golddoc 行）→ `引用 id 只有 2 个，少于 12`。
② 无冻结件偏离：不碰 contracts/，不碰 harness/。
③ 无禁用词。
④ 复用共用校验器。
⑤ 装载见 §1。

**一处如实说明**：校验器报的是「14 个引用 id」——多出的 2 个是 `plain` 与 `channels`
（p2 变异体把它们暴露了）。断言口径是「≥12 个反引号 id 且**每个**都能在 `harness/`+`assets/`
里查到」，不是「恰好这 12 个场景 id」。12 个场景 id 本身在文档里逐行列全，
存在性也逐个过了同一条断言。

## 5 产出

`docs/prod_caliber_impact_v04.md`（校验器复用 MIGRATE-05 的产出）。
