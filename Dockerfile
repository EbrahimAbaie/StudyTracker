FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_DISABLE_PIP_VERSION_CHECK=1 DEBUG=False
WORKDIR /app
RUN groupadd --system appuser && useradd --system --gid appuser --home-dir /app appuser
COPY requirements.txt .
RUN --mount=type=bind,source=wheels,target=/wheels \
    if find /wheels -name '*.whl' -print -quit | grep -q .; then \
        pip install --no-cache-dir --no-index --find-links=/wheels -r requirements.txt; \
    else pip install --no-cache-dir -r requirements.txt; fi
COPY config ./config
COPY tracker ./tracker
COPY templates ./templates
COPY static ./static
COPY manage.py entrypoint.sh ./
RUN sed -i 's/\r$//' /app/entrypoint.sh && chmod +x /app/entrypoint.sh \
    && python manage.py collectstatic --noinput
EXPOSE 8000
ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "1", "--timeout", "60", "--access-logfile", "-", "--error-logfile", "-"]
