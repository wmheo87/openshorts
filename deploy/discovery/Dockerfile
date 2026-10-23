FROM python:3.11-slim
WORKDIR /app
COPY requirements-discovery.txt ./
RUN --mount=type=secret,id=pip_ca \
    if [ -f /run/secrets/pip_ca ]; then export PIP_CERT=/run/secrets/pip_ca; fi; \
    pip install --no-cache-dir -r requirements-discovery.txt \
    && useradd --uid 10001 --create-home --shell /usr/sbin/nologin discovery \
    && mkdir /data && chown discovery:discovery /data
COPY --chown=discovery:discovery studio/ ./studio/
ENV PYTHONUNBUFFERED=1 DISCOVERY_ENABLED=1 DISCOVERY_DB_PATH=/data/discovery.sqlite3
USER discovery
EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s --start-period=10s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2)"
CMD ["uvicorn", "studio.discovery.app:app", "--host", "0.0.0.0", "--port", "8000"]
