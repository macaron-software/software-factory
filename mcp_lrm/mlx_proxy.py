#!/usr/bin/env python3
"""
MLX Proxy - Translates OpenAI /v1/responses to /v1/chat/completions
Allows opencode to use mlx_lm.server which only supports chat/completions
"""

from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse, JSONResponse
import httpx
import json
import uuid
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("mlx_proxy")

app = FastAPI(title="MLX Proxy")


def normalize_message(msg: dict) -> dict:
    """
    Normalize message content to plain text.
    mlx_lm.server only supports 'text' content type.
    """
    role = msg.get("role", "user")
    content = msg.get("content", "")

    # Content can be:
    # - string: "hello" -> keep as is
    # - list of dicts: [{"type": "text", "text": "hello"}, {"type": "image_url", ...}]
    #   -> extract only text parts
    if isinstance(content, str):
        return {"role": role, "content": content}
    elif isinstance(content, list):
        text_parts = []
        for part in content:
            if isinstance(part, dict):
                if part.get("type") == "text":
                    text_parts.append(part.get("text", ""))
                elif part.get("type") == "input_text":
                    text_parts.append(part.get("text", ""))
                # Skip image_url, tool_use, etc.
            elif isinstance(part, str):
                text_parts.append(part)
        return {"role": role, "content": "\n".join(text_parts)}
    else:
        return {"role": role, "content": str(content)}

MLX_SERVER = "http://localhost:8002"

# Model name mapping (short name -> full path)
MODEL_ALIASES = {
    "glm": "/Users/sylvain/models/GLM-4.7-Flash-4bit",
    "glm-4.7-flash": "/Users/sylvain/models/GLM-4.7-Flash-4bit",
    "qwen": "mlx-community/Qwen3-32B-4bit",
}

@app.get("/v1/models")
async def list_models():
    """Proxy models endpoint"""
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{MLX_SERVER}/v1/models")
        return resp.json()

@app.post("/v1/responses")
async def create_response(request: Request):
    """
    Translate /v1/responses to /v1/chat/completions
    OpenAI Responses API -> Chat Completions API
    """
    body = await request.json()
    logger.info(f"Incoming request: {json.dumps(body)[:500]}")

    # Extract fields from responses format
    model = body.get("model", "default")
    # Map short model names to full paths
    model = MODEL_ALIASES.get(model, model)
    input_content = body.get("input", "")
    instructions = body.get("instructions", "")
    max_tokens = body.get("max_output_tokens", 4096)
    temperature = body.get("temperature", 0.7)
    stream = body.get("stream", False)

    # Build messages for chat/completions
    messages = []
    if instructions:
        messages.append({"role": "system", "content": instructions})

    # Handle input - can be string or list of messages
    if isinstance(input_content, str):
        messages.append({"role": "user", "content": input_content})
    elif isinstance(input_content, list):
        for item in input_content:
            if isinstance(item, dict):
                # Normalize message content to plain text
                msg = normalize_message(item)
                messages.append(msg)
            else:
                messages.append({"role": "user", "content": str(item)})

    # Build chat/completions request
    chat_request = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "stream": stream
    }
    logger.info(f"Sending to MLX: {json.dumps(chat_request)[:1000]}")

    if stream:
        # Streaming response - OpenAI Responses API format
        async def generate():
            response_id = f"resp_{uuid.uuid4().hex[:24]}"
            item_id = f"item_{uuid.uuid4().hex[:16]}"
            msg_id = f"msg_{uuid.uuid4().hex[:24]}"

            # Send response.created event first
            created_event = {
                "type": "response.created",
                "response": {
                    "id": response_id,
                    "object": "response",
                    "status": "in_progress",
                    "model": model,
                    "output": []
                }
            }
            yield f"data: {json.dumps(created_event)}\n\n"

            # Send output_item.added event
            item_added = {
                "type": "response.output_item.added",
                "output_index": 0,
                "item": {
                    "type": "message",
                    "id": msg_id,
                    "role": "assistant",
                    "content": []
                }
            }
            yield f"data: {json.dumps(item_added)}\n\n"

            # Send content_part.added event
            content_added = {
                "type": "response.content_part.added",
                "item_id": msg_id,
                "output_index": 0,
                "content_index": 0,
                "part": {
                    "type": "output_text",
                    "text": ""
                }
            }
            yield f"data: {json.dumps(content_added)}\n\n"

            async with httpx.AsyncClient(timeout=300) as client:
                async with client.stream("POST", f"{MLX_SERVER}/v1/chat/completions", json=chat_request) as resp:
                    async for line in resp.aiter_lines():
                        if line.startswith("data: "):
                            data = line[6:]
                            if data == "[DONE]":
                                # Send response.completed event
                                completed_event = {
                                    "type": "response.completed",
                                    "response": {
                                        "id": response_id,
                                        "object": "response",
                                        "status": "completed",
                                        "model": model
                                    }
                                }
                                yield f"data: {json.dumps(completed_event)}\n\n"
                                yield f"data: [DONE]\n\n"
                            else:
                                try:
                                    chunk = json.loads(data)
                                    # Transform to responses format
                                    responses_chunk = transform_chunk(chunk, item_id=msg_id)
                                    yield f"data: {json.dumps(responses_chunk)}\n\n"
                                except:
                                    pass  # Skip malformed chunks
        return StreamingResponse(generate(), media_type="text/event-stream")
    else:
        async with httpx.AsyncClient(timeout=300) as client:
            # Non-streaming
            resp = await client.post(f"{MLX_SERVER}/v1/chat/completions", json=chat_request)
            chat_response = resp.json()

            # Transform to responses format
            return JSONResponse(transform_response(chat_response, body))

def transform_response(chat_response: dict, original_request: dict) -> dict:
    """Transform chat/completions response to responses format"""
    choice = chat_response.get("choices", [{}])[0]
    message = choice.get("message", {})

    # Debug: log what mlx_lm returns
    logger.info(f"MLX response message keys: {list(message.keys())}")
    logger.info(f"content={repr(message.get('content', '')[:100] if message.get('content') else 'EMPTY')}")
    logger.info(f"reasoning={repr(message.get('reasoning', '')[:100] if message.get('reasoning') else 'EMPTY')}")

    # GLM-4.7-Flash uses "reasoning" field for extended thinking
    # Extract content from "content" first, fallback to "reasoning" if empty
    text_content = message.get("content", "") or message.get("reasoning", "")
    logger.info(f"Final text_content length: {len(text_content)}")

    return {
        "id": f"resp_{uuid.uuid4().hex[:24]}",
        "object": "response",
        "created_at": datetime.now().isoformat(),
        "model": chat_response.get("model", ""),
        "output": [
            {
                "type": "message",
                "id": f"msg_{uuid.uuid4().hex[:24]}",
                "role": "assistant",
                "content": [
                    {
                        "type": "output_text",
                        "text": text_content
                    }
                ]
            }
        ],
        "usage": chat_response.get("usage", {}),
        "status": "completed"
    }

def transform_chunk(chat_chunk: dict, item_id: str = None) -> dict:
    """Transform streaming chunk to OpenAI Responses API streaming format"""
    choice = chat_chunk.get("choices", [{}])[0]
    delta = choice.get("delta", {})

    # GLM-4.7-Flash: extract from "content" or "reasoning"
    text_content = delta.get("content", "") or delta.get("reasoning", "")

    # OpenAI Responses API format for text delta
    return {
        "type": "response.output_text.delta",
        "item_id": item_id or f"item_{uuid.uuid4().hex[:16]}",
        "output_index": 0,
        "content_index": 0,
        "delta": text_content  # Just the text string, not an object
    }

# Also proxy chat/completions directly
@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    """Direct proxy for chat/completions"""
    body = await request.json()
    async with httpx.AsyncClient(timeout=300) as client:
        resp = await client.post(f"{MLX_SERVER}/v1/chat/completions", json=body)
        return resp.json()

if __name__ == "__main__":
    import uvicorn
    print("Starting MLX Proxy on port 8003...")
    print("Proxying /v1/responses -> localhost:8002/v1/chat/completions")
    uvicorn.run(app, host="0.0.0.0", port=8003)
