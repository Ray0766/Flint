# LOC-01 · 九区清单在前端还留着一份字面量副本

**卡** `docs/steward/tasks-v041-b3.json#LOC-01` · **cycles 1（oneshot）** ·
**self_review = true** → §5 · **owner_review = false** · **依赖** `WIRE-01` / `GAUGE-07`

## 1. 装载清单

卡面 LOC-01 · `web/components/region-switch/RegionSwitch.tsx` 全文 ·
`web/components/locale-settings/LocaleSettings.tsx` 全文 ·
`web/app/settings/locale/page.tsx` 全文 · `web/lib/ScreenFetchState.tsx`（五态渲染）·
`flint/api/settings.py` 的 `options()` / `locale_json` · `tools/check_locale_seam.py`
的白名单段 · `web/__tests__/app/ui07.test.tsx` 与 `tests/v041/test_ui07.py` 的清单判据。
约 12k tokens，预算 40k 以内。

## 2. 缺陷：同一份清单存在两处，而两处都写着自己是九区

```ts
// web/components/region-switch/RegionSwitch.tsx（改前）
export const REGIONS = ["CN", "US", "AU", "SG", "JP", "KR", "GB", "IT", "FR"] as const;
export type Region = (typeof REGIONS)[number];
```

真相在 `contracts_v04.Region`，`GET /settings/locale` 的 `options.region` 就是它，
`WIRE-01` 也早把那条路由挂上了——**页面一直在取 `/settings/locale`，
`options` 一直躺在响应里，只是没人往下传**。

两份清单迟早各说各的（加第十个地区那天只有一处会跟上），
而**读的人分不出哪份是真的**。

## 3. 联合类型也是副本

`export type Region = "CN" | "US" | …` 与那个数组一样是抄件，而且更硬：
加第十个地区那天，`tsc` 会**理直气壮地拦下新地区**——一个类型错误看起来永远像是对的。

所以这里退回 `string`：**可选值由后端把关**
（`PUT /settings/locale` 对不在 options 里的值回 422，`BE-07` 已实现）。
前端再拦一道，就是把同一条规则写第二遍——而第二遍那份不知道第十个地区。

## 4. 「九区完整、无 EU」那句断言没有消失，它搬去了源头

改前它写在组件测试里：`expect(options).toEqual([...REGIONS])` —— **判的是抄件**。
改后：

- **组件测试故意喂三项**（`["JP", "CN", "FR"]`，顺序不是字母序）：
  渲染出来必须正好是这三项。组件若还留着一份自带的九区，这条当场变红；
- **九区与无 EU 判在真栈上**（`tests/v041/test_regions_from_backend.py`）：
  `options.region == sorted(get_args(contracts_v04.Region))`，且 `len == 9`、无 EU。

**同一句话，从抄件搬到了正本上。**

## 5. verify、全局门与 self_review

```
verify_cmd: pytest tests/v041/test_regions_from_backend.py -q → 5 passed
全局门:     ruff check . --no-cache → All checks passed!
            mypy --strict flint     → Success: 299 source files
            pytest -q               → 3873 passed（FIX-03 收卡时 3868，本卡 +5）
            npx tsc --noEmit        → exit 0
            npm test -- --run       → 74 files / 752 passed
视觉取证:   ui_probe /settings/locale → 控制台 error 0，下拉正常（截图 url1-dark-*.png）
```

**① acceptance ↔ 测试映射**

| acceptance | 测试 |
|---|---|
| ① 前端 REGIONS 改从端点 options 取 | `test_the_page_hands_the_list_down_from_the_response`、`test_the_endpoint_serves_the_nine_from_the_frozen_contract`（**真栈**：装配后的应用上判 `options.region` 逐字等于冻结件） |
| ② 断言前端不再持有字面量副本 | `test_no_file_in_web_holds_half_the_region_list`（**全域扫描**，阈值「一半」：`"JP"` 当例子值不是副本，半份清单才是。改前实测 `RegionSwitch.tsx` 命中 9、其余最多 3）、`test_the_switch_no_longer_exports_a_region_constant`（连联合类型一起判） |
| ③ 端点不可用时显示未提供态，NEVER 悄悄退回硬编码副本 | `test_the_fallback_is_a_stated_state_not_a_hidden_copy`（页面有 `ScreenFetchState` 五态；组件里不许有 `?? REGIONS` 一类的回落形状；拿不到清单必须标 `data-screen-state="not_provided"`）+ 三条 vitest（`null` / 空数组 / 页面级） |

**② 改既有文件五处**：

| 文件 | 改前 → 改后 | 为什么非改不可 |
|---|---|---|
| `web/components/region-switch/RegionSwitch.tsx` | 删 `REGIONS` 与 `Region`；`regions` 改为入参；拿不到清单渲染未提供态 | **卡上 outputs（`web/`）**，本卡主体 |
| `web/components/locale-settings/LocaleSettings.tsx` | 删 `import { REGIONS }`；加 `regions` 入参；空清单渲染未提供态 | 同上。它是那份常量的另一个消费者，不改就还是抄件 |
| `web/app/settings/locale/page.tsx` | `ScreenFetchState` 的 render prop 改用 `(data)`，把 `data.options.region` 传下去 | 同上。清单要**从响应下发**，页面是唯一拿得到响应的地方 |
| `web/__tests__/app/ui07.test.tsx` | 不再 `import { REGIONS }`，改用三项的 `SERVED_REGIONS`；「十八种组合（2×9）」→「2 语言 × 端点给的每个地区」；「地区下拉就是既有 REGIONS」→「就是端点回的那一份」；新增「端点没给清单 → 未提供态」 | 同上。**那两条判的是抄件**：写死「9」的循环在加第十个地区那天不会跟着走 |
| `tests/v041/test_ui07.py` | `assert 'from "../region-switch/RegionSwitch"' in code`（要求 LocaleSettings **借用**那份常量）→ 改判「谁都不持有」：`regions` 是入参、且不许再借 | **这条判据钉的是旧设计**。那份常量退役后它必然红——不改它，本卡就无法收卡。同 `FIX-01` 处理 `test_cjk_numerals.py` 的先例：判据钉住的东西变了，判据跟着翻面并写清为什么 |

`contracts/` · `flint/domain/` · `requirements.lock` · `assets/heldout_questions.yaml`
一字未动；未新增依赖。

**③ 变异考 5 咬住 + 假变异对照绿**

| 变异 | 判据 |
|---|---|
| ① 退回缺陷态（组件里重新写死九区） | 红（2 条） |
| ② **藏一份回落副本**：`regions = regions ?? REGIONS` | 红（2 条） |
| ③ 空清单渲染空下拉（去掉未提供态） | 红 |
| ④ 页面不再从响应下发（改回自带一份） | 红 |
| ⑤ 联合类型副本回潮（`type Region = "CN" \| …`） | 红 |
| ⑥ 假变异对照：只改一句注释 | 全绿 |

② 是本卡最该有的那条：`?? REGIONS` 那一行**看起来很稳健**，
实际是把「端点挂了」显示成「一切正常」——用户照着一份可能过期的清单做选择，
而屏幕上没有任何迹象。

**④** 装载约 12k tokens；**⑤** 禁用词六词 0 命中。

## 6. 两条被别的尺子当场抓住（都是我改出来的）

1. **CRLF**：我用 python 写盘时 Windows 把 `\n` 翻成了 `\r\n`，三个 `web/` 文件行尾变了。
   `GAUGE-08` 的行尾尺子当场判红并说清了后果（「JS 剥刀 `//.*$` 在 `\r` 前走不下去，
   **整行注释一条都剥不掉**」）。改回 LF。
   **那把尺子是上一张卡建的，这一轮就抓到了第一条真鱼。**
2. **`tests/v041/test_ui07.py` 那条判据**：见 §5-②末行。

两条都不是「测试碍事」，是**判据在履职**。

## 7. 登记未做

1. **`/settings/locale` 在 390px 视口横向溢出 48px**（`scroll_width=438`）。
   已实测排除是本卡改出来的：把页面临时改回「前端自带九区」的形态再量，
   **同一个数**。已开单 `docs/blocked/LOCALE-FORM-OVERFLOWS-ON-MOBILE.md`——
   改样式在本卡 outputs 之外。
   顺带值得问：**其余十几屏在 390px 下有没有同样的事**？本单只报了一屏，因为只量了一屏。
2. **副本判据的阈值是启发式**：`HALF = 5`。有人把回落副本写成三项
   （`["CN","US","JP"]`）时扫不出来。当前用 `?? REGIONS` 一类的形状扫作补充，
   但那是字符串匹配。真正的护栏是「组件不接受任何默认值」——`regions` 是必填入参，
   不传就 `tsc` 红。
3. **`PUT /settings/locale` 的 422 没有在本卡验**：前端退掉自己那道校验之后，
   「非法地区被拦」这件事全靠后端。`BE-07` 有它自己的判据；本卡没有把两边接起来验一次。
4. **`tools/check_locale_seam.py` 只扫 `.py`**：前端这份副本它从来就看不见。
   本卡的扫描写在 pytest 里（扫 `.ts/.tsx`），两把尺子各扫一侧——
   要不要合成一把是另一张卡。
