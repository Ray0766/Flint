# 金标 trace：gold-A-05

## inputs 清单
- 大类：cat-ai；关键词：脑机接口写作助手
- 证据 docs：4 条（内联 fixture，离线）
- 证伪断言：1 条；支持断言：1 条
- user_provided 判 A optin：False
- 竞品（意图强度）：
  - Vendor gold-A-05-1（moderate）https://gold.example/gold-A-05/comp1
  - Vendor gold-A-05-2（moderate）https://gold.example/gold-A-05/comp2
- refute 已执行：True；相关率：0.8
- 覆盖执行面：
  - q1: executed=True 新增竞品=2

## 判定依据
- 预测 verdict：A_infeasible；all_satisfied：['A_infeasible']
- C 档失败项：coverage_not_met
- 金标 expected：A_infeasible；all_satisfied：['A_infeasible']
- 比对：一致
