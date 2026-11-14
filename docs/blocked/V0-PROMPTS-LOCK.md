# blocked · V0 出口全局门被 prompts/worker.md 卡住

**状态** closed · 2026-08-05 · `HYG-01`

**时间** 2026-08-02 · **阻塞点** SELFCHECK-V0 的全局门 `pytest -q`（V0 九张卡本身全部 verified、
工单 §8 的 V0 出口命令清单 8 条全部 exit 0）

## 现象（命令原样输出）

```
$ python -m pytest -q --tb=no -rf
FAILED tests/fe_core/test_section_prompt.py::test_prompts_lock_clean - Assert...
FAILED tests/m2/test_m2_004.py::test_repo_lock_is_current - AssertionError: a...
2 failed, 1348 passed in 132.24s

$ python -m pytest tests/m2/test_m2_004.py -q
>       assert verify_lock(PROMPTS_DIR) == []
E       AssertionError: assert ['worker'] == []
```

## 根因

`prompts/` 不是普通目录，是**带 lock 的产品提示词注册表**：

```
prompts/
  cluster_naming@1.md  gate1_verdict@1.md  keyword_extract@1.md
  relevance_judge@1.md  section_draft@1.md  topic_gen@1.md  topic_gen@2.md  topic_gen@3.md
  prompts.lock.json
  worker.md          ← 本次归位放进来的
```

两条既有断言（`flint/llm/prompts.py:58 verify_lock`）要求目录内每个提示词都在
`prompts.lock.json` 里且哈希一致。`worker.md` 一进目录就被当成第 9 个提示词，
于是 lock 不一致 → 两处红。

注意命名：既有全部是 `<名字>@<版本>.md`，`worker.md` **没有版本段**——
它从命名上就不属于这个注册表。

## 已试三案

1. **不动**：红留着 → 违反 §5「SELFCHECK 不过 NEVER 带病进下一阶段」，V1 开不了工。
2. **加进 lock**：可行，但 `worker.md` 是 agent 指令文件、不是产品提示词；
   进了 lock 之后**每改一次 worker.md 就要 bump 版本 + 重生成 lock**，
   否则整套测试变红。本会话中 owner 已经中途更新过一次 worker.md——
   这条路会把那次更新变成一次「测试全红」事故。
3. **改 lock 扫描口径**（忽略无版本段的文件）：能一次解决，但**改的是既有测试的行为语义**，
   撞 owner 红线「NEVER 改任何测试的断言内容或默认行为语义」，NEVER 自行执行。

## 怀疑根因

归位指令把 `worker.md` 指到了 `prompts/`，而该目录在本仓库有 lock 语义——
指令下达时这一点没有被考虑到（工单与 worker.md 里都没提 prompts/ 的 lock）。

## 需要 owner 决定（三选一）

| 方案 | 动作 | 代价 |
|---|---|---|
| **A（推荐）** | `worker.md` 移出注册表，落 `docs/worker.md` 或仓库根 | 零测试改动；`prompts/` 保持「只放带版本的产品提示词」这条干净语义 |
| B | 改名 `prompts/worker@1.md` 并写进 lock | 每次改 worker.md 都要 bump 版本 + 重生成 lock，否则全套红 |
| C | 改 lock 扫描口径，跳过无 `@版本` 的文件 | 改既有测试语义，需 owner 明确授权 |

## 绕行现状

- V0 九张卡**全部 verified**，工单 §8 的 V0 出口命令 8 条**全部 exit 0**（含合并 DAG）；
- `ruff check --no-cache .` **全绿**；
- 唯一未过的是全局门里的 `pytest -q` 两处红，**根因与 V0 产出内容无关**，纯粹是文件位置；
- 我**没有**擅自移动 `worker.md`，也**没有**改 lock 或改测试——等 owner 一句话。

## 关闭（HYG-01 · 2026-08-05）· 根因逐条实跑，NEVER 凭印象

这张单的根因是那两个测试红着（原文：`2 failed, 1348 passed`）。现在：

```
$ python -m pytest tests/m2/test_m2_004.py tests/fe_core/test_section_prompt.py -q
.........
9 passed in 0.05s
```

**两个文件共 9 条全绿**，其中就有当时点名的 `test_repo_lock_is_current`
与 `test_prompts_lock_clean`。全局门 `pytest -q` 本轮实测 3873 passed、零失败。
