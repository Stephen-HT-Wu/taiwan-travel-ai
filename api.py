import json
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from agent import stream_agent

load_dotenv(override=True)

# 每個 session 保留對話歷史（demo 用途）
sessions: dict[str, list] = {}


class ChatRequest(BaseModel):
    message: str
    session_id: str = "default"


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(title="Taiwan Travel AI", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def format_sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@app.post("/api/chat")
async def chat(req: ChatRequest):
    if req.session_id not in sessions:
        sessions[req.session_id] = []

    messages = sessions[req.session_id]

    def generate():
        for item in stream_agent(req.message, messages):
            yield format_sse(item["event"], item["data"])

    return StreamingResponse(generate(), media_type="text/event-stream")


@app.get("/api/health")
async def health():
    return {"status": "ok"}
