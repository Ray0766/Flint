# FIX-03 · `tsc --noEmit` 的两条既有错：`?raw` 导入没有类型声明

**卡** `docs/steward/tasks-v041-b3.json#FIX-03` · **cycles 1（oneshot）** ·
**self_review = true** → §4 · **owner_review = false** · **依赖** 无

## 1. 装载清单

卡面 FIX-03 · `web/tsconfig.json` · `web/components/workbench-switch/WorkbenchSwitch.test.tsx`
的两处 `?raw` 段（第 149 / 161 行）· `tests/v041/test_verdict_constraints_type.py`
的 `_typecheck`（造误用跑真 tsc 的先例）· `docs/V041-BATCH2-COMPLETION.md` 的 tsc 段。
约 6k tokens，预算 40k 以内。

## 2. 两条错，一句声明

```
WorkbenchSwitch.test.tsx(149,33): error TS2307:
  Cannot find module './WorkbenchSwitch?raw' or its corresponding type declarations.
WorkbenchSwitch.test.tsx(161,33): 同上
```

`?raw` 是打包器的后缀语法（导入文件原文）。**运行时一直是好的**——
vitest 解析得好好的，那两条用例（「组件源码里没有 mode 键」「零 CJK 字面量」）一直绿。
缺的只是 TypeScript 这一侧的一份声明：`web/types/raw-imports.d.ts`。

## 3. 三种「让 tsc 闭嘴」的修法，两种被判据挡住

卡面 acceptance②：**NEVER 用 `any` 或 `ts-ignore` 压掉**。这两种加上第三种
（把 `?raw` 导入删掉）都能让 `tsc --noEmit` 归零，代价各不相同：

| 廉价修法 | 代价 | 挡它的判据 |
|---|---|---|
| `@ts-ignore` | 那一行的**全部**检查从此关掉 | `test_no_suppression_was_added_anywhere_in_web` |
| `const content: any` | 声明还在，但 `source.split("\n")` 之后一切失去检查——**错的用法与对的用法长得一模一样** | `test_the_declaration_is_a_string_not_an_escape_hatch`（**真造一次误用**：赋给 `number` 必须报 TS2322） |
| 删掉 `?raw` 导入 | 那两条 vitest 判据跟着一起没了 | `test_the_raw_import_is_still_used_for_what_it_was_for` |

**只判「tsc 归零」是不够的**：`any` 与 `string` 在归零这件事上没有区别。
所以判据要么去问编译器（造误用），要么去判修法本身。

## 4. verify、全局门与 self_review

```
verify_cmd: pytest tests/v041/test_tsc_clean.py -q → 6 passed
全局门:     ruff check . --no-cache → All checks passed!
            mypy --strict flint     → Success: 299 source files
            pytest -q               → 3868 passed（FIX-02 收卡时 3862，本卡 +6）
            npx tsc --noEmit        → **exit 0**（改前 2 条 TS2307）
            vitest workbench-switch → 16 passed（运行时行为未受影响）
```

**① acceptance ↔ 测试映射**

| acceptance | 测试 |
|---|---|
| ① tsc 归零 | `test_tsc_noemit_exits_zero`（判 exit code **与**逐行 `: error TS`）、`test_the_two_known_errors_are_the_ones_that_went_away`（**点名 TS2307 与 `?raw`**：只判总数为 0 的话，老错修掉、同时冒两条新错，数目照样是 0） |
| ② 补声明，NEVER any / ts-ignore | `test_the_fix_is_a_declaration_file`、`test_no_suppression_was_added_anywhere_in_web`、`test_the_declaration_is_a_string_not_an_escape_hatch`（**问编译器**，NEVER 只读源码判断） |
| ③ 把 exit 0 接成判据防再攒 | 这个文件本身：`tsc --noEmit` **不在**全局门那三条命令里，接进 `pytest` 之后它从此在门内——再有人写出类型错误，`pytest -q` 当场变红 |
| （自加） | `test_the_raw_import_is_still_used_for_what_it_was_for`（阴性对照，见 §3 第三行） |

**② 改既有文件 0 处**；新增两个文件（`web/types/raw-imports.d.ts` 在卡上 outputs
`web/` 之内，`tests/v041/test_tsc_clean.py` 是卡上 outputs）。
`contracts/` · `flint/domain/` · `requirements.lock` · `assets/heldout_questions.yaml`
一字未动；未新增依赖（`typescript` 本来就在 `web/package.json`）。

**③ 变异考 5 咬住 + 假变异对照绿**

| 变异 | 判据 |
|---|---|
| ① 退回缺陷态（删掉声明文件） | 红（4 条） |
| ② 声明写成 `any` | 红（2 条：造的误用通过了 + 声明扫描） |
| ③ 删声明 + 用 `@ts-ignore` 压掉（**tsc 照样 exit 0**） | 红（3 条） |
| ④ 把 `?raw` 导入删掉 | 红 |
| ⑤ 假变异对照：只改声明里的一句注释 | 全绿 |

③ 是本卡最该有的那条：它是**真会有人走的那条捷径**，且它让主判据（tsc 归零）继续绿。

**④** 装载约 6k tokens；**⑤** 禁用词六词 0 命中。

## 5. 一处判据我自己写宽了，当场改窄

第一版把 `@ts-expect-error` 与 `@ts-ignore` 一起禁了，实跑当场红：
`web/design/check-tristate/CheckStatus.test.tsx` 与 `web/design/direct-edit/directEdit.test.ts`
各有一处。

**这两者方向相反**：`@ts-ignore` 关掉检查；`@ts-expect-error` 断言「这里必须有一条错」，
**没有错反而会红**。混为一谈的话，本卡会去删掉两条真判据。
改成：`@ts-ignore` / `@ts-nocheck` 恒禁，`@ts-expect-error` **判等值**——
多一处要有人来这里说明为什么。

## 6. 登记未做

1. **`npx tsc --noEmit` 现在每跑一次 pytest 就跑一次**（约 4.5 秒 × 3 条判据）。
   合并成一条会快，但那样「归零」与「点名那两条」就共用一次输出，
   一条红时看不出是哪一类。本卡选了慢的那条路。
2. **`?url` / `?inline` 等其他打包器后缀没有声明**。现在没人用；
   一次把全部后缀声明上等于替一批还没写的代码提前放行。用到的那天各自声明。
3. **`npm test` 与 `tsc` 的全局门归属仍未定**（GAUGE-09 §6 的 owner 待定项）。
   本卡把 tsc 接进了 pytest，**但 55 条 vitest acceptance 仍在门外**——
   那是另一个决定，本卡没有替 owner 做。
