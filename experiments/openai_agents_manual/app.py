"""Manual tool-loop agent with hand-rolled OTel instrumentation."""

import logging
import os
import sys

from dotenv import load_dotenv

load_dotenv()

REQUIRED_ENV = (
    "OPENAI_API_KEY",
    "OPENAI_MODEL",
    "OTEL_EXPORTER_OTLP_ENDPOINT",
    "OTEL_SERVICE_NAME",
)
missing = [name for name in REQUIRED_ENV if not os.environ.get(name)]
if missing:
    raise RuntimeError(f"Missing required environment variables: {', '.join(missing)}")

logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    format="%(asctime)s.%(msecs)03d %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stderr,
)

from fastapi import FastAPI  # noqa: E402
from openai import AsyncOpenAI  # noqa: E402
from pydantic import BaseModel  # noqa: E402

from src.instrument import init_instrumentation  # noqa: E402

app = FastAPI(title="OpenAI Agents Manual", version="0.1.0")
init_instrumentation(app)

from src import agent  # noqa: E402

client_kwargs = {"api_key": os.environ["OPENAI_API_KEY"]}
if os.environ.get("OPENAI_BASE_URL"):
    client_kwargs["base_url"] = os.environ["OPENAI_BASE_URL"]
client = AsyncOpenAI(**client_kwargs)
model = os.environ["OPENAI_MODEL"]


class AskRequest(BaseModel):
    query: str


class AskResponse(BaseModel):
    query: str
    answer: str


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/ask", response_model=AskResponse)
async def ask(req: AskRequest):
    answer = await agent.run_agent(req.query, client=client, model=model)
    return AskResponse(query=req.query, answer=answer)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "8003")))
