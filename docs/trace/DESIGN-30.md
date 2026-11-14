# DESIGN-30 trace — G5 模板注册表 @2026-08-02

## 1 装载
DESIGN-30 卡 + SCHEMA-10 的 `TemplateRecord`/`template_checksum` + E6 新降级行。~1,300 字符（3.3%）。

## 2 test-first
先写测试 → collection error → 实现 → **10 passed**；ruff 净、mypy 245 文件净。

## 3 「不可用」的两种后果（E6）
- **固化与生产渲染阻断**：把一个存不进注册表的模板当成「已固化」，
  下次生产渲染会找不到它——**而那时用户已经拿它出过东西了**；
- **探索期不阻断**：试样式、看预览不需要注册表参与。

把两者一起阻断会让一次存储故障变成「整个设计台不能用」。
所以报错文本 MUST 写清**什么还能做**（`test_blocking_message_says_what_still_works` 守着）。

## 4 去重按内容，不按名字
模板的身份是它的**内容**：改个名字不构成新版本（`test_dedupe_ignores_name_changes`），
换了 HTML 才是。

**checksum NEVER 作为入参**：能传就意味着能传错，而传错之后
「版本号没变、内容已变」就成立了（S2-2 第三条铁律：产物可复现）。
`test_checksum_mismatch_is_impossible_by_construction` 断言签名里没有 `checksum` 参数、
只有 `checksum_of` 计算函数。

## 5 旧版本不被覆盖
注册表是 append-only 的版本序列：固化过的东西可能已经被别人拿去渲染了，
覆盖它等于让那些产物失去出处（`test_new_content_bumps_the_version` 断言两条都在）。

## 6 产出
`flint/design/__init__.py`、`flint/design/templates/{__init__,registry}.py`、
`tests/v04/design/test_template_registry.py`（10 条）。
