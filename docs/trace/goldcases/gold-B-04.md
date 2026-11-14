# 金标 trace：gold-B-04

## inputs 清单
- 大类：cat-quantum；关键词：量子随机数云服务
- 证据 docs：5 条（内联 fixture，离线）
- 证伪断言：0 条；支持断言：1 条
- user_provided 判 A optin：False
- 竞品（意图强度）：
  - Vendor gold-B-04-1（moderate）https://gold.example/gold-B-04/comp1
  - Vendor gold-B-04-2（moderate）https://gold.example/gold-B-04/comp2
  - Vendor gold-B-04-3（moderate）https://gold.example/gold-B-04/comp3
  - Vendor gold-B-04-4（unknown）https://gold.example/gold-B-04/comp4
- refute 已执行：True；相关率：0.8
- 覆盖执行面：
  - q1: executed=True 新增竞品=4
  - q2: executed=True 新增竞品=0

## 判定依据
- 预测 verdict：B_red_ocean；all_satisfied：['B_red_ocean']
- C 档失败项：strong_or_unknown_competitor
- 金标 expected：B_red_ocean；all_satisfied：['B_red_ocean']
- 比对：一致
