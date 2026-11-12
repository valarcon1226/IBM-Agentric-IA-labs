FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY demo_app/ demo_app/

RUN mkdir -p /var/log/demo-app

ENV PORT=8000
ENV LOG_FILE_PATH=/var/log/demo-app/app.log

EXPOSE 8000

CMD ["uvicorn", "demo_app.main:app", "--host", "0.0.0.0", "--port", "8000"]
