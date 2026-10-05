FROM python:3.13-slim

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

COPY pyproject.toml .
RUN uv pip install --system .

COPY . .

ENTRYPOINT ["python", "-u"]
CMD ["src/stage_0_plain_bot.py"]
