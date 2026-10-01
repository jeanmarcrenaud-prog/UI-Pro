# ====================== UI-Pro Frontend (Next.js) =====================
# Multi-stage build: deps -> build -> runtime

FROM node:20-slim AS base

WORKDIR /app

# ---- Stage 1: Dependencies ----
COPY package.json package-lock.json* ./
RUN npm install --no-audit --no-fund

# ---- Stage 2: Build ----
COPY . .
ARG NEXT_PUBLIC_API_URL=""
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
RUN npx next build

# ---- Stage 3: Runtime ----
FROM node:20-slim AS runtime

WORKDIR /app
ENV NODE_ENV=production \
    PORT=3000

COPY --from=base /app/package.json ./package.json
COPY --from=base /app/node_modules ./node_modules
COPY --from=base /app/.next ./.next
COPY --from=base /app/next.config.js ./next.config.js
COPY --from=base /app/public ./public

EXPOSE 3000

CMD ["npm", "start"]
