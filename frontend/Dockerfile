FROM node:24-slim AS build
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM nginx:1.28-alpine
COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /frontend/dist /usr/share/nginx/html
HEALTHCHECK --interval=5s --timeout=3s --retries=12 CMD wget -q --spider http://127.0.0.1/ || exit 1
