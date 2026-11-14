# SCANNERS-DO-NOT-STRIP-COMMENTS · 注释里写一句路径，扫描器把它当成一次真调用

**状态** closed · 2026-08-06 · `GAUGE-10`

**发现者** worker / `TYPE-04` 执行中（被绊了两次）· **发现时间** 2026-08-05
**危害** 低—中 —— 不是产品缺陷，是**尺子的假阳性**；后果是「注释写清楚一点」反而被判红
**为什么停下**：`tools/check_fe_be_parity.py` 那一处本卡已修（它是本卡 outputs）；
`tests/v041/test_fe_api_contract.py` 里**另有一份独立扫描器**，同样不剥注释——
改它超出本卡 outputs。

## 实测：同一句注释绊了两把尺子

给 `web/lib/types.ts` 写了一句说明：

```ts
// `/projects/{}/proposal` 与 `/projects/{}/report` 此前藏在
// `/projects/{}/{}` 那条「扫不动」里
```

**两把尺子都把它读成了真调用**：

| 尺子 | 报了什么 |
|---|---|
| `tools/check_fe_be_parity.py` | `dynamic_path_not_checked: /projects/{}/{}`（本卡已修） |
| `tests/v041/test_fe_api_contract.py` | `web/lib/types.ts:158 GET /projects/{}/proposal —— 路径在，但方法不允许（后端允许 ['POST']）` |

根因一样：扫描器在**字符串字面量**里找路径，而 `//` 注释里的
反引号 `` ` `` **本身就长得像模板串**。

`check_fe_be_parity` 的模块注释一直写着「只在字符串里找，是为了把**注释**排除在外」——
**那句话对反引号引的路径不成立**。

## 已修的那一半

`tools/check_fe_be_parity.py` 加了 `_without_comments`：先剥 `/* */`，
再按行剥 `//`（`splitlines` 认所有换行形态）。
判据 `tests/v041/test_parity_dynamic_path.py::test_a_comment_that_mentions_a_path_is_not_read_as_a_call`
与它的阴性对照（剥注释别把真调用一起剥了）都在。

## 没修的那一半

`tests/v041/test_fe_api_contract.py` 自带一份扫描器。**本卡绕行方式**：
把 `types.ts` 那句注释改成不带反引号的写法，并在注释里注明为什么这么写。

**这是绕行，不是修好。** 下一个人写注释时还会踩：
一句诚实的说明性注释，会让全局门红。

## 修法

把 `check_fe_be_parity._without_comments` 提出去共用，或在
`test_fe_api_contract.py` 的扫描器里加同一段。
**顺带把那两处「只在字符串里找就等于排除了注释」的说明改掉**——
文档与行为不一致时，下一个人会照文档去查，然后查错地方。

**注意与既有单 `CRLF-BREAKS-COMMENT-STRIPPING` 的关系**：那张单说的是
JS 侧尺子按 `\\n` 剥注释、遇 CRLF 失效。本单是 Python 侧**根本没剥**。
两处都是「剥注释」这件事没做对，建议一并处置。

---

## 关闭（`GAUGE-10` · 2026-08-06）

第二把尺子补上了剥注释。**它不在本单猜的那个文件里**：
本单写着「`tests/v041/test_fe_api_contract.py` 里另有一份独立扫描器」，
而那个测试只是**调用方**，扫描器在 `tools/check_fe_api_contract.py#frontend_calls`。
改在真地方，卡面 outputs 那两处照旧写判据。

**剥法与第一把不同，因为要保住行号**：本工具报的是 `file:line`，
整段删掉注释会让后面每一行左移——尺子于是指向别处，
而**一个指错地方的红比不报更糟**（人会去改一段本来对的代码）。
所以用 `_blank_comments`：把注释字符换成**等长空白**、换行原样留着，
偏移量逐字节不变。它还带一个引号状态机，免得把 `"http://x"` 里的 `//` 当注释。

**改前实测**（一句注释 + 一处真调用）：

```
line   5  GET   /account                  ← 唯一的真调用
line   1  GET   /projects/{}/proposal     ← 注释
line   1  GET   /projects/{}/report       ← 注释
line   2  GET   /projects/{}/{}           ← 注释
line   3  GET   /billing                  ← 块注释
```

**改后**：只剩 `line 5 GET /account`，且行号仍是 5。

两份说明里那句「只在字符串里找就等于排除了注释」都改掉了，
并写明根因（**反引号本身长得像模板串**）——
文档与行为不一致时，下一个人会照文档去查，然后查错地方，本单正是这么绊了两次。

**判据**：`tests/v041/test_scanner_strips_comments.py`（9 条）——
两把尺子分别验、真调用仍被抓到（阴性对照：剥过头时上面两条照样绿）、
行号不漂、两份说明都写了根因、兄弟单 `CRLF-BREAKS-COMMENT-STRIPPING` 仍挂着。

## 兄弟单没有一并关掉

本单末尾建议「一并处置」`CRLF-BREAKS-COMMENT-STRIPPING`（JS 侧尺子按 `
` 剥、
遇 CRLF 失效）。**本卡没动它**：那是另一把尺子（JS 侧），改动面在本卡 outputs 之外。
两处是同一件事的两半，**NEVER 修了一半就当整件事完了**——所以那张单仍 open，
且本卡的判据里有一条专门确认它还在。

