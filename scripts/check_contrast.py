"""对比度门：把「日间/夜间两套 token 的每对前景/背景都达标」变成机器可验的断言。

为什么需要它
------------
颜色是唯一一类「看起来对、量起来错」的缺陷：暗色下清楚的灰，翻到浅底上就糊了。
本脚本直接读 `V0 files 前端设计/app/globals.css` 的两个主题作用域，取真实 token 值，
按 WCAG 2.1 相对亮度公式实算每一对**实际会同屏出现**的前景/背景组合。

判据（WCAG 2.1 AA）
    正文级（body）  >= 4.5
    大字级（large） >= 3.0    18.66px bold 或 24px 以上
不达标即打印明细并 **exit 非零**（CI 可直接挂门）。

它锁死的三条硬约束
------------------
1. --spark **必须双值**：单一取值不可能同时在纸底与暗底达标
   （#FF6B4A 在纸底 2.41 FAIL；#B4472C 在暗底 3.21 FAIL）。
2. --ink-3 是元信息色，本项目按**正文级**要求（11px 元信息仍要读得清），
   故 Claude _ds 的 #8B9799（纸底 2.57）NEVER 直接照抄。
3. --sulfur 只能作**背景**（黄底 + 深字），NEVER 作文字色（纸底 1.57）。
   故它不出现在任何「前景」位，只作为背景参与校验。

跑法（项目 .venv 即可，无第三方依赖）
    .venv/Scripts/python.exe scripts/check_contrast.py
    .venv/Scripts/python.exe scripts/check_contrast.py --verbose
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
CSS = REPO / "V0 files 前端设计" / "app" / "globals.css"

BODY_MIN = 4.5
LARGE_MIN = 3.0

# 实际会同屏出现的组合。level: "body" 正文级 / "large" 仅大字或非文本。
# 背景三阶：--base 页底 / --surface 卡面 / --raised 抬升层。
PAIRS: list[tuple[str, str, str, str]] = [
    # 文字三阶 × 三种底
    ("--ink", "--base", "body", "标题/主值压页底"),
    ("--ink", "--surface", "body", "标题/主值压卡面"),
    ("--ink", "--raised", "body", "标题/主值压抬升层"),
    ("--ink-2", "--base", "body", "正文压页底"),
    ("--ink-2", "--surface", "body", "正文压卡面"),
    ("--ink-2", "--raised", "body", "正文压抬升层"),
    ("--ink-3", "--base", "body", "元信息压页底（本项目按正文级要求）"),
    ("--ink-3", "--surface", "body", "元信息压卡面"),
    ("--ink-3", "--raised", "body", "元信息压抬升层"),
    # 告警色：只在这几种底上出现（NEVER 压在 raised 上，故不列）
    ("--spark", "--base", "body", "告警字压页底"),
    ("--spark", "--surface", "body", "告警字压卡面"),
    ("--spark", "--spark-wash", "body", "告警字压告警底纹"),
    # 结构色 / 链接
    ("--indigo", "--base", "body", "链接压页底"),
    ("--indigo", "--surface", "body", "链接压卡面"),
    # CTA：黄底深字（日间） / 反白按钮（夜间）
    ("--cta-fg", "--cta-bg", "body", "CTA 按钮字压其底"),
    ("--on-accent", "--sulfur", "body", "硫磺底上的深字"),
    ("--primary-foreground", "--primary", "body", "主按钮字压主按钮底"),
    # 源印记：2px 方块，非文本 → 大字级判据即可
    ("--src-trends", "--surface", "large", "源印记 gtrends"),
    ("--src-weibo", "--surface", "large", "源印记 weibo"),
    ("--src-github", "--surface", "large", "源印记 ghtrend"),
    ("--src-arxiv", "--surface", "large", "源印记 arxiv"),
    # 细线：非文本，仅需可辨
    ("--rail", "--surface", "large", "实线轨压卡面"),
]

# 这些 token NEVER 允许出现在「前景（文字）」位。
NEVER_AS_TEXT = {"--sulfur": "硫磺在纸底仅 1.57，只能作背景（黄底+深字）"}

# ── 圈地纪律（owner 裁决 ③）────────────────────────────────────────────
# --sulfur / --cta-bg（黄底 CTA）**只属营销屏**：首页与 /how-it-works。
# 数据屏（广场 / 工作台 / combo / Gate / 报告 …）用它，会稀释告警色在要紧处的唯一性
# ——与 glow 同样圈地。这里做成机器可验，而不是只写在注释里。
FE = REPO / "V0 files 前端设计"
SULFUR_ALLOWED = {
    "app/page.tsx",            # 营销首屏
    "app/how-it-works/page.tsx",  # 营销说明页
    "app/globals.css",         # token 定义处
    "app/styleguide/page.tsx",  # 设计词汇表（展示 token 本身）
}
SULFUR_TOKENS = ("--sulfur", "sulfur-underline", "bg-cta-bg", "text-cta-fg", "--cta-bg")


def scan_sulfur_confinement() -> list[str]:
    """扫描前端源码：数据屏若引用硫磺/CTA 黄底 token 即失败。"""
    bad: list[str] = []
    for p in sorted(FE.rglob("*.tsx")) + sorted(FE.rglob("*.css")):
        rel = p.relative_to(FE).as_posix()
        if rel.startswith(("node_modules/", ".next/", "components/ui/")):
            continue
        if rel in SULFUR_ALLOWED:
            continue
        for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            # 只看真正的使用，不看写着 NEVER 的纪律注释
            if "NEVER" in line:
                continue
            for tok in SULFUR_TOKENS:
                if tok in line:
                    bad.append(f"{rel}:{i} 数据屏引用了 {tok}（硫磺/CTA 黄底只属营销屏）")
    return bad


def _lin(c: float) -> float:
    c /= 255.0
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _luminance(rgb: tuple[float, float, float]) -> float:
    r, g, b = rgb
    return 0.2126 * _lin(r) + 0.7152 * _lin(g) + 0.0722 * _lin(b)


def parse_color(v: str) -> tuple[float, float, float, float] | None:
    """#rgb / #rrggbb / rgba(r,g,b,a) → (r, g, b, alpha)；其余返回 None。"""
    v = v.strip()
    m = re.fullmatch(r"#([0-9a-fA-F]{3})", v)
    if m:
        h = m.group(1)
        return (*(int(c * 2, 16) for c in h), 1.0)  # type: ignore[return-value]
    m = re.fullmatch(r"#([0-9a-fA-F]{6})", v)
    if m:
        h = m.group(1)
        return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), 1.0)
    m = re.fullmatch(r"rgba?\(([^)]+)\)", v)
    if m:
        parts = [p.strip() for p in m.group(1).replace("/", ",").split(",")]
        if len(parts) >= 3:
            r, g, b = (float(x) for x in parts[:3])
            a = float(parts[3]) if len(parts) > 3 else 1.0
            return (r, g, b, a)
    return None


def composite(fg: tuple[float, float, float, float],
              bg: tuple[float, float, float, float]) -> tuple[float, float, float, float]:
    """半透明前景压到不透明底上，得到实际观察到的颜色。"""
    a = fg[3]
    return (fg[0] * a + bg[0] * (1 - a),
            fg[1] * a + bg[1] * (1 - a),
            fg[2] * a + bg[2] * (1 - a), 1.0)


def ratio(fg: tuple[float, float, float, float],
          bg: tuple[float, float, float, float]) -> float:
    f = _luminance(fg[:3])
    b = _luminance(bg[:3])
    hi, lo = max(f, b), min(f, b)
    return (hi + 0.05) / (lo + 0.05)


def extract_scope(css: str, selector: str) -> dict[str, str]:
    """取出某个选择器块里的自定义属性声明（只认第一层 --x: y;）。

    两个坑（本脚本都真踩过，故写死在这里）：
    1. 只在**行首**匹配选择器，否则 `@custom-variant dark (&:where(.dark, .dark *));`
       里的 `.dark` 会先命中；
    2. **先剥注释**再匹配，否则文件头注释里写的 `:root = 日间` / `.dark = 夜间`
       会被当成选择器命中，把紧随的块误认作该作用域 —— 表现为「两套主题取值相同」的假象。
    """
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.DOTALL)
    pat = re.compile(r"^[ \t]*" + re.escape(selector), re.MULTILINE)
    m0 = pat.search(css)
    while m0 is not None:
        idx = m0.start()
        brace = css.find("{", idx)
        if brace == -1:
            break
        depth, i = 1, brace + 1
        while i < len(css) and depth:
            if css[i] == "{":
                depth += 1
            elif css[i] == "}":
                depth -= 1
            i += 1
        body = css[brace + 1:i - 1]
        decls = dict(re.findall(r"(--[\w-]+)\s*:\s*([^;]+);", body))
        if decls:
            return decls
        m0 = pat.search(css, i)
    return {}


def resolve(name: str, *scopes: dict[str, str]) -> str | None:
    """解析 token，跟随 var(--x) 链（最多 10 跳）。后面的 scope 优先级低。"""
    seen = 0
    cur = name
    while seen < 10:
        val = None
        for sc in scopes:
            if cur in sc:
                val = sc[cur]
                break
        if val is None:
            return None
        val = val.strip()
        m = re.fullmatch(r"var\(\s*(--[\w-]+)\s*\)", val)
        if m:
            cur = m.group(1)
            seen += 1
            continue
        return val
    return None


def check_theme(label: str, scopes: list[dict[str, str]], verbose: bool) -> list[str]:
    fails: list[str] = []
    for fg_name, bg_name, level, why in PAIRS:
        if fg_name in NEVER_AS_TEXT:
            fails.append(f"[{label}] {fg_name} 被用作前景色：{NEVER_AS_TEXT[fg_name]}")
            continue
        fg_raw = resolve(fg_name, *scopes)
        bg_raw = resolve(bg_name, *scopes)
        if fg_raw is None or bg_raw is None:
            fails.append(f"[{label}] token 未定义：{fg_name}={fg_raw} / {bg_name}={bg_raw}")
            continue
        fg = parse_color(fg_raw)
        bg = parse_color(bg_raw)
        if fg is None or bg is None:
            fails.append(f"[{label}] 颜色无法解析：{fg_name}={fg_raw} / {bg_name}={bg_raw}")
            continue
        if bg[3] < 1.0:
            base = parse_color(resolve("--base", *scopes) or "#ffffff")
            bg = composite(bg, base or (255, 255, 255, 1.0))
        if fg[3] < 1.0:
            fg = composite(fg, bg)
        r = ratio(fg, bg)
        need = BODY_MIN if level == "body" else LARGE_MIN
        ok = r >= need
        if verbose or not ok:
            mark = "OK  " if ok else "FAIL"
            print(f"  {mark} [{label}] {fg_name} on {bg_name} = {r:.2f} "
                  f"(需 >= {need}) — {why}")
        if not ok:
            fails.append(f"[{label}] {fg_name} on {bg_name} = {r:.2f} < {need}（{why}）")
    return fails


def main() -> None:
    ap = argparse.ArgumentParser(description="双主题对比度门（WCAG 2.1 AA）")
    ap.add_argument("--verbose", action="store_true", help="打印全部组合，不只失败项")
    a = ap.parse_args()

    if not CSS.exists():
        print(f"找不到 token 文件：{CSS}", file=sys.stderr)
        raise SystemExit(2)
    css = CSS.read_text(encoding="utf-8")

    light = extract_scope(css, ":root")
    dark = extract_scope(css, ".dark")
    shared = extract_scope(css, ":root,\n.dark")
    if not shared:
        shared = extract_scope(css, ":root,")

    if not light or not dark:
        print("未找到两套主题作用域（:root 与 .dark）——主题可能没建起来。", file=sys.stderr)
        raise SystemExit(2)

    same = [k for k in ("--base", "--surface", "--ink", "--ink-2", "--spark")
            if k in light and k in dark and light[k].strip() == dark[k].strip()]
    fails: list[str] = []
    if same:
        fails.append(f"日夜同值（主题没真正翻转）：{', '.join(same)}")

    print("== 日间 :root ==")
    fails += check_theme("light", [light, shared], a.verbose)
    print("== 夜间 .dark ==")
    fails += check_theme("dark", [dark, shared, light], a.verbose)

    print("== 硫磺圈地（裁决 ③：只属营销屏）==")
    confinement = scan_sulfur_confinement()
    if a.verbose and not confinement:
        print("  OK   数据屏未引用 --sulfur / --cta-bg")
    fails += confinement

    print()
    if fails:
        print(f"对比度门未通过，共 {len(fails)} 项：")
        for f in fails:
            print(f"  - {f}")
        raise SystemExit(1)
    print(f"对比度门通过：两套主题 × {len(PAIRS)} 对组合全部达标"
          f"（正文 >= {BODY_MIN} / 大字 >= {LARGE_MIN}）。")


if __name__ == "__main__":
    main()
