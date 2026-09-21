# arm64 지원 확인(2026-09). 주석은 반드시 줄 위에 — Dockerfile 은 명령 줄
# 끝 주석을 지원하지 않아 "FROM requires either one or three arguments" 로 깨진다.
FROM node:20.18.1-slim AS base
# corepack enable 은 최신 pnpm 을 받아오면서 서명키를 검증하는데, node 20.18.1 에
# 박힌 키가 낡아 "Cannot find matching keyid" 로 빌드가 깨진다(Release images 실패 원인 2).
# 락파일이 lockfileVersion 9.0 이라 pnpm 9 을 고정해 설치한다(CI 의 action-setup 과 동일).
ARG PNPM_VERSION=9.15.4
RUN npm install -g pnpm@${PNPM_VERSION} && pnpm --version

FROM base AS deps
WORKDIR /app
COPY package.json pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile

FROM base AS build
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
# NEXT_PUBLIC_* 는 빌드 시점에 번들에 주입된다(런타임 아님) → build arg 로 받음
ARG NEXT_PUBLIC_API_BASE=http://localhost:8000
ARG NEXT_PUBLIC_NAVER_MAP_CLIENT_ID=
ENV NEXT_PUBLIC_API_BASE=$NEXT_PUBLIC_API_BASE
ENV NEXT_PUBLIC_NAVER_MAP_CLIENT_ID=$NEXT_PUBLIC_NAVER_MAP_CLIENT_ID
RUN pnpm build

FROM base AS run
WORKDIR /app
ENV NODE_ENV=production
# standalone 출력은 실제로 쓰이는 모듈만 추려 담는다 → node_modules 전체 복사 불필요.
# server.js 가 next.config 까지 포함해 나오므로 이 셋이면 돈다.
COPY --from=build --chown=node:node /app/.next/standalone ./
COPY --from=build --chown=node:node /app/.next/static ./.next/static
COPY --from=build --chown=node:node /app/public ./public
USER node
EXPOSE 3000
ENV PORT=3000 HOSTNAME=0.0.0.0
CMD ["node", "server.js"]
