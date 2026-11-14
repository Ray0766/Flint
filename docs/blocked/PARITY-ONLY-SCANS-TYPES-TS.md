# PARITY-ONLY-SCANS-TYPES-TS · 对账器只读一个文件，于是把「类型在别处」报成「没建类型」

**状态** closed · 2026-08-05 · `TYPE-04`

> **已关闭 · 2026-08-05 · `TYPE-04`**（本卡拥有 `tools/check_fe_be_parity.py`，
> 两张单一并修——它们是同一段代码上的两处病）。
>
> **改法**：`_frontend_field_names`（只读 `types.ts`、返回平集）→
> `_frontend_interfaces`（扫 `web/lib/**` 的非测试文件，**按接口分组**，
> 键是 `"文件名#接口名"`）；`_field_findings` 改用 `_best_interface` 判：
>
> 1. **至少两个字段重合**才算「这个接口是为它建的」——一个同名字段的巧合不算；
> 2. 覆盖面按**层**算：**整个接口都落在这条响应里**，它才是这条响应的一层
>    （后端 `response_keys` 是摊平的，`/plaza/hot` 那 21 键分布在四层上）；
> 3. 报「漂移」时**指名是哪个接口**（`前端在 types.ts#ComboSubmitEcho 里…`）。
>
> **结果**：`field_mismatch` 6 → **0**，`frontend_untyped_response` **真归零**
> （`TYPE-02` 那次的零是误分类得来的）。修好之后新看得见四条真缺口，已补齐类型：
> `/projects/combo` 的 `hypothesis`、`/projects/{}/report`、`/projects/{}/proposal`、
> `/projects/{}/disputes`。
>
> 阴性对照见 `tests/v041/test_parity_dynamic_path.py`——
> 每一条「现在归零了」旁边都有一条「这样必须重新报出来」。
>
> 以下为关闭前的原文，一字未改。

---

**发现者** worker / `TYPE-02` 开工时 · **发现时间** 2026-08-05
**危害** 中高 —— 它让一张卡去**重复造已经存在的类型**
**为什么停下**：修它要改 `tools/check_fe_be_parity.py::_frontend_field_names`，
而 `TYPE-02` 的 outputs 是 `web/lib/types.ts` 与一个测试文件。按工单 §五.1 登记。
**天然归属**：`TYPE-04`（它拥有 `tools/check_fe_be_parity.py`）。
**与 `PARITY-FIELD-NAMES-COMPARED-AS-ONE-FLAT-SET.md` 是同一段代码的两处病**，建议一并修。

## 缺陷

```python
def _frontend_field_names(types_file: Path) -> set[str]:
    """`web/lib/types.ts` 里声明过的字段名。静态可见的那部分。"""
```

**只读 `types.ts` 一个文件。** 而本仓的类型是**跟着各自的 client 放**的：

| 文件 | 声明的类型 |
|---|---|
| `viewsClient.ts` | `PlazaCluster` · `EvidenceCard` · `Verdict` · `VerdictGap` |
| `topicClient.ts` | `Topic` · `TopicWhyNow` · `TopicEvidence` · `ProjectTopics` · `ComboResult` |
| `interventionClient.ts` | `DisputeInput` · `EvidenceInput` · `EvidenceResult` |
| `jobClient.ts` | `JobStreamState` · `StepEvent` · `JobEventPayload` … |
| `types.ts` | Block 树那一族 + `DeliverableMeta`（`TYPE-01` 新建） |

**这种组织方式没有问题**——类型放在用它的地方，比全塞进一个大文件更好读。
有问题的是尺子只看其中一个。

## 实测：把九条端点按「全 web/lib」重新量一遍

| 端点 | 后端键数 | 只看 `types.ts` 的结论 | **全 web/lib 实际仍缺** |
|---|---|---|---|
| `/projects/{}/topics` | 16 | 「没建类型」 | **0** |
| `/topics/{}` | 14 | 「没建类型」 | 1（`topic`，信封键） |
| `/jobs/{}/verdict` | 2 | 「没建类型」 | 1（`job_id`，信封键） |
| `/clusters/{}/evidence-cards` | 6 | 「没建类型」 | 1（`evidence_cards`，信封键） |
| `/projects/{}/disputes` | 3 | 「漂移」 | 1（`current_version`） |
| `/projects/{}/evidence` | 6 | 「漂移」 | 1（`current_version`） |
| `/projects/combo` | 3 | 「没建类型」 | 2 |
| `/projects/{}/analysis` | 3 | 「没建类型」 | 2 |
| `/plaza/hot` | 21 | 「没建类型」 | **15** ← 真缺口在这里 |

**九条里只有一条（`/plaza/hot`）是真的缺一大片**，其余是信封键与个别字段。
按尺子的说法去做，会把 `PlazaCluster` / `Topic` / `EvidenceCard` 等
**已经存在且正在被使用的类型**再抄一遍进 `types.ts`——
两份定义从抄完那一刻起就开始各走各的。

## 修法

`_frontend_field_names` 扫 `web/lib/**/*.ts` 的**非测试文件**，而不是单个 `types.ts`：

```python
def _frontend_field_names(lib_dir: Path) -> set[str]:
    names: set[str] = set()
    for source in lib_dir.rglob("*.ts"):
        if ".test." in source.name or "node_modules" in source.parts:
            continue
        names |= set(re.findall(r"^\s{2,}([a-z_][A-Za-z0-9_]*)\??:", ...))
    return names
```

与另一张单（按接口分组）**一起改**更省：分组之后，
「哪个文件的哪个接口」自然就能报出来，定位活不必再退回给人。

## `TYPE-02` 本轮怎么处置

1. **不重复造类型**——已有的就是已有的；
2. **真缺的那些补上**，重点是 `/plaza/hot` 的 15 个（弱信号与热度分量）；
3. 判据判**真正要紧的那条性质**：**后端发出的每个字段，在 `web/lib` 里都有一个
   带类型的落点**——比「`types.ts` 里有没有」严格得多，也不会逼人重复定义；
4. **acceptance③（`frontend_untyped_response` 归零）在本单修好之前达不成**，
   已在 `TYPE-02` 的 trace 写明。
