# Imagen solo con dependencias — el código y los datos (jobs.db, CVs_Listos, .env) se montan
# desde el host en /app (ver docker-compose.yml), así se actualizan sin rebuild.
FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONIOENCODING=utf-8 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

WORKDIR /app
COPY requirements.txt .
# jobspy fija numpy==1.26.3 pero langchain-community pide >=2.1 (ver nota en requirements.txt)
RUN grep -v python-jobspy requirements.txt > /tmp/req.txt \
 && pip install --no-cache-dir -r /tmp/req.txt \
 && pip install --no-cache-dir --no-deps python-jobspy \
 && pip install --no-cache-dir pandas tls-client markdownify regex \
 && playwright install --with-deps chromium \
 && chmod -R a+rx /ms-playwright
