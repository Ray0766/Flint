"""M2-044 金标 20 例生成器：场景构造直出真值（owner 判例 M1-039 @2026-07-27）。

- 每例的 expected（verdict + all_satisfied）由场景规格**显式携带**——构造
  意图即真值，生成器不跑被评测引擎（规避「用被测系统标注金标」的循环）。
- 四档各 5 例、每档 >=2 大类（验收「>=4 例且 >=1 跨大类」的超集）；
  证据 docs / 对齐真值表 / 竞品 signal 三态 / 覆盖执行面全部内联 fixture 化，
  离线可复跑（S2-7）。
- 场景覆盖设计：A 档含 user_provided+optin 例与 C 各失败面；B 档双路径与
  strong/unknown 阻断；D 档含对齐 partial 的 demote 例（压过已满足 B）。
运行：python -m fixtures._generate_goldcases（写 assets/goldcases/goldcases.json）。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
OUT_PATH = REPO_ROOT / "assets" / "goldcases" / "goldcases.json"
FETCHED_AT = "2026-07-26T12:00:00+00:00"
PUBLISHED = "2026-05-01"

SIGNAL_PRESETS: dict[str, dict[str, bool | None]] = {
    "strong": {
        "funded_or_scaled": True, "mature_pricing": True,
        "same_target_user": None, "active_last_12m": None,
    },
    "moderate": {
        "funded_or_scaled": None, "mature_pricing": None,
        "same_target_user": None, "active_last_12m": True,
    },
    "weak": {
        "funded_or_scaled": False, "mature_pricing": False,
        "same_target_user": False, "active_last_12m": False,
    },
    "unknown": {
        "funded_or_scaled": None, "mature_pricing": None,
        "same_target_user": None, "active_last_12m": None,
    },
}

# (case_id, tier, category, keywords, refute 对齐结论列表, user_refute,
#  support 对齐结论列表, comps 强度意图列表, refute_executed, hit,
#  coverage 形态, expected all_satisfied)
SPECS: list[dict[str, Any]] = [
    # ── A 档（证伪硬门槛）─────────────────────────────
    {"case_id": "gold-A-01", "tier": "A_infeasible", "category": "cat-ai",
     "keywords": ["室温超导存储"], "refute": ["supports"], "user_refute": False,
     "support": ["supports"], "comps": [], "refute_executed": True, "hit": 0.8,
     "coverage": "empty_ok", "expected_all": ["A_infeasible", "C_opportunity"]},
    {"case_id": "gold-A-02", "tier": "A_infeasible", "category": "cat-energy",
     "keywords": ["家用微型核电"], "refute": ["supports"], "user_refute": False,
     "support": ["supports"], "comps": ["moderate", "moderate", "moderate"],
     "refute_executed": True, "hit": 0.4, "coverage": "saturated",
     "expected_all": ["A_infeasible", "B_red_ocean"]},
    {"case_id": "gold-A-03", "tier": "A_infeasible", "category": "cat-robotics",
     "keywords": ["全自主家政人形机器人"], "refute": ["supports", "supports"],
     "user_refute": False, "support": [], "comps": ["weak"],
     "refute_executed": True, "hit": 0.8, "coverage": "saturated",
     "expected_all": ["A_infeasible"]},
    {"case_id": "gold-A-04", "tier": "A_infeasible", "category": "cat-semiconductor",
     "keywords": ["1nm 家庭光刻机"], "refute": ["supports"], "user_refute": True,
     "support": [], "comps": [], "refute_executed": True, "hit": 0.7,
     "coverage": "empty_ok", "expected_all": ["A_infeasible"]},
    {"case_id": "gold-A-05", "tier": "A_infeasible", "category": "cat-ai",
     "keywords": ["脑机接口写作助手"], "refute": ["supports"], "user_refute": False,
     "support": ["supports"], "comps": ["moderate", "moderate"],
     "refute_executed": True, "hit": 0.8, "coverage": "not_saturated",
     "expected_all": ["A_infeasible"]},
    # ── B 档（数量或强度双路径）───────────────────────
    {"case_id": "gold-B-01", "tier": "B_red_ocean", "category": "cat-ai",
     "keywords": ["会议纪要摘要工具"], "refute": [], "user_refute": False,
     "support": ["supports"], "comps": ["moderate", "moderate", "moderate"],
     "refute_executed": True, "hit": 0.8, "coverage": "saturated",
     "expected_all": ["B_red_ocean", "C_opportunity"]},
    {"case_id": "gold-B-02", "tier": "B_red_ocean", "category": "cat-energy",
     "keywords": ["户用储能电池"], "refute": [], "user_refute": False,
     "support": ["supports"], "comps": ["strong"],
     "refute_executed": True, "hit": 0.8, "coverage": "saturated",
     "expected_all": ["B_red_ocean"]},
    {"case_id": "gold-B-03", "tier": "B_red_ocean", "category": "cat-robotics",
     "keywords": ["仓储搬运机器人"], "refute": [], "user_refute": False,
     "support": ["supports"],
     "comps": ["moderate", "moderate", "weak", "weak"],
     "refute_executed": True, "hit": 0.3, "coverage": "saturated",
     "expected_all": ["B_red_ocean"]},
    {"case_id": "gold-B-04", "tier": "B_red_ocean", "category": "cat-quantum",
     "keywords": ["量子随机数云服务"], "refute": [], "user_refute": False,
     "support": ["supports"],
     "comps": ["moderate", "moderate", "moderate", "unknown"],
     "refute_executed": True, "hit": 0.8, "coverage": "saturated",
     "expected_all": ["B_red_ocean"]},
    {"case_id": "gold-B-05", "tier": "B_red_ocean", "category": "cat-semiconductor",
     "keywords": ["国产 EDA 插件市场"], "refute": [], "user_refute": False,
     "support": ["supports"], "comps": ["strong", "moderate", "weak"],
     "refute_executed": True, "hit": 0.8, "coverage": "saturated",
     "expected_all": ["B_red_ocean"]},
    # ── C 档（四必要条件全成立）───────────────────────
    {"case_id": "gold-C-01", "tier": "C_opportunity", "category": "cat-ai",
     "keywords": ["方言语音标注平台"], "refute": [], "user_refute": False,
     "support": ["supports"], "comps": ["weak", "weak"],
     "refute_executed": True, "hit": 0.8, "coverage": "saturated",
     "expected_all": ["C_opportunity"]},
    {"case_id": "gold-C-02", "tier": "C_opportunity", "category": "cat-energy",
     "keywords": ["退役电池梯次检测"], "refute": [], "user_refute": False,
     "support": ["supports"], "comps": [], "refute_executed": True, "hit": 0.7,
     "coverage": "empty_ok", "expected_all": ["C_opportunity"]},
    {"case_id": "gold-C-03", "tier": "C_opportunity", "category": "cat-robotics",
     "keywords": ["果园采摘执行器"], "refute": [], "user_refute": False,
     "support": ["supports", "supports"], "comps": ["moderate"],
     "refute_executed": True, "hit": 0.9, "coverage": "saturated",
     "expected_all": ["C_opportunity"]},
    {"case_id": "gold-C-04", "tier": "C_opportunity", "category": "cat-quantum",
     "keywords": ["量子传感地质勘探"], "refute": [], "user_refute": False,
     "support": ["supports"], "comps": ["moderate", "moderate"],
     "refute_executed": True, "hit": 0.65, "coverage": "saturated",
     "expected_all": ["C_opportunity"]},
    {"case_id": "gold-C-05", "tier": "C_opportunity", "category": "cat-semiconductor",
     "keywords": ["车规芯片老化预测"], "refute": [], "user_refute": False,
     "support": ["supports"], "comps": ["weak", "weak"],
     "refute_executed": True, "hit": 0.8, "coverage": "saturated",
     "expected_all": ["C_opportunity"]},
    # ── D 档（兜底：缺口清单必出）─────────────────────
    {"case_id": "gold-D-01", "tier": "D_insufficient", "category": "cat-ai",
     "keywords": ["行业大模型咨询"], "refute": [], "user_refute": False,
     "support": ["partial"], "comps": ["moderate", "moderate", "moderate"],
     "refute_executed": True, "hit": 0.8, "coverage": "saturated",
     "expected_all": ["D_insufficient"]},  # 对齐 partial -> demote 压过已满足 B
    {"case_id": "gold-D-02", "tier": "D_insufficient", "category": "cat-energy",
     "keywords": ["社区虚拟电厂聚合"], "refute": [], "user_refute": False,
     "support": ["supports"], "comps": ["weak"], "refute_executed": False,
     "hit": 0.0, "coverage": "saturated", "expected_all": ["D_insufficient"]},
    {"case_id": "gold-D-03", "tier": "D_insufficient", "category": "cat-robotics",
     "keywords": ["深海巡检蛇形机器人"], "refute": [], "user_refute": False,
     "support": ["supports"], "comps": [], "refute_executed": True, "hit": 0.3,
     "coverage": "empty_low", "expected_all": ["D_insufficient"]},
    {"case_id": "gold-D-04", "tier": "D_insufficient", "category": "cat-quantum",
     "keywords": ["量子加密对讲终端"], "refute": [], "user_refute": False,
     "support": ["supports"], "comps": ["unknown", "weak"],
     "refute_executed": True, "hit": 0.8, "coverage": "saturated",
     "expected_all": ["D_insufficient"]},
    {"case_id": "gold-D-05", "tier": "D_insufficient", "category": "cat-semiconductor",
     "keywords": ["晶圆缺陷开源数据集"], "refute": [], "user_refute": False,
     "support": ["supports"], "comps": ["moderate", "moderate"],
     "refute_executed": True, "hit": 0.8, "coverage": "pending",
     "expected_all": ["D_insufficient"]},
]


def _doc(case_id: str, slug: str, index: int, kind: str,
         origin: str, access: str) -> dict[str, Any]:
    return {
        "doc_id": f"{case_id}-{slug}-{index}",
        "source_id": "goldcase" if origin == "retrieved" else "user_upload",
        "kind": kind,
        "title": f"{case_id} {slug} evidence {index}",
        "url": f"https://gold.example/{case_id}/{slug}{index}",
        "published_at": PUBLISHED,
        "meta": {"fetched_at": FETCHED_AT},
        "origin": origin,
        "access": access,
    }


def _coverage(kind: str, total: int) -> list[dict[str, Any]]:
    if kind == "saturated":
        return [
            {"query_text": "q1", "executed": True, "new": total},
            {"query_text": "q2", "executed": True, "new": 0},
        ]
    if kind == "not_saturated":
        return [{"query_text": "q1", "executed": True, "new": max(1, total)}]
    if kind == "pending":
        return [
            {"query_text": "q1", "executed": True, "new": total},
            {"query_text": "q2", "executed": False, "new": 0},
        ]
    # empty_ok / empty_low：确认空集与「空但相关率不达标」共用零结果执行面
    return [{"query_text": "q1", "executed": True, "new": 0}]


def build_case(spec: dict[str, Any]) -> dict[str, Any]:
    case_id = str(spec["case_id"])
    docs: list[dict[str, Any]] = []
    alignment_truth: dict[str, str] = {}

    refute_claims: list[dict[str, str]] = []
    for i, outcome in enumerate(spec["refute"], start=1):
        origin = "user_provided" if spec["user_refute"] else "retrieved"
        access = "private" if spec["user_refute"] else "public"
        doc = _doc(case_id, "ref", i, "paper", origin, access)
        docs.append(doc)
        claim = f"[{case_id}] 该方向存在公开证伪证据 #{i}"
        refute_claims.append({"claim": claim, "doc_id": doc["doc_id"]})
        alignment_truth[f"{claim}|{doc['doc_id']}"] = outcome

    support_claims: list[dict[str, str]] = []
    for i, outcome in enumerate(spec["support"], start=1):
        doc = _doc(case_id, "sup", i, "paper", "retrieved", "public")
        docs.append(doc)
        claim = f"[{case_id}] 该方向存在市场支持证据 #{i}"
        support_claims.append({"claim": claim, "doc_id": doc["doc_id"]})
        alignment_truth[f"{claim}|{doc['doc_id']}"] = outcome

    competitors: list[dict[str, Any]] = []
    for i, preset in enumerate(spec["comps"], start=1):
        doc = _doc(case_id, "comp", i, "product", "retrieved", "public")
        docs.append(doc)
        competitors.append(
            {
                "name": f"Vendor {case_id}-{i}",
                "url": doc["url"],
                "source_doc_ids": [doc["doc_id"]],
                "signals": dict(SIGNAL_PRESETS[str(preset)]),
                "intended_strength": preset,
            }
        )

    expected_all = list(spec["expected_all"])
    return {
        "case_id": case_id,
        "tier": spec["tier"],
        "category": spec["category"],
        "keywords": list(spec["keywords"]),
        "locale": "zh-CN",
        "docs": docs,
        "refute_claims": refute_claims,
        "support_claims": support_claims,
        "alignment_truth": alignment_truth,
        "competitors": competitors,
        "user_evidence_optin": bool(spec["user_refute"]),
        "refute_executed": bool(spec["refute_executed"]),
        "refute_hit_rate": float(spec["hit"]),
        "coverage_executions": _coverage(str(spec["coverage"]), len(spec["comps"])),
        "expected": {
            "verdict": expected_all[0],
            "all_satisfied": expected_all,
        },
    }


def build() -> dict[str, Any]:
    return {
        "version": 1,
        "generated_by": "fixtures/_generate_goldcases.py",
        "cases": [build_case(spec) for spec in SPECS],
    }


def main() -> None:
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(
        json.dumps(build(), ensure_ascii=False, sort_keys=True, indent=1) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {OUT_PATH}")


if __name__ == "__main__":
    main()
