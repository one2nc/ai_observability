"""FastAPI RAG demo app — instrumented with OpenLLMetry (Traceloop)."""

import logging
import os
import sys

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, File, UploadFile
from pydantic import BaseModel

from instrument import init_instrumentation
import rag

logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    format="%(asctime)s.%(msecs)03d %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stderr,
)

app = FastAPI(title="AI Observability Demo — openllmetry_manual", version="0.1.0")
init_instrumentation(app)


class AskRequest(BaseModel):
    query: str
    user_id: str = "anonymous"


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
    result = rag.ask(req.query, user_id=req.user_id)
    return AskResponse(query=req.query, answer=result["answer"], sources=result["sources"])


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", "8001"))
    uvicorn.run(app, host="0.0.0.0", port=port)
