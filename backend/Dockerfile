# ============================================================
# CodeRAG 后端 Dockerfile
# ============================================================
FROM python:3.11-slim

WORKDIR /app

# 安装系统依赖（git 用于克隆仓库）
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    && rm -rf /var/lib/apt/lists/*

# 安装 Python 依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制代码
COPY app/ ./app/

# 数据卷
VOLUME ["/app/data", "/app/repos", "/app/chroma_data"]

# 环境变量（可被 docker-compose 覆盖）
ENV DATABASE_URL=sqlite:////app/data/app.db
ENV REPO_STORAGE_DIR=/app/repos
ENV CHROMA_PERSIST_DIR=/app/chroma_data
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
