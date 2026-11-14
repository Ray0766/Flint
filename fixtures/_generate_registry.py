"""registry 回放 fixture 生成器（M4-011/012 共用，E12 布局）。

生成器即真相：期望值（latest_stable、404 判别）由本文件的构造数据携带，
测试断言只对照这里写死的交换内容——改期望改这里，NEVER 改测试侧猜测。
运行：python fixtures/_generate_registry.py
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from flint.testing.replay import RecordedExchange, fixture_path, save_fixture

ROOT = Path(__file__).resolve().parent
DAY = date(2026, 7, 28)

PYPI_HTTPX = {
    "info": {"name": "httpx", "version": "0.28.1"},
    "releases": {
        "0.27.0": [{}],
        "0.28.1": [{}],
        "0.29.0rc1": [{}],
        "0.9.0": [{}],
    },
}


def _json_exchange(url: str, status: int, payload: object) -> RecordedExchange:
    return RecordedExchange(
        method="GET",
        url=url,
        status_code=status,
        content_type="application/json",
        body_text=json.dumps(payload, ensure_ascii=False),
    )


def generate_pypi() -> Path:
    path = fixture_path(ROOT, "registry_pypi", DAY)
    save_fixture(
        path,
        [
            _json_exchange(
                "https://pypi.org/pypi/httpx/json", 200, PYPI_HTTPX
            ),
            _json_exchange(
                "https://pypi.org/pypi/flint-no-such-package/json",
                404,
                {"message": "Not Found"},
            ),
            _json_exchange(
                "https://pypi.org/pypi/flint-broken-registry/json",
                503,
                {"message": "Service Unavailable"},
            ),
        ],
    )
    return path


NPM_ZUSTAND = {
    "name": "zustand",
    "dist-tags": {"latest": "5.0.3"},
    "versions": {
        "4.5.0": {}, "5.0.3": {}, "5.1.0-beta.1": {},
    },
}

CRATES_SERDE = {
    "crate": {"name": "serde", "max_stable_version": "1.0.219"},
}


def generate_npm() -> Path:
    path = fixture_path(ROOT, "registry_npm", DAY)
    save_fixture(
        path,
        [
            _json_exchange(
                "https://registry.npmjs.org/zustand", 200, NPM_ZUSTAND
            ),
            _json_exchange(
                "https://registry.npmjs.org/flint-no-such-package",
                404,
                {"error": "Not found"},
            ),
            _json_exchange(
                "https://registry.npmjs.org/flint-broken-registry",
                503,
                {"error": "Service Unavailable"},
            ),
        ],
    )
    return path


def generate_crates() -> Path:
    path = fixture_path(ROOT, "registry_crates", DAY)
    save_fixture(
        path,
        [
            _json_exchange(
                "https://crates.io/api/v1/crates/serde", 200, CRATES_SERDE
            ),
            _json_exchange(
                "https://crates.io/api/v1/crates/flint-no-such-package",
                404,
                {"errors": [{"detail": "Not Found"}]},
            ),
            _json_exchange(
                "https://crates.io/api/v1/crates/flint-broken-registry",
                503,
                {"errors": [{"detail": "Service Unavailable"}]},
            ),
        ],
    )
    return path


if __name__ == "__main__":
    print(generate_pypi())
    print(generate_npm())
    print(generate_crates())
