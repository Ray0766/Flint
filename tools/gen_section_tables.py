"""WB-05：把 `assets/templates/*.yaml` 的章节表**生成**成前端可用的一份。

    python tools/gen_section_tables.py            # 生成
    python tools/gen_section_tables.py --check    # 只校验：盘上那份是不是最新的（退 1 = 过期）

## 为什么是生成，不是手抄一份

工单原话：「章节表 MUST 与 `assets/templates/*.yaml` 对齐 …… NEVER 在前端
另建一份章节清单（一处定义他处引用）」。而前端**今天没有运行时的路**去读那五个
yaml：全仓没有任何端点回报告模板（`/design/templates` 是设计台那一族，不是这个）。

两难之下的第三条路：**yaml 仍是唯一真相，前端那份由它派生**，
派生这一步落成一个文件并由判据钉住（`--check` 在测试里跑）。
手抄一份的话，两处会在某次改模板之后分叉，而屏上看不出来——
分叉的症状是「章节导航里有一章，正文里永远没有它」。

## 生成两处，各有各的理由

- `web/lib/sectionTables.generated.ts`：**只有数**（id / 占比 / 字数区间）。
  一个中文字都不放——`tools/i18n_scan.mjs` 扫全 `web/` 的 CJK 字面量，
  而它扫得对：屏上出现的每一句话都该在词典里，生成物也不例外。
- `web/messages/{zh,en}.json` 的 `wb.check.<模板>.<章节>`：逐章那句**检查问句**。

检查问句今天**只有中文**（那五个 yaml 自己写着 `locale: zh-CN`），
所以 en 那份填的是同一句中文——**如实**：这是「模板还没有英文版」，
不是「翻译漏了」。哪天模板出了英文版，改的是那一份 yaml 与这里的生成规则。

章节的中文名/英文名同理走词典（`wb.section.<模板>.<章节>`），
但它们出自蓝本而不是 yaml，所以由人写进词典、判据逐字比对蓝本。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]
TEMPLATES = REPO / "assets" / "templates"
OUT = REPO / "web" / "lib" / "sectionTables.generated.ts"
MESSAGES = (REPO / "web" / "messages" / "zh.json", REPO / "web" / "messages" / "en.json")

#: 蓝本那个模板下拉里的五套（`前端设计/ai工作台/Flint 设计台 v3.dc.html`）。
#: `vibe_pack` **不在其中**：它是受众分叉里给 AI 执行器的那一份（`S1`），
#: 不是人读的计划书模板——摆进这个下拉等于让用户选一份他不会读的东西。
HUMAN_TEMPLATES = ("generic", "startup", "engineering", "grant", "thesis")

HEADER = """// 由 `tools/gen_section_tables.py` 从 `assets/templates/*.yaml` 生成。
// **NEVER 手改**：改了会被 `tests/v041/test_wb_sections.py` 当场判红。
// 要改章节表 → 改那五个 yaml（后端的模板真相）→ 重跑生成器。
//
// 章节的显示名不在这里：它是界面文案，走 `messages/{zh,en}.json` 的
// `wb.section.<id>`——写在这里的话，两份词典的对称判据管不到它。

export type SectionRow = {
  /** 章节 id（= yaml 的 `section_id`，也是 Block.section_id）。 */
  id: string;
  /** 占比（yaml 的 `ratio.share`，这里换算成整数百分比）。 */
  share: number;
  minWords: number;
  maxWords: number;
};

// 逐章那句检查问句在词典里：`wb.check.<模板>.<章节>`（同由本生成器写入）。
// 放在这里的话，`tools/i18n_scan.mjs` 会当场判红——它扫得对。

"""


def build() -> tuple[str, dict[str, str]]:
    tables: dict[str, list[dict[str, object]]] = {}
    checks: dict[str, str] = {}
    for template_id in HUMAN_TEMPLATES:
        payload = yaml.safe_load(
            (TEMPLATES / f"{template_id}.yaml").read_text(encoding="utf-8"))
        rows: list[dict[str, object]] = []
        for section in payload["sections"]:
            ratio = section["ratio"]
            questions = section["check_questions"]
            if not questions:
                raise SystemExit(
                    f"{template_id}/{section['section_id']} 没有检查问句——"
                    f"逐章检查项那一列会空着，而空着与「查过了没问题」在屏上长得一样")
            rows.append({
                "id": str(section["section_id"]),
                # `share` 在 yaml 里是 0~1 的小数；界面上说的是百分比。
                # **换算只此一处**：两处各算一次，某一天会差一个四舍五入。
                "share": round(float(ratio["share"]) * 100),
                "minWords": int(ratio["min_words"]),
                "maxWords": int(ratio["max_words"]),
            })
            checks[f"wb.check.{template_id}.{section['section_id']}"] = str(questions[0])
        tables[template_id] = rows
    body = json.dumps(tables, ensure_ascii=False, indent=2)
    ids = json.dumps(list(HUMAN_TEMPLATES), ensure_ascii=False)
    text = (
        f"{HEADER}export const TEMPLATE_IDS: readonly string[] = {ids};\n\n"
        f"export const SECTION_TABLES: Record<string, SectionRow[]> = {body};\n"
    )
    return text, checks


def _messages(path: Path) -> dict[str, str]:
    return dict(json.loads(path.read_text(encoding="utf-8")))


def _write_messages(path: Path, checks: dict[str, str]) -> None:
    data = _messages(path)
    data.update(checks)
    path.write_text(
        json.dumps(dict(sorted(data.items())), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8", newline="\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    wanted, checks = build()
    if args.check:
        current = OUT.read_text(encoding="utf-8") if OUT.exists() else ""
        if current != wanted:
            print(f"{OUT.relative_to(REPO)} 与 assets/templates/*.yaml 对不上——重跑生成器")
            return 1
        # 词典里那几条**也归这里管**：只核前端那份表的话，
        # 改了 yaml 里的检查问句而没重跑生成器时，判据照样绿，
        # 而屏上逐章那一列还写着旧口径。
        for path in MESSAGES:
            have = _messages(path)
            stale = {k: v for k, v in checks.items() if have.get(k) != v}
            if stale:
                print(f"{path.name} 里的检查问句与 yaml 对不上：{sorted(stale)[:3]}")
                return 1
        print("章节表与检查问句都与模板 yaml 一致。")
        return 0
    OUT.write_text(wanted, encoding="utf-8", newline="\n")
    for path in MESSAGES:
        _write_messages(path, checks)
    print(f"写出 {OUT.relative_to(REPO)} + 两份词典的 {len(checks)} 条检查问句")
    return 0


if __name__ == "__main__":
    sys.exit(main())
