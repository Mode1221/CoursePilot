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
COPY --from=build /app/.next ./.next
COPY --from=build /app/node_modules ./node_modules
COPY --from=build /app/package.json ./package.json
COPY --from=build /app/next.config.mjs ./next.config.mjs
COPY --from=build /app/public ./public
EXPOSE 3000
CMD ["pnpm", "start"]
