# AI 챗봇 서버 (FastAPI). 배포용 패키지만 설치한다 (requirements-deploy.txt)
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HF_HOME=/app/hf-cache

WORKDIR /app
COPY requirements-deploy.txt .
RUN pip install --no-cache-dir -r requirements-deploy.txt

COPY . .

EXPOSE 8000
# 세션(대화 기억)을 서버 메모리에 두므로 프로세스는 하나만 띄운다
CMD ["python", "-m", "uvicorn", "api_server:app", "--host", "0.0.0.0", "--port", "8000"]
