# 金标 trace：gold-D-01

## inputs 清单
- 大类：cat-ai；关键词：行业大模型咨询
- 证据 docs：4 条（内联 fixture，离线）
- 证伪断言：0 条；支持断言：1 条
- user_provided 判 A optin：False
- 竞品（意图强度）：
  - Vendor gold-D-01-1（moderate）https://gold.example/gold-D-01/comp1
  - Vendor gold-D-01-2（moderate）https://gold.example/gold-D-01/comp2
  - Vendor gold-D-01-3（moderate）https://gold.example/gold-D-01/comp3
- refute 已执行：True；相关率：0.8
- 覆盖执行面：
  - q1: executed=True 新增竞品=3
  - q2: executed=True 新增竞品=0

## 判定依据
- 预测 verdict：D_insufficient；all_satisfied：['D_insufficient']
- C 档失败项：no_aligned_support
- 金标 expected：D_insufficient；all_satisfied：['D_insufficient']
- 比对：一致
