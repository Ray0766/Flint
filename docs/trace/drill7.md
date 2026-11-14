# drill7 runbook — 7 天日更演练（M1-040）

## 总览：7/7 green；零人工干预 = True

## 逐日
- 2026-06-29: scheduler=executed, job=done
- 2026-06-30: scheduler=executed, job=done
- 2026-07-01: scheduler=executed, job=done
- 2026-07-02: scheduler=executed, job=done
- 2026-07-03: scheduler=executed, job=done
- 2026-07-04: scheduler=executed, job=done
- 2026-07-05: scheduler=executed, job=done [degraded]
  - 角标：今日缺 weibo 数据

## E7 四指标计数器
- ingest_success_total: 在册
- degraded_sources_total: 在册
- job_duration_seconds: 在册
- llm_cost_cny_total: 在册
  - degraded_sources_total{source=weibo} = 1.000
  - ingest_success_total{source=arxiv} = 7.000
  - ingest_success_total{source=ghtrend} = 7.000
  - ingest_success_total{source=gtrends} = 7.000
  - ingest_success_total{source=weibo} = 6.000
  - job_duration_seconds{kind=daily_ingest} = 0.000
  - job_duration_seconds_count{kind=daily_ingest} = 7.000
  - job_duration_seconds_sum{kind=daily_ingest} = 7.695
  - llm_cost_cny_total{kind=daily_ingest} = 0.000

## degraded 场景
- 2026-07-05: 今日缺 weibo 数据（degradation_notes 已落库，reason=rate_limited）
