# 金标 trace：gold-D-04

## inputs 清单
- 大类：cat-quantum；关键词：量子加密对讲终端
- 证据 docs：3 条（内联 fixture，离线）
- 证伪断言：0 条；支持断言：1 条
- user_provided 判 A optin：False
- 竞品（意图强度）：
  - Vendor gold-D-04-1（unknown）https://gold.example/gold-D-04/comp1
  - Vendor gold-D-04-2（weak）https://gold.example/gold-D-04/comp2
- refute 已执行：True；相关率：0.8
- 覆盖执行面：
  - q1: executed=True 新增竞品=2
  - q2: executed=True 新增竞品=0

## 判定依据
- 预测 verdict：D_insufficient；all_satisfied：['D_insufficient']
- C 档失败项：strong_or_unknown_competitor
- 金标 expected：D_insufficient；all_satisfied：['D_insufficient']
- 比对：一致
