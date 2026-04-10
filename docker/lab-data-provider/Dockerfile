FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends procps curl \
    && rm -rf /var/lib/apt/lists/*

RUN useradd -m -s /bin/bash openclaw
WORKDIR /home/openclaw

COPY --chown=openclaw:openclaw requirements.txt /home/openclaw/requirements.txt
RUN pip install --no-cache-dir -r /home/openclaw/requirements.txt

COPY --chown=openclaw:openclaw data_provider.py /home/openclaw/data_provider.py

USER openclaw

EXPOSE 8300

HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -sf http://localhost:8300/health || exit 1

CMD ["python3", "data_provider.py"]
