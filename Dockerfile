FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# uv 설치
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# 의존성 정의 파일 먼저 복사
COPY pyproject.toml ./
COPY uv.lock ./

# 프로젝트 소스 복사
COPY README.md ./
COPY src ./src

# 락파일 기준으로 의존성 설치
RUN uv sync --frozen --no-dev

EXPOSE 8000

CMD ["python", "-m", "src/python/main"]