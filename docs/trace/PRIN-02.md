# PRIN-02 trace — 七条原则的反例 fixture 集 @2026-08-02

## 1 装载清单（§2.3）

| 装了什么 | 字符 |
|---|---|
| PRIN-02 卡 | ~450 |
| `docs/PRINCIPLES-v04.md`（本卡 inputs） | 3,266 |
| `tools/check_principles_doc.py` 的解析函数签名（复用对象） | ~600 |
| **合计** | **~4,300**（≈4.3k tokens 最坏口径，预算 40k，占 10.8%） |

`context_refs` 的 `contracts_v04/` 仍不存在（SCHEMA-00 才建）；本卡不产生类型，未装载。

## 2 test-first（§4.2）

1. 先写 `tests/v04/principles/test_fixtures_load.py`；
2. 跑 → **红**：`ModuleNotFoundError: No module named 'tests.v04.principles.fixtures'`（收集期即失败）；
3. 再写 loader 包 + 生成七份 fixture → **5 passed**。

## 3 acceptance 映射

| acceptance | 对应测试 | 怎么算数 |
|---|---|---|
| 每条原则对应 1 个反例 fixture 且可被后续校验测试 import | `test_seven_fixtures_exist_and_are_importable` | 断言编号数 == 7，且**走的就是后续测试将来那条 import 路径**（`from tests.v04.principles.fixtures import load`），不是读文件路径糊弄 |
| （同上，一对一） | `test_one_fixture_file_per_principle` | 文件名集合 == 文档里的编号集合，防出现没人认领的孤儿样本 |
| fixture 内容与原则反例段一一对应 | `test_fixture_matches_the_counterexample_section_verbatim` | 测试**独立地从文档重解析**再比对，不是读 fixture 自证 |
| （反空转） | `test_comparison_is_not_vacuous` | 阳性对照：篡改一条后必须判不等，否则「一一对应」可能只是恒真 |
| （落盘格式） | `test_fixture_files_are_utf8_json_without_bom` | 后续测试与 CI 直接 `json.loads`，不做编码猜测 |

## 4 复用（§4.3②）

Markdown 解析**复用** `tools/check_principles_doc.py` 的 `split_principles`，
NEVER 在 fixtures 包里新写第二份解析器——两份解析器就会有两种口径，
「与反例段一一对应」这条断言也就失去意义。H1~H8 无命中（本卡不碰运行期通道）。

fixture 由 `regenerate()` 从文档生成，**NEVER 手敲**；`regenerate()` 放在 fixtures 包内
（属本卡 outputs），所以重生成能力留在仓库里，不依赖一次性脚本。

## 5 产出

| 文件 | 说明 |
|---|---|
| `tests/v04/principles/fixtures/__init__.py` | loader + `regenerate()`；ruff 净 |
| `tests/v04/principles/fixtures/{A3,B4,B5,B7,B8,B9,B10}.json` | 七份反例样本，UTF-8 无 BOM |
| `tests/v04/principles/test_fixtures_load.py` | 5 条断言，全绿 |

反例条目数：A3=3、B4=2、B5=1、B7=2、B8=1、B9=1、B10=2（切分规则：去句末「。」后按「；」切；
本节反例句里「；」只出现在顶层分隔位，括号与反引号内没有）。
