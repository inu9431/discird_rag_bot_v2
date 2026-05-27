# 파이썬 환경 설정
FROM python:3.13-slim

# 환경변수 
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# 가상환경 경로를 미리 등록
# ENV PATH="/app/.venv/bin:$PATH"

# 바이너리 복사
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# 필수 OS 패키지 설치 (psql 연결용)
# GCC는 빌드 후 삭제하여 이미지 용량 줄임
RUN apt-get update && apt-get install -y libpq-dev gcc curl && rm -rf /var/lib/apt/lists/*

# 디렉토리 작업 설정
WORKDIR /app

# 라이브러리 설치
COPY pyproject.toml uv.lock ./
RUN  uv pip install --system --no-cache -r pyproject.toml

# 소스 코드 복사
COPY . .

RUN python manage.py collectstatic --noinput

# 실행 권한 부여
RUN chmod +x manage.py

# 실행 명령
# Gunicorn 실행 시 worker 
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "2", "--timeout", "120"]
