"""OpenAI Agents demo instrumented with OpenLIT."""

import logging
import os
import sys

from dotenv import load_dotenv

load_dotenv()

REQUIRED_ENV = (
    "OPENAI_API_KEY",
    "OPENAI_MODEL",
    "OPENAI_AGENTS_API",
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

from fastapi import FastAPI
from pydantic import BaseModel

from src.instrument import init_instrumentation

app = FastAPI(title="OpenLIT + OpenAI Agents", version="0.1.0")
init_instrumentation(app)

# Import after instrumentation so Agent construction and SDK calls can be patched.
from src import rag


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
    answer = await rag.run_agent(req.query)
    return AskResponse(query=req.query, answer=answer)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.environ["PORT"]))
