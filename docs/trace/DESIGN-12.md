# DESIGN-12 trace — 评论批注（data-loc 锚 + 坐标降级 + 让 AI 处理）@2026-08-03

## 1 装载清单（§2.3）

- `CLAUDE.md#S2+S3`、`worker.md`、卡片 `tasks-v04.json#DESIGN-12`；
- context_refs：`WORKORDER-v04.md#5-G`（G17 一行）；
- 前置产物：`web/design/direct-edit/directEdit.ts`（DESIGN-10 的 data-loc 语义）、
  `flint/design/session.py`（DESIGN-01 的「只产数据、提交走既有通道」写法）、
  `tests/v04/_source_scan.py`、`web/test-utils/source.ts`。
- 实测装载 ≈ 7k tokens，未超 40k。

## 2 关键设计判断

**锚会失效，评论不会**。用户写下那句话时页面还长着另一个样子；后来那个元素被改没了，
评论就没了着落。此时把它藏起来，用户会以为自己的意见**被系统吃掉了**——
而它其实还在，只是钉不住原来那个位置。所以降级到坐标锚，并明说位置可能不准。

三种锚态：`element`（data-loc 还在）→ `point`（元素没了但有坐标）→ `orphan`（两者都没）。
**orphan 仍然渲染**，但不给「让 AI 处理」——一条指不出地方的意见交给模型，
只会让它凭空动手：改了别处，而用户说的那处没动。

**降级提示只在降级时出现**：常驻的提示等于没有提示。

**注入的是「评论 + 锚」而不是只有正文**：一句「这里太挤了」离开它所指的元素就没有意义，
模型会去猜是哪一处挤。

**只注入点了「让 AI 处理」且未解决的**：反复把已经改完的意见塞给模型，
它会反复改同一处——用户会觉得系统在跟自己较劲；没点过的评论则是他写给自己或同事看的。

**顺序照用户给的来**：重排会让「先改这个再改那个」这种意图丢掉。

**两侧都不越界**：前端评论层不改 HTML（四个词源码断言），后端只产上下文、
不 import JobRunner、不碰队列（AST 断言，§6-H7）。

## 3 acceptance ↔ 测试映射

| acceptance | 测试名 |
|---|---|
| 元素消失 → 坐标锚降级仍可见 | 前端 `元素没了：降级到坐标锚，且明说已降级`、`元素消失的评论仍然可见`、`降级的评论带得出提示`、`没降级的评论不挂那条提示`、`元素没了又没有坐标：标为失锚`；后端 `test_degraded_anchor_is_carried_as_coordinates` |
| 「让 AI 处理」注入下一 job 上下文 | 前端 `「让 AI 处理」把这一条交出去，带上它的锚`、`失锚的评论不给「让 AI 处理」`；后端 `test_payload_carries_the_comment_and_where_it_points`、`test_context_takes_only_requested_and_unresolved`、`test_context_keeps_user_order`、`test_context_is_empty_when_nothing_was_requested`、`test_payload_is_a_plain_dict_not_the_entity` |
| （边界与纪律） | 后端 `test_anchor_without_either_is_rejected`、`test_empty_comment_text_is_rejected`、`test_module_never_opens_its_own_job_channel`；前端 `已解决的评论不渲染在层上`、`评论层不改 HTML`、`文案 key 化` |

## 4 一次语法错

`DesignComment` 里又误留了一个裸 `/`（与 DESIGN-11 同款笔误），Python 直接 SyntaxError；
改为一行注释说明 `ai_requested` 的含义。**同一个笔误两次**，下次写 dataclass 时
先跑一遍 import 再往下写。

## 5 verify（卡上 verify_cmd 是合取，两段分别在各自 cwd 跑）

```
$ cd web && npm test -- --run design/comments        → 11 passed
$ pytest tests/v04/design/test_comment_job.py -q      → 9 passed
```

回归：`pytest tests/v04/design` 41 passed；前端全套 395 passed / 49 files；
typecheck 干净；`ruff` 全绿；`mypy --strict flint` 260 文件净；
`i18n_scan web/design` exit 0；禁用词 0。

## 6 产出

- `flint/design/comment_job.py`、`tests/v04/design/test_comment_job.py`（9 条）
- `web/design/comments/CommentLayer.tsx`、`CommentLayer.test.tsx`（11 条）
- `web/messages/{zh,en}.json`：各 +2 key（77 键，键集一致）
