FROM python:3.11-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

EXPOSE 8000

# 容器启动时自动建表；SEED_DEMO=1 时写入演示数据
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port 8000"]
