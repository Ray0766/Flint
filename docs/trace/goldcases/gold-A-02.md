# 金标 trace：gold-A-02

## inputs 清单
- 大类：cat-energy；关键词：家用微型核电
- 证据 docs：5 条（内联 fixture，离线）
- 证伪断言：1 条；支持断言：1 条
- user_provided 判 A optin：False
- 竞品（意图强度）：
  - Vendor gold-A-02-1（moderate）https://gold.example/gold-A-02/comp1
  - Vendor gold-A-02-2（moderate）https://gold.example/gold-A-02/comp2
  - Vendor gold-A-02-3（moderate）https://gold.example/gold-A-02/comp3
- refute 已执行：True；相关率：0.4
- 覆盖执行面：
  - q1: executed=True 新增竞品=3
  - q2: executed=True 新增竞品=0

## 判定依据
- 预测 verdict：A_infeasible；all_satisfied：['A_infeasible', 'B_red_ocean']
- C 档失败项：refute_hit_rate_below_theta
- 金标 expected：A_infeasible；all_satisfied：['A_infeasible', 'B_red_ocean']
- 比对：一致
