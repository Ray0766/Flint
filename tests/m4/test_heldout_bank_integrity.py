"""H-1 常驻卫兵：held-out 题库文件 sha256 冻结钉死——题库是 owner 只读输入
（v1.0，129 题，43 对全覆盖，sha256[:16]=A80C8C73AF03C8DB）。任何增删改题目/
版本/字节即改 sha256 → **本测当场红**，强制「NEVER 增删改题库、改题走 S9」。
"""
from __future__ import annotations

import hashlib
from pathlib import Path

BANK_PATH = Path("assets/heldout_questions.yaml")
# 冻结值（owner 投放 v1.0 @2026-07-28，与台账 delivery 记录 A80C8C73AF03C8DB
# 逐字一致；bytes=16286）。NEVER 为「让某模型通过」而改题库或此常量。
BANK_SHA256 = "a80c8c73af03c8db3115943ad87f2eae7d60a4c095dc1b9b6bd79ae5bad2931e"
BANK_BYTES = 16286


def test_heldout_bank_frozen_sha256() -> None:
    raw = BANK_PATH.read_bytes()
    actual = hashlib.sha256(raw).hexdigest()
    assert actual == BANK_SHA256, (
        "held-out 题库文件已变 —— 题库只读（owner v1.0），NEVER 增删改题目/"
        "版本；改题走 S9 上报。若确为 owner 授权换版，须同步升 bank_version + "
        "更新此冻结 sha256 常量并留裁决记录。"
    )
    assert len(raw) == BANK_BYTES


def test_bank_sha256_prefix_matches_delivery_record() -> None:
    # 与台账 OWNER DELIVERY 行记录的 sha256[:16] 逐字一致
    assert BANK_SHA256[:16] == "a80c8c73af03c8db"
