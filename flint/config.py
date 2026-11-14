"""配置加载与 feature flag 骨架（M1-005，技术方案 E8）。

- 三环境 dev/staging/prod，仅 env 文件差异；密钥经环境变量注入（S3）。
- feature flags：后端为 DB 表（M1-003 迁移落表后接 SQL 实现），统一经 FlagStore
  协议访问 + 5 分钟进程内缓存；单测用 InMemoryFlagStore。
- billing_enabled 在 M5 前恒 false（S1 非目标：VIP 开关先置 false）。
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Final, Literal, Protocol

from flint.burst import BurstConfig
from flint.hotness import HotnessConfig
from flint.region.authority_axis import AuthorityWeights
from flint.weaksignal import WeakSignalConfig

EnvName = Literal["dev", "staging", "prod"]

REQUIRED_ENV_KEYS: Final[list[str]] = ["FLINT_ENV", "DATABASE_URL", "REDIS_URL"]
_VALID_ENVS: Final[frozenset[str]] = frozenset(("dev", "staging", "prod"))

FLAG_CACHE_TTL_SECONDS: Final[float] = 300.0

# E8 已知开关的静态默认值；DB 表中的显式值永远优先。
DEFAULT_FLAGS: Final[dict[str, bool]] = {
    "billing_enabled": False,
}


class ConfigError(Exception):
    """Startup-time configuration failure; carries the full list of offenders."""

    def __init__(self, message: str, missing: list[str]) -> None:
        super().__init__(message)
        self.missing = missing


@dataclass(frozen=True)
class ModelAccess:
    """模型接入面（`WIRE-10`）。

    改前 `Settings` 只有 `env` / `database_url` / `redis_url` 三项，
    而 `combo` 那一族要 `provider` 与 `embed_service`——**无处可配**。
    demo 是从模块级 `OLLAMA` 常量拿的，那条路 NEVER 进产品：
    一个写死在源码里的模型地址，换环境时没有任何东西会提醒你它没跟着换。

    三项**全都可以不设**：不设就是「没配模型」，端点据此回 503 并点名——
    **NEVER 编一个默认地址**。一个猜出来的 `localhost:11434` 在生产上
    要么连不上（好），要么连上了某个不该连的东西（更坏）。
    """

    base_url: str | None = None
    model: str | None = None
    embed_model: str | None = None

    @property
    def configured(self) -> bool:
        """两项齐了才算配好。**缺一项 NEVER 算半配**——
        半配的行为无法预测：地址在而模型名空，调用会以一个说不清的错误失败。
        """
        return bool(self.base_url) and bool(self.model)


@dataclass(frozen=True)
class Settings:
    env: EnvName
    database_url: str
    redis_url: str
    # 可选：不设即「没配模型」。**NEVER 进 `REQUIRED_ENV_KEYS`**——
    # 把它设成必填会让所有不跑模型的部署（以及 CI）起不来。
    models: ModelAccess = ModelAccess()


def load_settings(environ: Mapping[str, str] | None = None) -> Settings:
    """Validate the process environment in one pass and fail listing every
    missing required key at once (acceptance: startup failure enumerates gaps)."""
    src: Mapping[str, str] = os.environ if environ is None else environ
    missing = [k for k in REQUIRED_ENV_KEYS if not src.get(k)]
    if missing:
        raise ConfigError(
            "missing required environment variables: " + ", ".join(missing), missing
        )
    env_name = src["FLINT_ENV"]
    if env_name not in _VALID_ENVS:
        raise ConfigError(
            f"FLINT_ENV must be one of {sorted(_VALID_ENVS)}, got {env_name!r}",
            ["FLINT_ENV"],
        )
    return Settings(
        env=env_name,  # type: ignore[arg-type]
        database_url=src["DATABASE_URL"],
        redis_url=src["REDIS_URL"],
        models=ModelAccess(
            base_url=src.get("FLINT_MODEL_BASE_URL") or None,
            model=src.get("FLINT_MODEL_NAME") or None,
            embed_model=src.get("FLINT_EMBED_MODEL") or None,
        ),
    )


class FlagStore(Protocol):
    """Flag table backend. SQL implementation lands with migration-0001 (M1-003);
    unit tests use InMemoryFlagStore."""

    def read(self, name: str) -> bool | None: ...

    def write(self, name: str, value: bool) -> None: ...


class InMemoryFlagStore:
    def __init__(self) -> None:
        self._values: dict[str, bool] = {}
        self.read_count: int = 0

    def read(self, name: str) -> bool | None:
        self.read_count += 1
        return self._values.get(name)

    def write(self, name: str, value: bool) -> None:
        self._values[name] = value


@dataclass
class _CacheEntry:
    value: bool | None
    filled_at: float


@dataclass
class FeatureFlags:
    """Flag reads go through a per-process cache with a 300s TTL (E8);
    set() writes through to the store and drops the cached entry so the
    new value is visible immediately to this process."""

    store: FlagStore
    now: Callable[[], float] = time.monotonic
    ttl_seconds: float = FLAG_CACHE_TTL_SECONDS
    _cache: dict[str, _CacheEntry] = field(default_factory=dict)

    def is_enabled(self, name: str, default: bool = False) -> bool:
        entry = self._cache.get(name)
        if entry is None or self.now() - entry.filled_at >= self.ttl_seconds:
            entry = _CacheEntry(value=self.store.read(name), filled_at=self.now())
            self._cache[name] = entry
        if entry.value is not None:
            return entry.value
        if name in DEFAULT_FLAGS:
            return DEFAULT_FLAGS[name]
        return default

    def set(self, name: str, value: bool) -> None:
        self.store.write(name, value)
        self._cache.pop(name, None)


# ═════════════════════ 热点参数标定通道（BL-05）
#
# G/α/β/γ/ν、s/γ、agg_ceiling/drift_penalty/burst_coef、θ_rel、δ ——
# 十几个数散在四个模块里，**每一个都是 S4 的未决项**（「待金标集调参」）。
# 想调，此前只能改代码；改了代码就分不清「这版是标定过的」还是「谁顺手改的」。
#
# 本通道建的是**路**，不是结论：
#   · 参数从配置读；配置缺失就用**代码里那份初值**并标 `calibrated=False`；
#   · 初值只有一处 —— 三个模块的 dataclass 默认值。这里 NEVER 再抄一份数，
#     抄一份就有了第二个真相，而两个真相里总有一个是旧的。
#   · 调参本身是 owner 决策：本通道只读不写，NEVER 回写任何默认值。


class TuningError(ValueError):
    """配置里有认不出的键——NEVER 静默忽略。

    静默忽略的后果很具体：owner 以为自己调了参，实际跑的还是初值，
    而 A/B 对照表上两组数字一模一样——他会得出「这个参数没用」的结论。
    """


# 可调旋钮的闭集。加一个数进来就要在这里报到，否则它仍然只能靠改代码调。
TUNING_KEYS: Final[tuple[str, ...]] = (
    "hotness.gravity",
    "hotness.w_agg",
    "hotness.w_velocity",
    "hotness.w_accel",
    "hotness.novelty_weight",
    "burst.s",
    "burst.gamma",
    "weak_signal.agg_ceiling",
    "weak_signal.drift_penalty",
    "weak_signal.burst_coef",
    "theta_rel",
    "delta",
    # —— K3-01：authority 五档权重（初值来自方法论调研，见 authority_axis.py）——
    "authority.official",
    "authority.mainstream",
    "authority.industry",
    "authority.community",
    "authority.unknown",
)

# 只说来源；「未标定」那句警告由 `tuning_note` 统一加，NEVER 在两处各写一遍
# （两处各写一遍的结果是同一行里出现两次，读的人会开始跳过它）。
UNCALIBRATED_SOURCE: Final[str] = "代码内初值（三个模块的 dataclass 默认值）"


@dataclass(frozen=True)
class TuningProfile:
    """一组参数 + 它**从哪来**。两者一体：分开传，下一段代码就会丢掉标注。"""

    hotness: HotnessConfig
    burst: BurstConfig
    weak_signal: WeakSignalConfig
    theta_rel: float
    delta: float
    calibrated: bool
    source: str
    authority: AuthorityWeights = field(default_factory=AuthorityWeights)
    overrides: tuple[str, ...] = ()


def _split(mapping: Mapping[str, Any]) -> dict[str, Any]:
    """把 `{"hotness": {"gravity": 1.8}}` 摊成 `{"hotness.gravity": 1.8}`。"""
    flat: dict[str, Any] = {}
    for key, value in mapping.items():
        if isinstance(value, Mapping):
            for leaf, inner in value.items():
                flat[f"{key}.{leaf}"] = inner
        else:
            flat[key] = value
    return flat


def load_tuning(source: Mapping[str, Any] | Path | None = None) -> TuningProfile:
    """读一组参数。`None` / 文件不存在 → 回落初值并标未标定。

    文件不存在**不抛**：没有配置的机器上整条流水线本来就该跑得起来，
    初值就是为此存在的。抛的那一刻，「还没调参」变成了「跑不了」。
    """
    from flint.retrieval.relevance import THETA_REL
    from flint.topic.differentiate import _DELTA_FLOOR

    origin = UNCALIBRATED_SOURCE
    payload: Mapping[str, Any] | None = None
    if isinstance(source, Path):
        if source.exists():
            payload = json.loads(source.read_text(encoding="utf-8"))
            origin = f"配置文件 {source}"
    elif source is not None:
        payload = source
        origin = "调用方传入的配置"

    flat = _split(payload) if payload else {}
    unknown = [k for k in flat if k not in TUNING_KEYS]
    if unknown:
        raise TuningError(
            f"配置里有认不出的键：{unknown}。可调旋钮只有 {list(TUNING_KEYS)}——"
            "静默忽略会让 owner 以为自己调了参，而跑的还是初值。"
        )

    def group(prefix: str) -> dict[str, Any]:
        return {
            k.split(".", 1)[1]: v for k, v in flat.items() if k.startswith(f"{prefix}.")
        }

    return TuningProfile(
        hotness=replace(HotnessConfig(), **group("hotness")),
        burst=replace(BurstConfig(), **group("burst")),
        weak_signal=replace(WeakSignalConfig(), **group("weak_signal")),
        theta_rel=float(flat.get("theta_rel", THETA_REL)),
        delta=float(flat.get("delta", _DELTA_FLOOR)),
        calibrated=bool(flat),
        source=origin,
        authority=replace(AuthorityWeights(), **group("authority")),
        overrides=tuple(k for k in TUNING_KEYS if k in flat),
    )


def tuning_note(profile: TuningProfile) -> str:
    """报告里**必须**带的那一行：参数从哪来、标没标定、哪几个被覆盖了。

    「未标定」写成句子而不是只留个字段：字段要人去查，句子会被读到。
    「已标定」也要列出**哪几个**——真相往往是「θ_rel 标了，G 没标」，
    而一个整体印象会把没标的那些一起算成标过的。
    """
    head = f"参数来源 = {profile.source}"
    if not profile.calibrated:
        return f"{head}｜**未标定**：本结果 report_only，NEVER 当作调参结论"
    covered = "、".join(profile.overrides)
    missing = [k for k in TUNING_KEYS if k not in profile.overrides]
    tail = f"｜来自配置：{covered}"
    if missing:
        tail += f"｜仍是初值（未标定）：{'、'.join(missing)}"
    return head + tail


# ═════════════════════ Z 线（一次通过率）初值（Z-01）
#
# `eval/pass_rate.py` 此前的口径是「初值未定 → verdict='report_only'」——
# 只报告不判定，NEVER 代 owner 画线。owner 2026-08-04 指示：
# **线先画上，达不到是另一件事**。于是这里给出初值，度量器从此出真判定。
#
# 0.95 的一半来自权威（DORA 2024 elite 档变更失败率 ≤5%），一半来自本项目实测
# （M4 19 卡 rate=1.0、v0.4 122 卡零 review_failed、v0.4.1 第 2 批 56 卡 1 处返工痕迹）。
# 推导与误差（三法则，95% 下界 ≈ 0.985）写在 docs/Z线初值-v041.md。
#
# **初值只写这一处**：`eval/pass_rate.py` 里 NEVER 再抄一份，抄一份就有了第二个真相。


class ZLineError(ValueError):
    """Z 线配置写错——NEVER 静默回落初值。

    静默回落的后果：owner 以为自己把线调到了 0.8，实际跑的还是 0.95，
    而报告上写着 fail——他会去查代码，而不是去查自己那行配置。
    """


Z_LINE_INITIAL: Final[float] = 0.95

Z_LINE_BASIS: Final[str] = (
    "初值 0.95 = DORA 2024 报告 elite 档变更失败率 ≤5% 的换算值；"
    "本项目实测高于它（n≈197，零 review_failed）。"
    "推导与误差见 docs/Z线初值-v041.md"
)


def load_z_line(env: Mapping[str, str] | None = None) -> float:
    """取 Z 线。环境变量 `FLINT_Z_LINE` 可覆盖；没设就是初值。

    **回落的是初值，不是 None**：回落 None 就又退回 `report_only`，
    等于这条线没画。
    """
    source = env if env is not None else os.environ
    raw = source.get("FLINT_Z_LINE")
    if raw is None or raw == "":
        return Z_LINE_INITIAL
    try:
        value = float(raw)
    except ValueError as err:
        raise ZLineError(f"FLINT_Z_LINE 不是数字：{raw!r}") from err
    if not 0.0 <= value <= 1.0:
        raise ZLineError(f"FLINT_Z_LINE 不在 [0,1] 内：{value}")
    return value


# ═════════════════════ 参数标定状态（CAL-02）
#
# 本卡的结论是**今天一个参数都标定不了**，四个理由各有实测撑着（见下）。
# 所以这里落的是**标定状态**，不是标定值：
#   · 「没写状态」与「查过了没问题」在盘上长得一模一样，这张表把它们分开；
#   · 没标定的必须写清**为什么** + **证据在哪**——「待标定」三个字不是理由。
#
# 「NEVER 反推阈值凑指标」的落法：`CALIBRATION_CALIBER` 是**先写好的评价口径**
# （用哪批金标 / 算什么指标 / 多少算过线），它有指纹；调完再改口径，指纹就对不上，
# 测试会红。**先定口径，再看数**，顺序反过来就是拿答案去凑题。

CALIBRATION_CALIBER: Final[dict[str, dict[str, str]]] = {
    "theta_rel": {
        "goldset": "assets/goldsets/relevance.jsonl（60 条逐对相关标注）",
        "metric": "以 hit_rate 为分数、以逐对标注为真值时的 F1",
        "pass_line": "F1 ≥ 0.80 且正负两类各 ≥ 20 条才认为标定有效",
    },
    "delta": {
        "goldset": "assets/goldsets/same_topic.jsonl（60 对同主题标注）",
        "metric": "以余弦距离为分数、以 same/different 为真值时的 F1",
        "pass_line": "F1 ≥ 0.80 才认为标定有效；低于此值说明分数本身没有区分力",
    },
    "hotness": {
        "goldset": "（无）——没有任何金标热度序列",
        "metric": "A/B 对照下的排序一致率",
        "pass_line": "有金标序列且一致率 ≥ 0.80 才谈得上标定",
    },
    "lineage_accuracy": {
        "goldset": "assets/goldsets/lineage.jsonl（60 簇血缘事件标注）",
        "metric": "判对的事件数 / 可判的事件数",
        "pass_line": "S4 出口线：≥90%（≥50 簇），且样本里要有可判错的情形",
    },
}


def caliber_fingerprint() -> str:
    """评价口径的指纹。**出数之后再动口径，这个数就变了。**"""
    return hashlib.sha256(
        json.dumps(CALIBRATION_CALIBER, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()


CALIBRATION_STATUS: Final[dict[str, dict[str, Any]]] = {
    "theta_rel": {
        "calibrated": False,
        "value": 0.6,
        "sample_size": 60,
        "date": "2026-08-04",
        "reason": (
            "形状不对，不是数量不够：θ_rel 是**每个查询**的 hit_rate"
            "（top-k 里被判相关的比例）的阈值，而金标是**逐对**的相关标注。"
            "要标定它，需要「每个查询的 hit_rate + 这次检索该不该被接受」的成对真值，"
            "而后者今天没有"
        ),
        "evidence": ["flint/retrieval/relevance.py", "assets/goldsets/relevance.jsonl"],
    },
    "delta": {
        "calibrated": False,
        "value": 0.05,
        "sample_size": 60,
        "date": "2026-08-04",
        "reason": (
            "分数本身没有区分力：demo 库的关键词嵌入是随机向量"
            "（任意两词余弦距离均值 1.0001、标准差 0.031，1024 维随机向量的特征），"
            "扫遍所有阈值最优 F1 只有 0.22，且 same 对比 different 对**还远**——"
            "在这种分数上定出来的 δ 是噪声"
        ),
        "evidence": ["assets/goldsets/same_topic.jsonl", "docs/参数标定-v041.md"],
    },
    "hotness": {
        "calibrated": False,
        "value": None,
        "sample_size": 0,
        "date": "2026-08-04",
        "reason": (
            "没有任何金标热度序列可比：harness/tune_hotness.py 一直是 report_only，"
            "CAL-01 也没采集热度面的标注。没有真值就没有「最优」"
        ),
        "evidence": ["harness/tune_hotness.py"],
    },
    "lineage_accuracy": {
        "calibrated": False,
        "value": None,
        "sample_size": 60,
        "date": "2026-08-04",
        "reason": (
            "测得出但判不了：CAL-01 实测 60/60 簇 correct（=1.00），"
            "但那批语料里**一次簇漂移都没有**——判不出错不等于没错，"
            "拿这个 100% 去对 S4 的 ≥90% 出口线说明不了问题"
        ),
        "evidence": ["assets/goldsets/lineage.jsonl",
                     "docs/blocked/LINEAGE-GOLD-REPLAY-MISSING.md"],
    },
}
