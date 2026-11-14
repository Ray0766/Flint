# `SHELL-02`：卡面要「存得住」，而 outputs 够不着存它的那一列

**状态** closed · 2026-08-09 · `SHELL-02`（`DEC-050` 解阻）

**开单人**：worker，第 9 批（2026-08-09）。
**性质**：**不是设计问题，是卡面 outputs 漏了一处**——一句话就能解开。

## 现象

`SHELL-02` 的 acceptance④ 写着：

> 选择要存得住：刷新后仍是上次选的（`prefs` 表），**NEVER 只存在内存里**

而卡面 outputs 只有两项：

```json
"outputs": ["web/components/shell/", "tests/v041/test_theme_toggle.py"]
```

**存主题需要后端那一列**，而那一列在三个 outputs 之外的地方：

| 要动的东西 | 在哪 | 在 outputs 里吗 |
|---|---|---|
| `prefs` 表加 `theme` 列 | `migrations/versions/0026_*.py` | ✗ |
| `Prefs` 加 `theme` 字段 + 越界值校验 | `flint/profile/prefs.py` | ✗ |
| `GET/PUT /settings/locale` 认这根轴 | `flint/api/settings.py` | ✗ |
| 右上角三态控件 | `web/components/shell/` | ✓ |

本批 rules 写死：「改动面大于卡上 outputs → 停下走 `docs/blocked/`」。
所以停在这里，**NEVER 自己把 outputs 扩了当没发生**。

## 为什么不能绕开那一列

**绕法一：存进 `localStorage`。** 不行——
`DEC-047` 与卡面都写着靠 `prefs` 表，而且同一批的 `SHELL-01` 有一条判据
（`test_the_choice_is_written_to_the_server_not_kept_in_memory`）**逐字禁掉了
`localStorage` / `sessionStorage`**，理由是 `flint/profile/prefs.py` 文件头那句
「跨设备一致不是附加功能，它就是『服务端为真相』的可观测形式」。
主题走浏览器存储的话，同一个人在两台设备上看到的东西不一样，
而他从没在第二台上选过。

**绕法二：塞进现有的两根轴。** 不行——
`PUT /settings/locale` 的请求体是 `extra="forbid"`，多一个 `theme` 当场 422；
而把主题编码进 `lang` 或 `region` 是把三件事塞进两个格子，
`PRINCIPLES#A3` 那两条轴当场作废。

**绕法三：只做控件、不做持久化。** 那是**交付一个半成品**：
控件切得动、刷新就回去了，而用户会以为自己没点到——
`LocaleSettings` 文件头那句「NEVER 回滚成旧值假装成功」说的正是这种形状。

## 需要 owner / steward 的什么

**一句话，二选一**：

1. **「`SHELL-02` 的 outputs 加上 `migrations/` 与 `flint/`」**
   → worker 立刻做完整条：迁移 `0026` 加 `theme` 列（**接盘上当时最高的那一号，
   不留号**——理由见 `docs/trace/PERSIST-03.md` §2）、`Prefs` 加第三根轴、
   端点认它、右上角三态控件。
2. **「主题按设备存，不进 `prefs`」** → 那是一条**改口径**的裁决
   （与 `DEC-047` 现在的措辞不一致，也与 `SHELL-01` 那条禁掉浏览器存储的判据冲突），
   要落成一条新的 DEC 并说明为什么主题与语言/地区的存法不同。
   **worker 倾向不走这条**，但它有一个真实的产品理由值得 owner 掂量：
   主题是**显示偏好**，同一个人在夜里用手机、白天用台式机，
   想要的可能本来就不是同一个——而语言与地区不是这样。

## 顺带：本卡另外五条 acceptance 与 outputs 没有冲突

停的只有「存得住」这一条。三态控件、「跟随系统」是显式选项、
显式选择压过系统偏好、`DARK-02` 的 `theme-switches` 判据不倒、
首帧不闪白——**全部落在 `web/components/shell/` 之内**，
口径解开之后可以一次做完。

`SHELL-01` 已经把右上角那块地方建好了（`LocaleControls` + `.app-shell__spacer`），
三态控件排在它之后、共用同一个推到右边的机制即可
（`docs/trace/SHELL-01.md` §10 记着这件事）。

## 绕行现状

- **一行代码都没写**——判据文件也没建，免得盘上留下一个半红半绿的东西；
- `DARK-01` 建的暗色板与双通道（`prefers-color-scheme` 与 `data-theme`）**照旧生效**：
  今天用户仍然跟着系统偏好走，**只是切不了**；
- worker 转去做下一张依赖就绪的卡。

---

## 关闭（`SHELL-02` · `DEC-050`）

owner 2026-08-09 逐字答复：**「你按本批 rules 停下开单、一行代码都没写，那是对的行为。」**
并按第一条路裁决：**outputs 增加 `migrations/` 与 `flint/`**
（`profile/prefs.py` + `api/settings.py` 两处），主题作**第三根正交轴**存进 `prefs`。

**不按设备存**的理由也一并写进了 `DEC-050`：三态里的「跟随系统」已经覆盖
「夜里用手机、白天用台式机想要的不一样」——选它的人每台设备各跟各的系统走；
显式选了亮或暗的人，是在说「我到哪都要这个」。

落地：迁移 `0026`（`prefs.theme`，非空默认 `system`）· `Prefs` 第三个字段 + 越界校验 ·
`GET/PUT /settings/locale` 认第三根轴（`extra="forbid"` 照旧）· 右上角三态控件 ·
首帧同步脚本（实测刷新后第一帧就是暗色，**且那一刻 React 还没水合**）。
判据 23 条全绿，详见 `docs/trace/SHELL-02.md`。
