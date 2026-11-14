# No pip install anywhere: the bot is standard library only, so the image is
# small, builds in seconds on a Raspberry Pi, and has no supply chain to trust.
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    TZ=Asia/Jerusalem \
    DB_PATH=/data/budget.db

RUN useradd --system --uid 10001 --create-home bot \
 && mkdir -p /data && chown bot:bot /data

WORKDIR /app
COPY budgetbot/ ./budgetbot/

USER bot
VOLUME ["/data"]

ENTRYPOINT ["python3", "-m", "budgetbot"]
CMD ["watch"]
