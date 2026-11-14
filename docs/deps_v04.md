# v0.4 新增依赖登记（DEC-006）

> `CLAUDE.md` S2-6：新增依赖 MUST 先过 RegistryValidator（存在性 + 最新稳定版），
> 版本 MUST 锁死写入 lock 文件；**registry 校验不可用时 NEVER 引入新依赖**。
> 本轮网络授权是 **owner 一次性放行、仅 npm registry、仅 next-intl 一个包**（DEC-006）；
> 装完即回归离线纪律（§4.3⑤ / S2-7）。

## 一、next-intl（I18N-01）

| 项 | 值 |
|---|---|
| 生态 | npm |
| 校验器 | `flint/registry/npm.py#check_npm`（与 `flint/registry/pypi.py` **同一套两态口径**） |
| 校验时刻 | **2026-08-02T13:16:38Z** |
| `exists` | **True** |
| `latest_stable` | **4.13.4** |
| 采用版本 | **4.13.4**（= latest_stable，精确钉死） |
| 写入位置 | `web/package.json` → `"next-intl": "4.13.4"`（`--save-exact`，**无 `^`/`~`**） |
| lockfile | `web/package-lock.json` 已含 `node_modules/next-intl`，带 `resolved` + `integrity` |

**为什么取 latest_stable 而不是「最新」**：npm 的 `dist-tags.latest` 可能被指到预发布上。
校验器只认纯数字段版本（`1.2.3` 形态），`-rc` / `-beta` 一律非稳定——
这条与 PyPI 客户端逐字同源，NEVER 另立一种口径。

## 二、两态判别（为什么必须分开）

- **404 = 包不存在**（`exists=False`，可讨论替换）；
- **网络错误 / 非 200 非 404 = 校验不可用**（`RegistryUnavailable`）→ **NEVER 引入**。

把两态混成一个，就会在 registry 抽风时把包判成「不存在」，
然后有人「顺手」换一个包——那是最坏的一种依赖决策。
离线断言见 `tests/v04/deps/test_npm_registry.py`（respx 拦截，零真实网络）。

## 三、本轮**没有**引入的东西

除 `next-intl` 外**零新增依赖**（DEC-006 明令）。
`npm install` 过程中出现的 `sharp` / `@parcel/watcher` / `@swc/core` 三条
`allow-scripts` 警告属既有依赖树的安装脚本提示，**未批准执行**，也未新增任何直接依赖。

## 四、离线纪律恢复点

本文件写毕即视为网络授权用尽：此后 `LLMProvider` 与 `Translator` 恒 fixture 注入，
测试层 respx 护栏照旧，**NEVER 再有真实网络调用**。
