FROM python:3.11-slim

WORKDIR /app

# 依赖层缓存：先拷 requirements 再安装，代码改动不触发重新安装
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 只拷代码（.env/.venv/.chroma 已被 .dockerignore 排除，真实 API key 绝不会进镜像）
COPY app/ ./app/

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
