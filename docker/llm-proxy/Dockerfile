FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends procps \
    && rm -rf /var/lib/apt/lists/*

RUN useradd -m -s /bin/bash openclaw

WORKDIR /home/openclaw

COPY --chown=openclaw:openclaw requirements.txt /home/openclaw/requirements.txt
RUN pip install --no-cache-dir -r /home/openclaw/requirements.txt

COPY --chown=openclaw:openclaw proxy.py /home/openclaw/proxy.py
COPY --chown=openclaw:openclaw entrypoint.sh /home/openclaw/entrypoint.sh
RUN chmod +x /home/openclaw/entrypoint.sh

RUN mkdir -p /home/openclaw/.openclaw/logs \
    && chown -R openclaw:openclaw /home/openclaw/.openclaw

USER openclaw

EXPOSE 8200

HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python3 -c "import urllib.request; urllib.request.urlopen('http://localhost:8200/v1/proxy/health')" || exit 1

ENTRYPOINT ["/home/openclaw/entrypoint.sh"]
