# SCHEMA-03 trace — I3 SourceRegistry（空表种子）@2026-08-02

## 1 装载

SCHEMA-03 卡 + `models_v04.py` 的 I3 区 + `WORKORDER#7-K1` 一行。~1,500 字符 ≈ 1.5k tokens（3.8%）。

## 2 test-first（真红）

先写测试 → **3 failed**：`SourceRegistry` 没有 `select` 方法（SCHEMA-00 预落的只是纯数据类），
且 `SourceEntry.homepage` 是必填而测试没传。

两处各自定了：

- **补 `select(region)`**：返回该区**启用中**的源；空表 → 空集，**NEVER 抛错、NEVER 跨区回落**。
  理由写进 docstring：「该区没有源」与「取源失败」是两件事，混起来会让上层把
  「今天没数据」误报成故障。
- **`homepage` 保留必填**：没有主页的源既抓不了也审不了。测试里传空串占位，
  并在注释写明「K1 未决，NEVER 写真实站点」。

改完 **6 passed**，additive 校验 exit 0。

## 3 acceptance 映射

| acceptance | 测试 |
|---|---|
| `select(region)` 空表返回空集不抛错 | `test_select_on_empty_registry_returns_empty_for_every_region`（九区逐个） |
| （反向）NEVER 跨区回落 | `test_select_never_falls_back_to_another_region`：US 有源时 `select("JP")` 仍是空集 |
| （反向）停用源不进选集 | `test_select_excludes_disabled_entries` |
| NEVER 内置真实站点清单 | `test_no_real_site_list_is_baked_in`：扫 `models_v04.py` 的**字符串字面量**，断言无 URL、无域名 |
| 空表种子是明确状态 | `test_empty_seed_is_the_declared_baseline` |

扫站点清单那条是本卡的要害：K1 未决时最容易的失守方式是「先随手写几个大站顶着」，
那是编造——各国源的 `FetchLegalStatus` 没有 owner 结论前，任何具体站点都是猜的。
扫的是字符串字面量而不是全文，注释与 docstring 里的说明不算清单。

## 4 产出

`tests/v04/schema/test_i3_registry.py`（6 条）+ `SourceRegistry.select()`。
