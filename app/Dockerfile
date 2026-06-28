FROM python:3.11-slim

WORKDIR /app

# 系统依赖（含 Tesseract OCR 中文支持）
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    tesseract-ocr \
    tesseract-ocr-chi-sim \
    tesseract-ocr-chi-tra \
    tesseract-ocr-eng \
    && rm -rf /var/lib/apt/lists/*

# Python 依赖
COPY pyproject.toml .
RUN pip install --no-cache-dir -e ".[dev]" || pip install --no-cache-dir \
    fastapi>=0.110.0 \
    uvicorn[standard]>=0.27.0 \
    sqlalchemy[asyncio]>=2.0.0 \
    asyncpg>=0.29.0 \
    aiosqlite>=0.20.0 \
    alembic>=1.13.0 \
    pydantic[email]>=2.5.0 \
    pydantic-settings>=2.1.0 \
    python-jose[cryptography]>=3.3.0 \
    bcrypt>=4.1.0 \
    python-multipart>=0.0.6 \
    celery[redis]>=5.3.0 \
    redis[hiredis]>=5.0.0 \
    httpx>=0.26.0 \
    loguru>=0.7.0 \
    pymupdf>=1.23.0 \
    python-docx>=1.1.0 \
    python-pptx>=0.6.0 \
    openpyxl>=3.1.0 \
    beautifulsoup4>=4.12.0 \
    lxml>=5.0.0 \
    langchain-text-splitters>=0.2.0 \
    pymilvus>=2.3.0 \
    minio>=7.2.0 \
    elasticsearch[async]>=8.12.0,<9.0.0 \
    neo4j>=5.18.0 \
    sentence-transformers>=2.7.0 \
    pyyaml>=6.0 \
    pytesseract>=0.3.0 \
    Pillow>=10.0.0

# 应用代码
COPY . .

# 启动命令
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
