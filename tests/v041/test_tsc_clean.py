"""FIX-03 · `npx tsc --noEmit` 的两条既有错：`?raw` 导入没有类型声明。

## 缺陷

```
components/workbench-switch/WorkbenchSwitch.test.tsx(149,33):
  error TS2307: Cannot find module './WorkbenchSwitch?raw' or its corresponding type declarations.
components/workbench-switch/WorkbenchSwitch.test.tsx(161,33): 同上
```

`?raw` 是打包器的后缀语法（导入文件原文），运行时由 vitest 解析得好好的——
**那两条 vitest 用例一直是绿的**。缺的只是 TypeScript 侧的一份声明。

## 为什么不能用 `any` 或 `ts-ignore` 压掉（卡面 acceptance②）

两种压法都能让 `tsc` 闭嘴，代价不同、但方向一样：

- `@ts-ignore` 把**那一行**的全部检查关掉——不止关掉这条错，
  以后那一行写错什么都不会有人说话；
- `any` 更隐蔽：声明还在，但 `source.split("\\n")` 之后拿到的东西是 `any`，
  **错的用法与对的用法从此长得一模一样**。

所以判据不只判「tsc 归零」，还**真造一次误用**去看编译器拦不拦
（`test_the_declaration_is_a_string_not_an_escape_hatch`）：
把 `?raw` 的结果赋给 `number` 必须报错。声明写成 `any` 的那天，这条会红。

## acceptance③：把 exit 0 接成判据，防止再攒

`npx tsc --noEmit` 不在全局门那三条命令里（`ruff` / `mypy` / `pytest -q`）。
这个文件把它接进 `pytest`——**于是它从此在门内**。
"""
from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
WEB = REPO / "web"
DECL = WEB / "types" / "raw-imports.d.ts"
SUBJECT = WEB / "components" / "workbench-switch" / "WorkbenchSwitch.test.tsx"
# `@ts-ignore` / `@ts-nocheck` **关掉**检查；`@ts-expect-error` 相反——
# 它断言「这里必须有一条错」，没有错反而会红。两者 NEVER 混为一谈。
FORBIDDEN = ("@ts-ignore", "@ts-nocheck")
# 现有的两处负向断言（改前实测就这两处）。多一处要有人来这里说明为什么。
EXPECTED_ERROR_FILES = {
    "design/check-tristate/CheckStatus.test.tsx",
    "design/direct-edit/directEdit.test.ts",
}


def _npx() -> str:
    npx = shutil.which("npx")
    assert npx is not None, "找不到 npx：这条门量不了，NEVER 当它通过"
    return npx


def _tsc(*extra: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [_npx(), "tsc", "--noEmit", *extra],
        cwd=WEB, capture_output=True, text=True, encoding="utf-8",
        errors="replace", check=False)


# ───────────────────────── acceptance①③：归零，并把 exit 0 接成判据


def test_tsc_noemit_exits_zero() -> None:
    """`npx tsc --noEmit` **exit 0**，一条错都没有。

    改前实测两条 `TS2307`。这条判据同时是 acceptance③ 的防攒闸：
    再有人写出类型错误，`pytest -q` 当场变红——不必等谁想起来单独跑 tsc。
    """
    done = _tsc()
    errors = [ln for ln in done.stdout.splitlines() if ": error TS" in ln]

    assert errors == [], "tsc 有错：\n" + "\n".join(errors)
    assert done.returncode == 0, done.stdout + done.stderr


def test_the_two_known_errors_are_the_ones_that_went_away() -> None:
    """**点名**改前那两条：它们来自 `?raw` 导入，且都在同一个文件里。

    只判「总数为 0」的话，两条老错被修掉、同时冒出两条新错，数目照样是 0。
    """
    done = _tsc()

    assert "TS2307" not in done.stdout, "还有模块解析不了的导入"
    assert "?raw" not in done.stdout, f"`?raw` 还在报错：{done.stdout[:300]}"


# ───────────────────────── acceptance②：补声明，NEVER 压掉


def test_the_fix_is_a_declaration_file() -> None:
    """修法是**一份类型声明**，不是把检查关掉。"""
    assert DECL.exists(), f"没有 {DECL.relative_to(REPO)}"
    text = DECL.read_text(encoding="utf-8")

    assert 'declare module "*?raw"' in text
    assert re.search(r":\s*string", text), "声明里没有 string——那它声明了什么？"
    assert ": any" not in text and "<any>" not in text


def test_no_suppression_was_added_anywhere_in_web() -> None:
    """`web/` 全域**零 `@ts-ignore` / `@ts-nocheck`**；负向断言逐个点名。

    钉住它，是因为「让 tsc 闭嘴」永远比「修好」省事，
    而被关掉的那一行从此不在任何类型判据下——**下次那里写错什么都没人说话**。

    `@ts-expect-error` 是另一回事：它断言「这里必须有一条错」，没有错反而红。
    所以不禁，但**判等值**——多一处要有人来这里说明为什么。
    """
    silenced: list[str] = []
    expecting: set[str] = set()
    for path in sorted(WEB.rglob("*.ts*")):
        if "node_modules" in path.parts or ".next" in path.parts:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        rel = path.relative_to(WEB).as_posix()
        silenced += [f"{rel} → {m}" for m in FORBIDDEN if m in text]
        if "@ts-expect-error" in text:
            expecting.add(rel)

    assert silenced == [], f"web/ 里出现了类型抑制：{silenced}"
    assert expecting == EXPECTED_ERROR_FILES, (
        f"负向断言的分布变了：多出 {sorted(expecting - EXPECTED_ERROR_FILES)}、"
        f"少了 {sorted(EXPECTED_ERROR_FILES - expecting)}"
    )


def test_the_declaration_is_a_string_not_an_escape_hatch(tmp_path: Path) -> None:
    """**真造一次误用**：`?raw` 的结果赋给 `number` 必须被编译器拦下。

    声明写成 `any` 的话 `tsc` 会照样闭嘴、这条会绿——
    所以只判「tsc 归零」是不够的：`any` 与 `string` 在归零这件事上没有区别。

    NEVER 只读源码判断：能不能写出那种误用，只有编译器说了算。
    """
    probe = WEB / "_fix03_probe.ts"
    probe.write_text(
        'import source from "./components/workbench-switch/WorkbenchSwitch?raw";\n'
        "export const wrong: number = source;\n",
        encoding="utf-8")
    try:
        done = subprocess.run(
            [_npx(), "tsc", "--noEmit", "--strict", "--skipLibCheck",
             "--target", "ES2022", "--moduleResolution", "bundler",
             "--module", "esnext", "--types", "node",
             str(probe), str(DECL)],
            cwd=WEB, capture_output=True, text=True, encoding="utf-8",
            errors="replace", check=False)
    finally:
        probe.unlink(missing_ok=True)

    assert done.returncode != 0, (
        "把一份原文赋给 number 竟然通过了——声明大概是 any"
    )
    assert "TS2322" in done.stdout, f"拦下了，但不是类型不符：{done.stdout[:300]}"


def test_the_raw_import_is_still_used_for_what_it_was_for() -> None:
    """**阴性对照**：那两条 vitest 用例还在用 `?raw` 读源码。

    把 `?raw` 导入删掉也能让 tsc 归零——代价是
    「组件源码里没有 mode 键 / 零 CJK 字面量」这两条判据一起没了。
    """
    text = SUBJECT.read_text(encoding="utf-8")

    assert text.count("?raw") == 2, "那两处 `?raw` 导入不在了"
    assert "没有 mode 键" in text and "零 CJK 字面量" in text
