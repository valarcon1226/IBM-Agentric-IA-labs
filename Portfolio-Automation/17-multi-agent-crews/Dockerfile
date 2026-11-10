FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app app
COPY corpus corpus
RUN useradd --create-home appuser && mkdir data && chown appuser data
USER appuser
ENV CREWAI_DISABLE_TELEMETRY=true OTEL_SDK_DISABLED=true
EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s --retries=5 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
