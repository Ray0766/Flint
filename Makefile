# 燧石 Flint 开发入口（E12）。Windows 宿主无 make 时执行同款命令：
#   python -m harness.replay30 --days 30
DAYS ?= 30

.PHONY: dev-replay gate

dev-replay:
	python -m harness.replay30 --days $(DAYS)

# S7 全局门扩面（M4-042：eval/ 与 harness/ 承载出口断言级交付物，属交付面）
# ENV-01：`PYTHONIOENCODING=utf-8` 是**跑测试的固定前提**，不是可选项。
# 不带它，27 条走 subprocess 的判据会以 `TypeError: NoneType is not iterable` 假红
# （子进程按 GBK 写、父进程按 UTF-8 解 → stdout 变 None）。
# 纪律与那句人话：worker.md §4.3b · tools/check_encoding_env.py。
gate:
	ruff check . && mypy --strict flint eval harness && PYTHONIOENCODING=utf-8 pytest -q
