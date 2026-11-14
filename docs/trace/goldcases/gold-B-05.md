# 金标 trace：gold-B-05

## inputs 清单
- 大类：cat-semiconductor；关键词：国产 EDA 插件市场
- 证据 docs：4 条（内联 fixture，离线）
- 证伪断言：0 条；支持断言：1 条
- user_provided 判 A optin：False
- 竞品（意图强度）：
  - Vendor gold-B-05-1（strong）https://gold.example/gold-B-05/comp1
  - Vendor gold-B-05-2（moderate）https://gold.example/gold-B-05/comp2
  - Vendor gold-B-05-3（weak）https://gold.example/gold-B-05/comp3
- refute 已执行：True；相关率：0.8
- 覆盖执行面：
  - q1: executed=True 新增竞品=3
  - q2: executed=True 新增竞品=0

## 判定依据
- 预测 verdict：B_red_ocean；all_satisfied：['B_red_ocean']
- C 档失败项：strong_or_unknown_competitor
- 金标 expected：B_red_ocean；all_satisfied：['B_red_ocean']
- 比对：一致
