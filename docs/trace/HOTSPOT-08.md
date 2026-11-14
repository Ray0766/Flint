# HOTSPOT-08 trace — 只读外链（viewer + 过期/密码 + 越权）@2026-08-02

## 1 装载
HOTSPOT-08 卡 + SCHEMA-11 的 `ShareLink`（含 `password_hash`）+ `flint/api/analysis.py`
的既有鉴权写法（H2 复用对象）。~1,800 字符（4.5%）。

## 2 test-first
先写测试 → collection error → 实现 → 1 failed（见 §4）→ 修 → **14 passed**；ruff 净、mypy 240 文件净。

## 3 三个状态码为什么不合并成 404
- **410**：链接曾经有效、现在过期或被撤销 → 告诉持链人「你没走错，它到期了」，
  这决定他是去找人续期还是以为拿错了链接；
- **401**：需要口令而没给对；
- **403**：链接有效、身份也对，但**这个动作**不允许（只读链上的写请求）。

全报 404 看起来更安全，实际是把三种完全不同的处境糊成一句「没有」，让持链人无从判断下一步。
真正需要藏的是「这个 token 存不存在」——那一种才用 404（枚举防护属路由层，本卡不涉及）。

**判断顺序**：先「还有效吗」再「你是谁」。反过来会把「已过期」泄露成「口令错」，
也让一条死链接还能被拿来试口令（`test_expiry_is_checked_before_password`）。

## 4 一处真实的坑：isinstance 跨两个模块实例恒 False
首轮 `test_anonymous_viewer_is_a_principal` 红。查因：测试顶部用
`spec_from_file_location` **另加载了一份** `models_v04`，而实现走
`from contracts_v04.models_v04 import Principal` —— 两个不同的类对象，isinstance 恒 False。
**错的是断言的取法，不是实现**。改成按实现的导入口径取类型后转绿，教训写进了该测试的 docstring。

## 5 acceptance 映射
| acceptance | 测试 |
|---|---|
| 匿名 viewer 走同一 auth 通道（H2） | `test_anonymous_viewer_is_a_principal`（复用既有 `Principal`）+ `test_viewer_id_is_stable_for_the_same_token`（id 带 token 便于审计追到是哪条链接）+ `test_module_reuses_existing_principal_type`（源码里 NEVER 出现 `class ViewerPrincipal`/`AnonymousUser`/`ShareIdentity`） |
| 过期 410 | `test_expired_link_is_410` + `test_revoked_link_is_410_too`（撤销与过期是同一类处境） |
| 密码错 401 | `test_missing_password_is_401` / `test_wrong_password_is_401` / `test_correct_password_passes`（阴性对照） |
| 改写请求 403 | `test_write_request_is_403`（GET/HEAD 放行） |
| 明文密码不落库 | `test_password_is_hashed_not_stored_plain` + `test_share_link_has_no_plaintext_password_field` + `test_error_never_echoes_the_password`（**报错文本会进日志**） |

口令比对用 `hmac.compare_digest`。fixture 档用固定盐 + sha256；
生产实现应换 per-link 随机盐 + argon2（选型属 K 组），已写在模块 docstring 里。

## 6 self_review（self_review=true）
① 见 §5；② 冻结件未动；③ 无禁用词；④ H2 复用由源码断言守着；⑤ 装载 1.8k tokens（4.5%）。

## 7 产出
`flint/share/__init__.py`、`flint/share/links.py`、`tests/v04/share/test_link.py`（14 条）。
