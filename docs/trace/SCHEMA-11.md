# SCHEMA-11 trace — I11 ShareLink + friend 缝 @2026-08-02

## 1 装载
SCHEMA-11 卡 + `models_v04.py` 的 I11 区。~800 字符 ≈ 0.8k tokens（2%）。

## 2 test-first（真红 3 条）
先写测试 → **3 failed**：预落的 `ShareLink` 没有 `password_hash`，也没有 friend 通道。
补齐后 **6 passed**，additive exit 0，全套 76 passed。

## 3 两条判断
**① 明文口令连字段都不能有**：要求不是「别往里写明文」，而是**连放明文的地方都不留**。
只要存在 `password: str` 字段，就一定有人在某个构造点把明文塞进去——
然后它随 `ShareLink` 一起进日志、进快照、进导出。契约里只留 `password_hash`，
明文必须在进入模型之前就消失。测试两侧都断：`password` 不在、`password_hash` 在。

**② friend 缝抛错而不是 flag**：留一个 `enabled=False` 的开关，意味着有人打开它就「能用」——
而背后没有好友关系模型、没有鉴权路径。`NotImplementedError("friends: post-v1")` 是唯一诚实的占位：
调用点存在、语义已定、实现明确没有。`test_friend_channel_is_not_a_flag` 反向断言
`ShareLink` 上**没有任何 friend 相关字段**。

## 4 acceptance 映射
| acceptance | 测试 |
|---|---|
| password 明文字段不存在（仅 hash） | `test_no_plaintext_password_field_exists` + `test_password_hash_is_optional_and_defaults_to_none` |
| friend 通道抛 `NotImplementedError('friends: post-v1')` | `test_friend_channel_raises_not_implemented`：错误文本**逐字**断言（`str(err.value) == "friends: post-v1"`） |
| （不越界） | `test_friend_channel_is_not_a_flag` |
| （附带）过期与撤销分离 | `test_expiry_and_revocation_are_separate_states`：过期可续期、撤销不可逆，NEVER 合并成一个 bool |

## 5 产出
`tests/v04/schema/test_i11_share.py`（6 条）+ `ShareLink.password_hash` + `share_with_friend()`。
