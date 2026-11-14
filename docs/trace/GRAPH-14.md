# GRAPH-14 trace — 多工作台数据层 + archived @2026-08-02

## 1 装载
GRAPH-14 卡 + `WORKORDER#5-F18` + `#7-K6` + SCHEMA-08 的 `WorkbenchGraph.archived`
+ `flint/config.py` 的 flag 命名口径（E8）。~1,400 字符（3.5%）。

## 2 test-first
先写测试 → collection error → 实现 → **13 passed**；ruff 净、mypy 246 文件净。

## 3 为什么数据层先行、入口 flag 必须关
K6 未决：多工作台的**交互稿还没出**。数据层可以先做（多台存储、归档、按 owner 列举都是确定的），
但**入口 flag 必须 off**——打开一个没有交互稿的入口，用户会遇到
**一半能用一半不能用**的界面，那比「暂时只有一台」糟得多。
K6 落地后打开 flag 即可，不必改代码（`test_flag_can_be_turned_on_explicitly_when_k6_lands`）。

**flag 是必填参数**：默认关不能靠「调用方记得传空 dict」——不传就该是个错误，
而不是悄悄取到某个可变全局的当前值（`test_flag_default_is_not_read_from_a_mutable_global`
用 `pytest.raises(TypeError)` 守着）。

## 4 archived 不是 delete
归档的台**仍然存在**、仍可翻回；列举默认不含归档台，显式要时能拿到，内容一字不少。
`test_no_delete_path_exists` 断言导出面上没有 `delete_workbench`/`drop_workbench`/`purge_workbench`——
**数据删除是 owner 人审节点，v0.4 内 NEVER 有这条路径**。

## 5 产出
`flint/graph/multi.py`、`tests/v04/graph/test_multi_workbench_store.py`（13 条）。
