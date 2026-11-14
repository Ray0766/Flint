# REGION-CN-HK · DEC-056 说「其余七区」，而实际是八区

**状态** open · 2026-08-11 · `REGION-CN-HK`

## 事实

`DEC-056` 原文两处写「其余七区」：

> · CN 区 = 微博，HK 区 = Google 趋势，两区都进「本版有内容」的范围；**其余七区**照旧明说
>   「本版暂无该区内容」，CN-02 那三句不同的空态一条都 NEVER 合并；
> · **其余七区** NEVER 顺手打开，那是下一版的事。

而 **HK 原本不在清单 A2 的九区里**：

```
Region = Literal["CN", "US", "AU", "SG", "JP", "KR", "GB", "IT", "FR"]   # 改前
```

九区去掉 CN 剩八个（US/AU/SG/JP/KR/GB/IT/FR）。HK 加进来之后一共十区，
CN 与 HK 之外**是八个**，不是七个。

「七」这个数只有在「HK 本来就在九区里」时才成立——而它不在。

## 这一处怎么处置的

| 落点 | 写的是什么 | 为什么 |
|---|---|---|
| `DECISIONS-v04.md` | **原文一字不改**（含「七区」） | 那是**记录**。改它就等于修改 owner 说过的话 |
| `flint/region/version_scope.py` | 「其余八区（US/AU/SG/JP/KR/GB/IT/FR）」 | 那是**执行**。代码里写错数，下一版解除收窄时会漏掉一个区 |
| `contracts_v04.models_v04.Region` | 十个成员 | 「两区都可切」要求 HK 是个真的可选区 |

**NEVER 为了对上那个「七」去删掉一个区**：`DEC-056` 的裁决是「其余各区照旧暂无内容」，
那一句在八个区上照样成立；而删区会真的拿掉一个下一版要用的能力
（`DEC-045` 原话：收窄的是呈现，NEVER 删代码）。

## 为什么这不算「自行择一」

裁决本身**没有歧义**：CN 与 HK 在范围内，其余全部在范围外，各自明说暂无内容。
七还是八不改变任何一行行为——它只改变一句描述里的数字。
所以这里按事实写数并把差异摆出来，而不是停下等回话。

**要 owner 确认的只有一件**：`Region` 从九个成员加到十个这件事本身。

- 它是**加成员不是改口径**：`tools/check_frozen_additive.py` 对 Literal 别名按
  「成员集合 base ⊆ v04」比，加成员明确允许；
- 且 `Region` 是 v0.4 纯新增，**原冻结件 `contracts/models.py` 里没有它**，原件零触碰；
- 但清单 A2 那份纸面规格写的是「九地区」——**纸面与代码今天对不上了**。

若 owner 认为清单 A2 也要跟着修订，那是 PDD 变更通道的事，不是本卡能办的。

## 判据

`tests/v041/test_region_cn_hk.py::test_the_count_discrepancy_is_on_the_record`
读这份单据；`::test_both_regions_are_in_scope_and_the_rest_are_not` 断言其余区
**是八个且一个都没被打开**。
