# Build context is the repo root (npm workspace root), not app/web — see docker-compose.yml.
FROM node:22-slim AS build
WORKDIR /workspace
COPY package.json package-lock.json ./
COPY app/web/package.json app/web/package.json
RUN npm ci
COPY app/web app/web
# NEXT_PUBLIC_* vars are inlined into the client bundle at build time, so this
# must be a build ARG, not a runtime `environment:` entry in docker-compose.yml.
ARG NEXT_PUBLIC_API_URL=http://localhost:8000
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
RUN npm run build --workspace app/web

FROM node:22-slim
WORKDIR /workspace
COPY --from=build /workspace/app/web/.next/standalone ./
COPY --from=build /workspace/app/web/.next/static ./app/web/.next/static
COPY --from=build /workspace/app/web/public ./app/web/public

EXPOSE 3000
ENV PORT=3000 HOSTNAME=0.0.0.0
CMD ["node", "app/web/server.js"]
