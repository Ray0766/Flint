// 由 `tools/gen_section_tables.py` 从 `assets/templates/*.yaml` 生成。
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

export const TEMPLATE_IDS: readonly string[] = ["generic", "startup", "engineering", "grant", "thesis"];

export const SECTION_TABLES: Record<string, SectionRow[]> = {
  "generic": [
    {
      "id": "summary",
      "share": 10,
      "minWords": 300,
      "maxWords": 900
    },
    {
      "id": "opportunity",
      "share": 20,
      "minWords": 600,
      "maxWords": 1800
    },
    {
      "id": "market",
      "share": 20,
      "minWords": 600,
      "maxWords": 1800
    },
    {
      "id": "competition",
      "share": 15,
      "minWords": 450,
      "maxWords": 1350
    },
    {
      "id": "plan",
      "share": 20,
      "minWords": 600,
      "maxWords": 1800
    },
    {
      "id": "budget",
      "share": 10,
      "minWords": 300,
      "maxWords": 900
    },
    {
      "id": "risks",
      "share": 5,
      "minWords": 150,
      "maxWords": 450
    }
  ],
  "startup": [
    {
      "id": "one_liner",
      "share": 5,
      "minWords": 150,
      "maxWords": 450
    },
    {
      "id": "problem",
      "share": 15,
      "minWords": 450,
      "maxWords": 1350
    },
    {
      "id": "solution",
      "share": 20,
      "minWords": 600,
      "maxWords": 1800
    },
    {
      "id": "market_size",
      "share": 15,
      "minWords": 450,
      "maxWords": 1350
    },
    {
      "id": "go_to_market",
      "share": 15,
      "minWords": 450,
      "maxWords": 1350
    },
    {
      "id": "business_model",
      "share": 10,
      "minWords": 300,
      "maxWords": 900
    },
    {
      "id": "team",
      "share": 10,
      "minWords": 300,
      "maxWords": 900
    },
    {
      "id": "financials",
      "share": 10,
      "minWords": 300,
      "maxWords": 900
    }
  ],
  "engineering": [
    {
      "id": "goal",
      "share": 10,
      "minWords": 300,
      "maxWords": 900
    },
    {
      "id": "architecture",
      "share": 25,
      "minWords": 750,
      "maxWords": 2250
    },
    {
      "id": "milestones",
      "share": 25,
      "minWords": 750,
      "maxWords": 2250
    },
    {
      "id": "resources",
      "share": 15,
      "minWords": 450,
      "maxWords": 1350
    },
    {
      "id": "risks",
      "share": 15,
      "minWords": 450,
      "maxWords": 1350
    },
    {
      "id": "budget",
      "share": 10,
      "minWords": 300,
      "maxWords": 900
    }
  ],
  "grant": [
    {
      "id": "significance",
      "share": 15,
      "minWords": 450,
      "maxWords": 1350
    },
    {
      "id": "innovation",
      "share": 15,
      "minWords": 450,
      "maxWords": 1350
    },
    {
      "id": "approach",
      "share": 25,
      "minWords": 750,
      "maxWords": 2250
    },
    {
      "id": "feasibility",
      "share": 15,
      "minWords": 450,
      "maxWords": 1350
    },
    {
      "id": "team_resources",
      "share": 10,
      "minWords": 300,
      "maxWords": 900
    },
    {
      "id": "budget_justification",
      "share": 15,
      "minWords": 450,
      "maxWords": 1350
    },
    {
      "id": "timeline",
      "share": 5,
      "minWords": 150,
      "maxWords": 450
    }
  ],
  "thesis": [
    {
      "id": "abstract",
      "share": 8,
      "minWords": 240,
      "maxWords": 720
    },
    {
      "id": "related_work",
      "share": 22,
      "minWords": 660,
      "maxWords": 1980
    },
    {
      "id": "method",
      "share": 25,
      "minWords": 750,
      "maxWords": 2250
    },
    {
      "id": "evaluation_plan",
      "share": 20,
      "minWords": 600,
      "maxWords": 1800
    },
    {
      "id": "timeline",
      "share": 15,
      "minWords": 450,
      "maxWords": 1350
    },
    {
      "id": "resources",
      "share": 10,
      "minWords": 300,
      "maxWords": 900
    }
  ]
};
