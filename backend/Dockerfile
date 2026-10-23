FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY backend/requirements.lock /app/requirements.lock
RUN pip install --no-cache-dir -r requirements.lock
COPY backend/ /app/
RUN pip install --no-cache-dir --no-deps . \
    && useradd --create-home app
USER app
EXPOSE 8000
CMD ["python", "-m", "feedback2req.runtime", "backend"]
