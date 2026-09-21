FROM node:20.18.1-slim AS base  # arm64 지원 확인
RUN corepack enable

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
