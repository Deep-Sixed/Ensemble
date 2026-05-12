import json
import os
from typing import AsyncIterator

import httpx
from fastapi import FastAPI, Request, Response
from fastapi.responses import StreamingResponse

app = FastAPI()

MODEL_MAP: dict[str, str] = {}
DEFAULT_MODEL = "qwen2.5-coder"

# Full GGUF name aliases → canonical router IDs
ALIASES: dict[str, str] = {
    "qwen2.5-coder-7b-instruct-q4_k_m": "qwen2.5-coder",
    "qwen3-4b-instruct-2507-ud-q4_k_xl": "qwen3-4b",
    "qwen3.6-35b-a3b-ud-q4_k_xl": "qwen3.6-35b",
    "Qwen3.5-9B-Uncensored-HauhauCS-Aggressive-Q4_K_M": "qwen3.5-uncensored",
}

MODELS_LIST = [
    {"id": "qwen2.5-coder", "label": "Qwen2.5 Coder 7B", "default": True},
    {"id": "qwen3-4b", "label": "Qwen3 4B Instruct"},
    {"id": "qwen3.6-35b", "label": "Qwen3.6 35B A3B"},
    {"id": "qwen3.5-uncensored", "label": "Qwen3.5 9B Uncensored"},
]


@app.on_event("startup")
async def startup() -> None:
    global MODEL_MAP, DEFAULT_MODEL
    DEFAULT_MODEL = os.environ.get("DEFAULT_MODEL", "qwen2.5-coder")
    MODEL_MAP = {
        "qwen2.5-coder": os.environ["QWEN25_CODER_URL"],
        "qwen3-4b": os.environ["QWEN3_4B_URL"],
        "qwen3.6-35b": os.environ["QWEN36_35B_URL"],
        "qwen3.5-uncensored": os.environ["QWEN35_UNCENSORED_URL"],
    }


def resolve_model(model: str | None) -> str:
    if not model or model == "default":
        return DEFAULT_MODEL
    return ALIASES.get(model, model)


def upstream_url(model_id: str) -> str:
    return MODEL_MAP.get(model_id, MODEL_MAP[DEFAULT_MODEL])


@app.get("/v1/models")
async def list_models() -> dict:
    return {
        "object": "list",
        "data": [
            {
                "id": m["id"],
                "object": "model",
                "created": 1700000000,
                "owned_by": "ensemble",
            }
            for m in MODELS_LIST
        ],
    }


@app.post("/v1/chat/completions")
async def chat_completions(request: Request) -> Response:
    body = await request.body()
    payload = json.loads(body)
    model_id = resolve_model(payload.get("model"))
    payload["model"] = model_id
    base = upstream_url(model_id)

    if payload.get("stream"):
        async def stream_upstream() -> AsyncIterator[bytes]:
            async with httpx.AsyncClient(timeout=None) as client:
                async with client.stream(
                    "POST",
                    f"{base}/v1/chat/completions",
                    content=json.dumps(payload),
                    headers={"Content-Type": "application/json"},
                ) as resp:
                    async for chunk in resp.aiter_bytes():
                        yield chunk

        return StreamingResponse(stream_upstream(), media_type="text/event-stream")

    async with httpx.AsyncClient(timeout=300.0) as client:
        resp = await client.post(
            f"{base}/v1/chat/completions",
            content=json.dumps(payload),
            headers={"Content-Type": "application/json"},
        )
    return Response(
        content=resp.content,
        media_type="application/json",
        status_code=resp.status_code,
    )


@app.get("/health")
async def health() -> dict:
    results: dict[str, bool] = {}
    async with httpx.AsyncClient(timeout=5.0) as client:
        for mid, url in MODEL_MAP.items():
            try:
                r = await client.get(f"{url}/health")
                results[mid] = r.status_code == 200
            except Exception:
                results[mid] = False
    return {"status": "ok", "upstreams": results}
