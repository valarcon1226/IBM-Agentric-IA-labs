FROM python:3.12-slim
WORKDIR /app
COPY server.py .
USER nobody
EXPOSE 8080
HEALTHCHECK --interval=5s --timeout=3s --retries=5 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/health')"
CMD ["python", "server.py"]
