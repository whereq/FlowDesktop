# =============================================================================
# FlowDesktop frontend — production Dockerfile
#
# Build context is the REPOSITORY ROOT:
#     docker build -f docker/frontend/Dockerfile .
# =============================================================================

# -----------------------------------------------------------------------------
# Stage 1: build
# -----------------------------------------------------------------------------
FROM node:22-alpine AS builder

WORKDIR /app

COPY frontend/package.json frontend/yarn.lock* ./
RUN yarn install --frozen-lockfile

COPY frontend/ ./

# The OIDC settings are baked into the JS bundle at build time. Point these at
# YOUR identity provider before building.
ARG VITE_KEYCLOAK_URL=https://auth.example.com
ARG VITE_KEYCLOAK_REALM=flowdesktop
ARG VITE_KEYCLOAK_CLIENT_ID=flowdesktop-spa
ENV VITE_KEYCLOAK_URL=$VITE_KEYCLOAK_URL
ENV VITE_KEYCLOAK_REALM=$VITE_KEYCLOAK_REALM
ENV VITE_KEYCLOAK_CLIENT_ID=$VITE_KEYCLOAK_CLIENT_ID

RUN yarn build

# -----------------------------------------------------------------------------
# Stage 2: serve
# -----------------------------------------------------------------------------
FROM nginx:alpine AS runtime

LABEL maintainer="FlowDesktop contributors"
LABEL description="FlowDesktop frontend"

COPY docker/frontend/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=builder /app/dist /usr/share/nginx/html

HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD wget -q --spider http://localhost:80/health || exit 1

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
