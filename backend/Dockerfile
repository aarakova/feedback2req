FROM node:24-slim AS frontend
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 F2R_FRONTEND_DIST=/app/frontend/dist
WORKDIR /app
COPY backend/requirements.lock /app/requirements.lock
RUN pip install --no-cache-dir -r requirements.lock
COPY backend/ /app/
COPY --from=frontend /frontend/dist /app/frontend/dist
RUN pip install --no-cache-dir --no-deps . \
    && useradd --create-home app
USER app
EXPOSE 8000
CMD ["uvicorn", "feedback2req.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--no-access-log", "--no-proxy-headers"]
