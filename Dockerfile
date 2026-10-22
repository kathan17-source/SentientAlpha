FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY pyproject.toml requirements-runtime.lock ./
COPY backend ./backend
RUN pip install --no-cache-dir -r requirements-runtime.lock \
    && pip install --no-cache-dir --no-deps . \
    && useradd --uid 10001 --create-home researcher \
    && mkdir -p /data \
    && chown researcher:researcher /data
COPY alembic.ini ./
COPY migrations ./migrations
COPY config ./config
ENV DATABASE_URL=sqlite:////data/sentientalpha.db SENTIENTALPHA_MODE=simulation
USER researcher
EXPOSE 8000
CMD ["uvicorn", "sentientalpha.api.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
