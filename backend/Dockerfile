# arm64 지원 확인(2026-09). 주석은 반드시 줄 위에 — Dockerfile 은 명령 줄
# 끝 주석을 지원하지 않아 "FROM requires either one or three arguments" 로 깨진다.
FROM python:3.11.13-slim-bookworm

WORKDIR /app

# 의존성 먼저 설치(레이어 캐시)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# 비root 로 돌린다. 컨테이너 탈출 시 피해를 줄이고, 마운트한 /data/localdata 에
# 루트 소유 파일이 쌓이는 것도 막는다(uid 1000 = 호스트의 기본 사용자).
RUN useradd --uid 1000 --create-home --shell /usr/sbin/nologin app \
    && mkdir -p /data/localdata \
    && chown -R app:app /app /data/localdata
USER app

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
