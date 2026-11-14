# 金标 trace：gold-B-01

## inputs 清单
- 大类：cat-ai；关键词：会议纪要摘要工具
- 证据 docs：4 条（内联 fixture，离线）
- 证伪断言：0 条；支持断言：1 条
- user_provided 判 A optin：False
- 竞品（意图强度）：
  - Vendor gold-B-01-1（moderate）https://gold.example/gold-B-01/comp1
  - Vendor gold-B-01-2（moderate）https://gold.example/gold-B-01/comp2
  - Vendor gold-B-01-3（moderate）https://gold.example/gold-B-01/comp3
- refute 已执行：True；相关率：0.8
- 覆盖执行面：
  - q1: executed=True 新增竞品=3
  - q2: executed=True 新增竞品=0

## 判定依据
- 预测 verdict：B_red_ocean；all_satisfied：['B_red_ocean', 'C_opportunity']
- C 档失败项：（无）
- 金标 expected：B_red_ocean；all_satisfied：['B_red_ocean', 'C_opportunity']
- 比对：一致
