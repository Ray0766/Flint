# FIX-10 · 空假设：一个码、一句话

> v0.4.1 第 6 批第十一张。全量 `pytest -q` **4468 passed / 0 failed**。

## 装载清单

`tasks-v041-b6.json#FIX-10` · `docs/blocked/EMPTY-HYPOTHESIS-TWO-CODES.md` ·
`flint/topic/create.py#_require_str` · `flint/graph/store.py`（H8 复用那一行）·
`flint/api/{combo,graph_edges,schemas}.py` · `web/lib/topicClient.ts` ·
`tests/v041/test_analysis_entry_screens.py`（CHAIN-04 的既有口径）。
约 11k tokens，**未超 40k**。

## 一、开工第一件事：分叉到底在哪

单子说的是「两条端点两个码」。查下去发现——**分叉从来不在校验器上**：

```
flint/topic/create.py#_require_str        ← 唯一的校验，抛 "hypothesis required (non-empty str)"
flint/graph/store.py:28                   ← 逐字写着「H8: 复用 combo 的 hypothesis 校验语义」
```

两条端点抛的是**同一个异常、同一句话**。分叉只在 `except` 那一层的 HTTP 映射：
combo 一律 400 `VALIDATION_FAILED`，graph_edges 一律 422 `EMPTY_HYPOTHESIS`。

**这件事决定了修法**：要动的是映射，不是校验器，更不是「统一两套规则」。

## 二、统一到 `EMPTY_HYPOTHESIS` / 422

`ErrorCode` 的注释逐字说明了它为什么单列：

> 「边上没写假设」与「请求体格式不对」的修法完全不同，
> 前端要据此把光标送回假设输入框而不是弹一句通用报错。

把它并回 `VALIDATION_FAILED` 就是**把那句注释作废**——顺带把一条产品行为删掉。
反过来，combo 的**其余**校验失败（卡数不对、卡不存在）仍是 `VALIDATION_FAILED`，
它们确实是「请求体不对」。判据里有一条阴性对照钉着这一半。

## 三、那句话从校验器身上取，NEVER 手抄

新建 `flint/api/errors.py`。它在**导入期真调一次** `_require_str({}, "hypothesis")`，
把抛出来的消息捕获下来当唯一真相：

```python
EMPTY_HYPOTHESIS_MESSAGE = _derive_empty_hypothesis_message()
```

校验器哪天改了措辞，映射与判据自动跟着走。**手抄一份的话，改了一处而另一处没改时，
判据仍然是绿的**——而两条端点会开始说两句话，正是这张单子的由来。

分辨也用**逐字相等**而不是子串猜测：猜的话，一条「hypothesis 里有非法字符」
之类的新错误会被当成「空假设」，而它们的修法不同。

## 四、改了三个既有文件

| 处 | 改前 | 改后 | 为什么非改不可 |
|---|---|---|---|
| `flint/api/combo.py` | `_error(400, "VALIDATION_FAILED", …)` | `origin_validation_error(err)` | 答复变了（空假设那条），且映射不能留在这里 |
| `flint/api/graph_edges.py` | `_error(422, "EMPTY_HYPOTHESIS", …)` | 同上 | **答复没变**，变的是它从哪来——各写一个 `except` 的后果是下一条端点照着最近的那个抄，而它抄到哪一个取决于作者先看到哪一份 |
| `web/lib/topicClient.ts` | `"combo hypothesis is required"` | 后端那一句 | 规格 #2.3 要「前端本地预检话术与之逐字一致」 |

**预检不删**：它省的是一次注定被拒的往返。统一话术之后最容易顺手做的事就是
「反正后端会拒，前端别判了」——那样用户每打错一次都要等一个来回。判据钉着它还在。

## 五、判据里两条最值钱的

1. **阴性对照**：combo 其余失败仍是 `VALIDATION_FAILED`。
   没有它，把整个异常一律映成 `EMPTY_HYPOTHESIS` 也能让「两处一致」为真——
   而那时「卡数不对」会告诉用户「假设是空的」，光标被送到一个没有问题的输入框；
2. **扫全仓**：凡接住 `OriginValidationError` 的 `flint/api/*.py` 都要走这个映射。
   只判那两条的话，第三条端点漏了不会有任何东西响——
   而「新增端点漏了则判红」正是卡面 acceptance③。

## 六、动了一条既有判据（前提过期）

`tests/v041/test_analysis_entry_screens.py::test_the_two_codes_gap_stays_registered`
写的是「两码不一致的单必须还开着」。统一之后它红了——**红的是自己的前提过期**。
改成判「那件事真的做完了」：映射模块在 + 单据关。

同一份文件的 docstring 里那段「存哪一句都会与另一条端点对不上」也订正了：
**那两屏仍然一句拒绝话都不写，但理由换了**——现在是「屏上显示的拒绝话恒由服务端说」。
并写明它与 `topicClient.ts` 的区别：**「用同一句」与「自己编一句」是两件事**。

## 七、verify

```
pytest tests/v041/test_empty_hypothesis_one_code.py -q  → 9 passed（含 2 条 compose）
pytest tests/v04/graph tests/v041/test_analysis_entry_screens.py -q → 48 / 28 passed
pytest -q（全量）                                        → **4468 passed / 0 failed**
ruff / mypy --strict flint                               → 全绿 / 306 files
cd web && npx tsc --noEmit / npm test -- --run           → exit 0 / 805 passed
check_line_endings                                       → 219 个文件全是 LF
```

## 八、self_review

① 判据覆盖 acceptance 四条，含两条阴性对照与一条全仓扫描；
② 零冻结件改动；③ 无禁用词；④ 改动面：`flint/api/errors.py`（新）+
`flint/api/{combo,graph_edges}.py` + `web/lib/topicClient.ts` + 判据，
**全在卡上 outputs**（`flint/api/` · `web/` · 测试）；⑤ 装载 ≈11k tokens。

## 九、留给下游

映射只有一处了。**下一条接 `hypothesis` 的写端点**只要 `except OriginValidationError`
里转调 `origin_validation_error(err)` 即可；忘了的话第五节那条全仓判据会红。
