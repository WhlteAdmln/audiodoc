ARG RUNTIME_BASE=python:3.12-slim

FROM python:3.12-slim AS builder

WORKDIR /build

COPY pyproject.toml requirements-lock.txt ./
COPY app.py ./
COPY audiodoc ./audiodoc

RUN python -m pip wheel \
    --no-cache-dir \
    --wheel-dir=/wheels \
    --requirement requirements-lock.txt \
    && python -m pip wheel \
        --no-cache-dir \
        --no-deps \
        --wheel-dir=/wheels \
        .

FROM ${RUNTIME_BASE} AS runtime

RUN apt-get update \
    && apt-get install --yes --no-install-recommends \
        ca-certificates \
        djvulibre-bin \
        libgomp1 \
        passwd \
        tesseract-ocr \
        tesseract-ocr-eng \
        tesseract-ocr-rus \
    && if ! python -c 'import sys, venv; assert sys.version_info[:2] == (3, 12)' >/dev/null 2>&1; then \
        apt-get install --yes --no-install-recommends python3.12 python3.12-venv; \
        ln -sfn /usr/bin/python3.12 /usr/local/bin/python; \
    fi \
    && python -m venv /opt/venv \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /wheels /wheels
COPY --from=builder /build/requirements-lock.txt /tmp/requirements-lock.txt

RUN python -m pip install \
    --no-cache-dir \
    --no-index \
    --find-links=/wheels \
    --requirement /tmp/requirements-lock.txt \
    audiodoc \
    && rm -rf /wheels /tmp/requirements-lock.txt

COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint

RUN chmod 0755 /usr/local/bin/docker-entrypoint

RUN groupadd --system --gid 10001 audiodoc \
    && useradd --system --uid 10001 --gid audiodoc \
        --create-home --home-dir /home/audiodoc \
        --shell /usr/sbin/nologin audiodoc \
    && install -d -o audiodoc -g audiodoc /data /data/models

ENV PATH="/opt/venv/bin:${PATH}" \
    AUDIODOC_HOME=/data \
    HF_HOME=/data/models \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

LABEL org.opencontainers.image.source="https://github.com/WhlteAdmln/audiodoc"

WORKDIR /app
VOLUME ["/data"]
EXPOSE 8000

USER audiodoc:audiodoc

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3)"]

ENTRYPOINT ["/usr/local/bin/docker-entrypoint"]
CMD ["audiodoc", "run", "--host", "0.0.0.0"]
