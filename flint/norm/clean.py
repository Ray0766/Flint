"""关键词清洗管道 · A3 第一段（M1-017，PDD v0.2 §3.1）。

管线顺序（对齐 §3.1「Unicode/大小写/全半角归一」）：
  NFKC 归一（全半角/兼容字符）→ 去 emoji 与不可见字符 → 繁→简字表 →
  casefold 小写 → 空白折叠。
中英术语映射（第二段）在 M1-018，canonical/别名归并（第三段）在 M1-019。

繁简转换为内置字表（S2-6：S3 选型清单外不引入新依赖；opencc 不在清单）。
字表按黄金用例与后续真实源数据增量维护——缺字的表现是「原样保留」，
不会产生错字。
"""
from __future__ import annotations

import unicodedata
from typing import Final

# 繁 -> 简 单字映射（覆盖当前语料；缺字原样保留，增量维护）。
T2S_CHAR_MAP: Final[dict[str, str]] = {
    "態": "态", "電": "电", "動": "动", "車": "车", "機": "机", "學": "学",
    "習": "习", "區": "区", "塊": "块", "鏈": "链", "語": "语", "體": "体",
    "網": "网", "絡": "络", "雲": "云", "運": "运", "記": "记", "憶": "忆",
    "開": "开", "發": "发", "熱": "热", "點": "点", "數": "数", "據": "据",
    "貨": "货", "幣": "币", "檢": "检", "強": "强", "無": "无", "醫": "医",
    "療": "疗", "計": "计", "艦": "舰", "補": "补", "貼": "贴", "驅": "驱",
    "們": "们", "為": "为", "與": "与", "產": "产", "業": "业", "應": "应",
    "鏡": "镜", "頭": "头", "壓": "压", "縮": "缩", "測": "测", "試": "试",
}

# emoji / 象形符号码点区间（含杂项符号、补充符号、箭头装饰）。
_EMOJI_RANGES: Final[tuple[tuple[int, int], ...]] = (
    (0x1F000, 0x1FAFF),
    (0x2600, 0x27BF),
    (0x2B00, 0x2BFF),
    (0x1F1E6, 0x1F1FF),
)

# 变体选择符 / 零宽字符 / 方向控制符：一律移除。
_STRIP_CODEPOINTS: Final[frozenset[int]] = frozenset(
    {0xFE0E, 0xFE0F, 0x200B, 0x200C, 0x200D, 0x200E, 0x200F, 0x2060, 0xFEFF}
)


def _drop_char(ch: str) -> bool:
    cp = ord(ch)
    if cp in _STRIP_CODEPOINTS:
        return True
    return any(lo <= cp <= hi for lo, hi in _EMOJI_RANGES)


def clean(raw: str) -> str:
    """Normalize one raw keyword: NFKC -> strip emoji/invisibles -> t2s ->
    casefold -> collapse whitespace. Idempotent by construction."""
    text = unicodedata.normalize("NFKC", raw)
    text = "".join(ch for ch in text if not _drop_char(ch))
    text = "".join(T2S_CHAR_MAP.get(ch, ch) for ch in text)
    text = text.casefold()
    return " ".join(text.split())
