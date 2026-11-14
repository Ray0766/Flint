# 金标 trace：gold-D-05

## inputs 清单
- 大类：cat-semiconductor；关键词：晶圆缺陷开源数据集
- 证据 docs：3 条（内联 fixture，离线）
- 证伪断言：0 条；支持断言：1 条
- user_provided 判 A optin：False
- 竞品（意图强度）：
  - Vendor gold-D-05-1（moderate）https://gold.example/gold-D-05/comp1
  - Vendor gold-D-05-2（moderate）https://gold.example/gold-D-05/comp2
- refute 已执行：True；相关率：0.8
- 覆盖执行面：
  - q1: executed=True 新增竞品=2
  - q2: executed=False 新增竞品=0

## 判定依据
- 预测 verdict：D_insufficient；all_satisfied：['D_insufficient']
- C 档失败项：coverage_not_met
- 金标 expected：D_insufficient；all_satisfied：['D_insufficient']
- 比对：一致
