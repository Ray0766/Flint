# 文书金标 trace：golddoc-thesis-channels

## inputs 清单
- 模板：thesis（human_reader）；变体：channels
- facts：['fact-thesis-1', 'fact-thesis-2']；price_entries：['pe-compute-01']；
  profile_paths：['identity.org']

## 组稿依据
- 章节序 = 模板声明序：通过
- 通道清单比对（facts/price/profile 三面）：通过
  （期望：{'facts': ['fact-thesis-1', 'fact-thesis-2'], 'price_entries': ['pe-compute-01'], 'profile_paths': ['identity.org']}）
- 三通道互斥校验违规数：0
- 声明块防改写（保护执行器）：通过
- 三格式渲染（md 字节稳定 / html / docx）：通过
- 非空 claim 对齐（3 对全 supports）：通过
- 结论：green
