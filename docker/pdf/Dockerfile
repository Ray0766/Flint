# M3-035 PDF 验收容器（Q-003 选项 3：Linux 容器 = 生产同构）
# 一次性构建属环境预备（同 compose pg/redis 镜像类）；测试期 docker run
# 挂载仓库离线执行，不再联网。
FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
        libpango-1.0-0 \
        libpangocairo-1.0-0 \
        libgdk-pixbuf-2.0-0 \
        fonts-noto-cjk \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir weasyprint==69 markdown-it-py==4.2.0

WORKDIR /work
