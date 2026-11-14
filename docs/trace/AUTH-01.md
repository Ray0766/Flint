# AUTH-01 · 迁移 0020：users / orgs / memberships 三张表

**卡** `docs/steward/tasks-v041-b4.json#AUTH-01` · **cycles 1（oneshot）** ·
**self_review = true** → §4 · **owner_review = false** · **依赖** 无

## 1. 装载清单

卡面 AUTH-01 · `docs/steward/连跑工单-v041-第4批.md` §2 与 §3-A ·
`contracts/models.py` 的 `User` / `Org` / `Membership` / `Principal` / `Role` 五段 ·
`migrations/versions/0019_doc_content.py` 全文 ·
`migrations/versions/0006_evidence_layer.py` 的 `CheckConstraint` 写法 ·
`tests/m3/test_m3_001.py` 的 alembic 子进程助手 · `tests/conftest.py` 的建库探针。
约 9k tokens，预算 40k 以内。

## 2. 这张卡是计划里一直有的那件事

`flint/jobs/runner.py` 文件头第 9 行原话：

> 角色解析经注入 `RoleResolver`（**memberships 表随身份任务落库后接 SQL 实现**）

三个类型在冻结件里躺了很久，只是没有表。把它顶出来的是 `WIRE-01`：
四族十条路由全是写操作，挂上去就要回答「这个人对这个项目是什么角色」，
而库里没有任何事实可查。**本卡只落表，`contracts/` 一字未动。**

## 3. 三处判断

**① 判据两侧都钉。**「列按冻结件逐字」只判一侧不够：
只判「表 == 冻结件」，有人改冻结件时判据跟着改、照样绿；
只判「表 == 手抄的名字」，冻结件改了而表没跟上、也绿。
所以字段名对着卡面的字面量钉住冻结件（`test_the_frozen_types_still_say_what_the_card_says`），
列名对着 `dataclasses.fields` 钉住表（`test_every_table_has_exactly_the_frozen_columns`）。
**两侧同时动才骗得过**，而那种改动没人会不小心做出来。

**② `role` 的取值域是 `CHECK`，不是只靠 `Literal`。**
一条绕过应用的 `INSERT ... role='god'` 打进来时 Python 不在场，
而库里存着的越界角色解析出来会是**一个谁都没定义过的权限**。
用 `CHECK` 而非 PG `ENUM`：本仓既有取值域全是 `CHECK`（`ck_docs_kind` 等），
换一种写法就要维护两套改法。

**③ 复合主键落在两列上，并有对照。**
`(user_id, org_id)` 重复 → `UniqueViolation`；而**同一人在另一个组织**可以有另一个角色
（`test_the_composite_key_is_on_both_columns_not_just_the_user`）。
只有前一条时，主键写成单列 `user_id` 也能让它红——那是另一种错。

## 4. verify、全局门与 self_review

```
verify_cmd: pytest tests/v041/test_migration_identity.py -q → 8 passed
全局门:     ruff check . --no-cache → All checks passed!
            mypy --strict flint     → Success: 299 source files
            pytest -q               → 3913 passed（第 3 批收尾时 3905，本卡 +8）
```

**① acceptance ↔ 测试映射**

| acceptance | 测试 |
|---|---|
| ① 三张表的列按冻结件逐字 | `test_the_frozen_types_still_say_what_the_card_says` + `test_every_table_has_exactly_the_frozen_columns`（两侧，见 §3-①） |
| ② role 取值域与冻结件一致、越界在库层被拒 | `test_a_role_outside_the_frozen_literal_is_refused_by_the_database`（真发一次越界写入）、`test_the_four_frozen_roles_all_insert`（**正例**：没有它，「越界被拒」可能是「什么都被拒」换来的） |
| ③ 复合主键 `(user_id, org_id)` | `test_the_same_person_cannot_hold_two_roles_in_one_org` + 上面那条对照 |
| ④ up 与 down 都跑一遍 | `test_downgrade_removes_the_tables_and_upgrade_brings_them_back`（**两个方向都真跑**：只跑 upgrade 的话 `downgrade()` 写错什么都没人知道，而回滚是出事那天唯一的退路）、`test_the_revision_follows_0019_without_skipping` |
| ⑤ NEVER 改 contracts/ 与 flint/domain/ | 同 ①：冻结件字段被钉在卡面字面量上，改了就红 |

**② 改既有文件 0 处**；新增 `migrations/versions/0020_identity.py` 与
`tests/v041/test_migration_identity.py`（都在卡上 outputs）。
`contracts/` · `flint/domain/` · `requirements.lock` · `assets/heldout_questions.yaml`
一字未动；未新增依赖。

**③ 变异考 4 咬住 + 假变异对照绿**

| 变异 | 判据 |
|---|---|
| ① 去掉 `role` 的 `CHECK` | 红 |
| ② 主键只落在 `user_id` 上 | 红 |
| ③ 列名与冻结件不符（`display_name` → `name`） | 红（5 条） |
| ④ `downgrade` 空转 | 红 |
| ⑤ 假变异对照：只改一句注释 | **第一轮红（污染）→ 清干净后绿** |

**⑤ 第一轮那个红是变异④留下的污染，不是判据的事**：
空转的 `downgrade` 把 alembic 版本戳回 `0019`，**而三张表还在**——
于是后面每一轮的 `upgrade head` 都撞 "table already exists"。
把三张表手工清掉（测试库）再验，⑤ 当场绿。

**这条值得记**：变异体如果**把环境留在半路上**，后面所有轮次的红都不可信。
变异驱动器 MUST 保证每轮起点一致——本轮是我事后发现并手工修的，
下次做迁移类变异考要先想好回滚。

**④** 装载约 9k tokens；**⑤** 禁用词六词 0 命中。

## 5. 登记未做

1. **demo 库还没迁到 0020**。本卡只迁了测试库（`flint_test`）。
   demo 库（`localhost:55432/flint`）要等 `AUTH-05` 那只假手退役时才需要——
   到时候一并迁，NEVER 现在动一个还没人用得上的表。
2. **三张表还没有任何 store**。`AUTH-02` 才写 SQL 解析器；本卡交的是**表**，
   不是读写面。
3. **`users` 没有密码/凭证列**。身份来源按工单 §8-④ 定为 `X-User-Id` 受信头
   （延续 `BE-05` 既有口径），签发与校验属网关，不在本仓。
   哪天要自建登录，那是新的一张卡与新的一列。
4. **`orgs` 可以是空表**：冻结件 `Principal` 写着「个人使用无需先建 Org」。
   所以 `AUTH-02` 的解析器 MUST 先认「归属直属」那条路，NEVER 假设人一定在某个组织里。
