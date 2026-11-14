# 文书金标 trace：golddoc-vibe_pack-plain

## inputs 清单
- 模板：vibe_pack（ai_executor）；变体：plain
- facts：['fact-vibe_pack-1', 'fact-vibe_pack-2']；price_entries：[]；
  profile_paths：[]

## 组稿依据
- 章节序 = 模板声明序：通过
- 通道清单比对（facts/price/profile 三面）：通过
  （期望：{'facts': ['fact-vibe_pack-1', 'fact-vibe_pack-2'], 'price_entries': [], 'profile_paths': []}）
- 三通道互斥校验违规数：0
- 声明块防改写（保护执行器）：通过
- 三格式渲染（md 字节稳定 / html / docx）：通过
- 非空 claim 对齐（3 对全 supports）：通过
- 结论：green
