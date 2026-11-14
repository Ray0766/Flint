# SCHEMA-09 trace — I9 Favorite（内嵌快照 + P1 采纳位）@2026-08-02

## 1 装载
SCHEMA-09 卡 + `WORKORDER#9-P1` + `models_v04.py` 的 I9 区。~1,300 字符 ≈ 1.3k tokens（3.3%）。

## 2 test-first（真红 4 条）
先写测试 → **4 failed**。SCHEMA-00 预落的是 `snapshot_id` 引用 + `stale`，
卡要的是 **`evidence_snapshot` 内嵌 JSON** + **`snapshot_stale` 默认 False**。校正后 5 passed。

## 3 为什么基线是「内嵌」而不是「引用」
收藏要能长期翻回。只存 `snapshot_id` 的话，被引 snapshot 被 180 天周删清掉之后，
收藏就变成一个**指向空处的壳**——「已收藏但内容已被清理」。内嵌之后收藏自带内容，
不依赖别人活着。

`§9-P1` 提案的做法是改回引用 + 给被引 snapshot 加冻结保护。那是**提案**，
owner 未采纳前 NEVER 实现 —— 本卡只在**替换位**留 `#` 注释，写明采纳时怎么改、要同步 E2 的哪一条。

## 4 一次自纠：断言写法把散文当成了代码
`test_p1_replacement_site_is_marked_as_comment_only` 初版用「行不以 `#` 开头 = 代码行」来判定
`snapshot_id` 是否成了真字段。结果 docstring 里那句解释「若只存 snapshot_id 会怎样」的**散文**
被当成代码行，测试红在一个本来正确的实现上。

改法：**「是不是真字段」以 `__dataclass_fields__` 为准**（那才是权威），
注释存在性另行断言。反证：把 `snapshot_id` 真加成字段后该条立刻变红（4 failed），还原后 5 passed。

## 5 acceptance 映射
| acceptance | 测试 |
|---|---|
| evidence_snapshot 内嵌 JSON | `test_evidence_snapshot_is_embedded_json`（原样保存） |
| snapshot_stale 默认 False | `test_snapshot_stale_defaults_to_false`——新收藏还没被 Revalidator 算过；置 True 只能来自后端统一口径（§6-H1） |
| P1 采纳位以注释标记，不实现 | `test_p1_replacement_site_is_marked_as_comment_only`：注释在 + 字段不在，两侧都断 |
| （基线不依赖外部存活） | `test_favorite_survives_without_any_snapshot_id_reference` |

## 6 产出
`tests/v04/schema/test_i9_favorite.py`（5 条）+ `Favorite` 内嵌快照形状与 P1 注释位。
