# 金标 trace：gold-C-05

## inputs 清单
- 大类：cat-semiconductor；关键词：车规芯片老化预测
- 证据 docs：3 条（内联 fixture，离线）
- 证伪断言：0 条；支持断言：1 条
- user_provided 判 A optin：False
- 竞品（意图强度）：
  - Vendor gold-C-05-1（weak）https://gold.example/gold-C-05/comp1
  - Vendor gold-C-05-2（weak）https://gold.example/gold-C-05/comp2
- refute 已执行：True；相关率：0.8
- 覆盖执行面：
  - q1: executed=True 新增竞品=2
  - q2: executed=True 新增竞品=0

## 判定依据
- 预测 verdict：C_opportunity；all_satisfied：['C_opportunity']
- C 档失败项：（无）
- 金标 expected：C_opportunity；all_satisfied：['C_opportunity']
- 比对：一致
