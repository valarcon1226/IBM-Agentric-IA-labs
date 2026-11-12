FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir fastapi uvicorn pydantic

COPY webhook_sink/ webhook_sink/

EXPOSE 5001

CMD ["uvicorn", "webhook_sink.sink:app", "--host", "0.0.0.0", "--port", "5001"]
