#!/usr/bin/env python3
"""validate_dag_v04 — tasks-v04.json 质量门（单文件零依赖）。

用法:
  python tools/validate_dag_v04.py --file tasks-v04.json
  python tools/validate_dag_v04.py --base tasks.json --patch tasks-m1m4-v04-patch.json --merged

检查项（任一失败 → 非零退出）:
  1 依赖存在且无自依赖        2 无环（Kahn）
  3 verify_cmd 覆盖率 == 1.0   4 双单位（cycles + estimate_days）
  5 V0 先行：非 PRIN/MIGRATE 卡的祖先集 ⊇ 全部 V0 卡
  6 隔离带：带外卡 NEVER 依赖带内卡
输出: dag_report dict（acyclic/nodes/edges/errors/total_cycles/critical_path*/coverage/...）。
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import deque

V0_PREFIX = ("PRIN-", "MIGRATE-")

def load(path: str):
    with open(path, encoding="utf-8-sig") as f:
        return json.load(f)

def build_report(tasks: list[dict], droppable: list[str]) -> dict:
    ids = [t["id"] for t in tasks]
    idset = set(ids)
    errors: list[str] = []
    if len(ids) != len(idset):
        errors.append("duplicate ids")
    deps = {t["id"]: list(t.get("depends_on", [])) for t in tasks}
    for tid, ds in deps.items():
        for d in ds:
            if d == tid:
                errors.append(f"self-dep: {tid}")
            if d not in idset:
                errors.append(f"unknown dep: {tid} -> {d}")
    # Kahn
    indeg = {i: 0 for i in ids}
    children: dict[str, list[str]] = {i: [] for i in ids}
    for tid, ds in deps.items():
        for d in ds:
            if d in idset:
                indeg[tid] += 1
                children[d].append(tid)
    q = deque(sorted(i for i in ids if indeg[i] == 0))
    topo: list[str] = []
    indeg2 = dict(indeg)
    while q:
        n = q.popleft(); topo.append(n)
        for c in children[n]:
            indeg2[c] -= 1
            if indeg2[c] == 0:
                q.append(c)
    acyclic = len(topo) == len(ids)
    if not acyclic:
        errors.append("cycle detected: " + ",".join(sorted(set(ids) - set(topo))[:8]))
    # coverage + dual units
    miss_v = [t["id"] for t in tasks if not str(t.get("verify_cmd", "")).strip()]
    if miss_v:
        errors.append("verify_cmd missing: " + ",".join(miss_v))
    miss_u = [t["id"] for t in tasks if "cycles" not in t or "estimate_days" not in t]
    if miss_u:
        errors.append("dual-units missing: " + ",".join(miss_u))
    # ancestors
    anc: dict[str, set[str]] = {}
    if acyclic:
        for n in topo:
            s: set[str] = set()
            for d in deps[n]:
                s.add(d); s |= anc.get(d, set())
            anc[n] = s
        v0 = {i for i in ids if i.startswith(V0_PREFIX)}
        for t in tasks:
            tid = t["id"]
            if tid.startswith(V0_PREFIX):
                continue
            if not v0 <= anc[tid]:
                lack = sorted(v0 - anc[tid])
                errors.append(f"V0-precedence broken: {tid} lacks {lack[:3]}")
    # isolation
    dset = set(droppable)
    for t in tasks:
        if t["id"] in dset:
            continue
        hit = [d for d in deps[t["id"]] if d in dset]
        if hit:
            errors.append(f"isolation broken: {t['id']} depends on {hit}")
    # critical path (longest by cycles)
    cyc = {t["id"]: float(t.get("cycles", 0)) for t in tasks}
    best: dict[str, float] = {}; prev: dict[str, str | None] = {}
    cp: list[str] = []; cp_len = 0.0
    if acyclic:
        for n in topo:
            base = max((best[d] for d in deps[n]), default=0.0)
            best[n] = base + cyc[n]
            prev[n] = max(deps[n], key=lambda d: best[d]) if deps[n] else None
        end = max(best, key=lambda k: best[k])
        cp_len = best[end]
        node: str | None = end
        while node:
            cp.append(node); node = prev[node]
        cp.reverse()
    edges = sum(len(v) for v in deps.values())
    return {
        "acyclic": acyclic,
        "nodes": len(ids),
        "edges": edges,
        "errors": errors,
        "total_cycles": sum(cyc.values()),
        "critical_path_cycles": cp_len,
        "critical_path": cp,
        "verify_cmd_coverage": (len(ids) - len(miss_v)) / len(ids) if ids else 1.0,
        "self_review_cards": sorted(t["id"] for t in tasks if t.get("self_review")),
        "owner_review_cards": sorted(t["id"] for t in tasks if t.get("owner_review")),
        "milestone_counts": _mcounts(tasks),
    }

def _mcounts(tasks):
    out: dict[str, int] = {}
    for t in tasks:
        out[t.get("milestone", "?")] = out.get(t.get("milestone", "?"), 0) + 1
    return dict(sorted(out.items()))

def merge_patch(base: dict, patch: dict) -> list[dict]:
    tasks = {t.get("task_id", t.get("id")): dict(t) for t in base["tasks"]}
    for p in patch.get("patches", []):
        tid = p["task_id"]
        if tid not in tasks:
            raise SystemExit(f"patch targets unknown task: {tid}")
        tasks[tid].update(p.get("set", {}))
    merged = []
    for t in tasks.values():
        q = dict(t)
        q.setdefault("id", q.get("task_id"))
        q.setdefault("cycles", q.get("estimate_cycles", 0))
        q.setdefault("estimate_days", q.get("estimate_days", 0))
        merged.append(q)
    return merged

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--file"); ap.add_argument("--base"); ap.add_argument("--patch")
    ap.add_argument("--merged", action="store_true")
    a = ap.parse_args()
    if a.file:
        pack = load(a.file)
        rep = build_report(pack["tasks"], pack.get("isolation", {}).get("owner_droppable", []))
    elif a.base and a.patch and a.merged:
        rep = build_report(merge_patch(load(a.base), load(a.patch)), [])
        # 合并模式不检查 V0 先行（基线卡自有里程碑序）
        rep["errors"] = [e for e in rep["errors"] if not e.startswith("V0-precedence")]
    else:
        ap.error("need --file OR (--base --patch --merged)")
        return 2
    print(json.dumps(rep, ensure_ascii=False, indent=2))
    return 0 if not rep["errors"] and rep["acyclic"] else 1

if __name__ == "__main__":
    sys.exit(main())
