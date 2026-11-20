# syntax=docker/dockerfile:1.7
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    TP_DATA_DIR=/data \
    TP_HOST=0.0.0.0 \
    TP_PORT=8000

# OpenCV and the PDF tools need a few shared libraries.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /srv/termpilot
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY termpilot ./termpilot
COPY scripts ./scripts

RUN useradd --create-home --uid 10001 termpilot && mkdir -p /data && chown termpilot /data
USER termpilot
VOLUME ["/data"]
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=4)"

CMD ["python", "-m", "termpilot"]
