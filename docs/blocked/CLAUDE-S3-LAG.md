# 登记（非阻塞）· CLAUDE.md S3 目录结构与实仓不符（**已关闭** @2026-08-03）

**状态** closed · 2026-08-03 · `DEC-019`

**裁决（owner 2026-08-03 · DEC-019）：认可登记结论，照登记关闭——取第一选项「保持现状」。**

S3 的目录结构继续作为**概念分层示意**永久留档，实际落点真相以 `tasks-v04.json` 为准（DEC-003 已钉死）。`CLAUDE.md` 本体**零修改**——它属 owner 变更通道，NEVER 由执行侧改。

---

**性质**：文字滞后登记，与 `WORKORDER-v04.md#2` 第 18 条（models.py 头部冻结规则文字滞后）同一类。
**不阻塞**任何卡；owner 已按 DEC-003 定口径，本条只留痕。

## 现象

`CLAUDE.md` S3「目录结构」写的是包模板形态：

```
flint/
  domain/  config.py  obs/  sources/  norm/  embed.py  cluster/ …
tests/  fixtures/  assets/  migrations/  prompts/  docs/  web/
```

而 v0.4 工单与 `tasks-v04.json` 原本按 **`src/`** 书写代码落点（75 张卡引用），
`worker.md` §5 的全局门也写 `mypy --strict src`。实仓既没有 `src/`，
Python 包就是 `flint/`——三处口径两两不一致。

## 处置（owner DEC-003）

**以实仓为准**：v0.4 代码并入 `flint/`，`src/` 口径作废。已完成机械重映射
（`tasks-v04.json` 48 处、`WORKORDER-v04.md` 1 行、`worker.md` §5 一处），
前端 153 处 `web/src` 路径按上下文跳过。

## 仍留着的滞后（本条登记的对象）

`CLAUDE.md` 本体**零修改**（owner 明令），因此 S3 的目录结构文字**仍是包模板形态**，
与实仓 `flint/` 的实际子包（`align/`、`compose/`、`evidence/`、`topic/`、`intervene/`、
`llm/`、`repo/`、`api/`、`jobs/` 等）并不逐一对应。

**影响**：读 S3 的人可能按模板去找目录。**不影响执行**——
落点真相以 `tasks-v04.json` 为准（worker.md §1.2），且 DEC-003 已把口径钉死。

## 需要 owner 的什么

一句话即可，两选一：

- **保持现状**：S3 继续作为「概念分层示意」，实际落点看 `tasks-v04.json`；本条永久留档。
- **走 PDD 修订通道**改 S3 正文（`CLAUDE.md` 属 owner 变更通道，NEVER 由执行侧改）。
