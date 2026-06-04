"""FastAPI RAG demo app — OpenLLMetry + manual spans routed through Bifrost."""

import logging
import os
import sys

from dotenv import load_dotenv

load_dotenv()

import openai
from fastapi import FastAPI, File, UploadFile
from fastapi import HTTPException
from pydantic import BaseModel

from instrument import init_instrumentation
import rag

logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    format="%(asctime)s.%(msecs)03d %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stderr,
)

app = FastAPI(title="AI Observability Demo — 04_bifrost", version="0.1.0")
init_instrumentation(app)


class AskRequest(BaseModel):
    query: str
    user_id: str = "anonymous"
    chat_model: str | None = None


class AskResponse(BaseModel):
    query: str
    answer: str
    sources: list[dict]


class IngestResponse(BaseModel):
    source: str
    chunks_stored: int


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/ingest", response_model=IngestResponse)
async def ingest(file: UploadFile = File(...)):
    content = (await file.read()).decode("utf-8")
    source = file.filename or "unknown"
    count = rag.ingest_file(content, source)
    return IngestResponse(source=source, chunks_stored=count)


@app.post("/ask", response_model=AskResponse)
def ask_endpoint(req: AskRequest):
    try:
        result = rag.ask(req.query, user_id=req.user_id, chat_model=req.chat_model)
    except openai.APIStatusError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={
                "error": "upstream_model_request_failed",
                "message": str(exc),
                "chat_model": req.chat_model,
            },
        ) from exc
    return AskResponse(query=req.query, answer=result["answer"], sources=result["sources"])


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", "8004"))
    uvicorn.run(app, host="0.0.0.0", port=port)
