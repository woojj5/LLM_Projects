# apps/services/llm.py
import os, json, asyncio, httpx
from fastapi import HTTPException
from ..config import settings

DEMO_MODE = os.getenv("DEMO_MODE", "0") in ("1", "true", "True")
PROVIDER = os.getenv("PROVIDER", "openai").lower()

# ---------- Ollama ----------
async def _ollama_stream(messages, temperature=0.7):
    base = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
    model = os.getenv("OLLAMA_MODEL", "llama3.1:8b")
    payload = {
        "model": model,
        "messages": messages,  # [{"role":"system/user/assistant","content":"..."}]
        "options": {"temperature": float(temperature)},
        "stream": True,
    }
    async with httpx.AsyncClient(base_url=base, timeout=None) as client:
        async with client.stream("POST", "/api/chat", json=payload) as r:
            if r.status_code != 200:
                text = (await r.aread()).decode(errors="ignore")
                raise HTTPException(status_code=r.status_code, detail=text or "ollama error")
            # Ollama는 line-delimited JSON을 흘립니다 (SSE 아님)
            async for line in r.aiter_lines():
                if not line.strip():
                    continue
                try:
                    obj = json.loads(line)
                except Exception:
                    continue
                if obj.get("done"):
                    break
                delta = obj.get("message", {}).get("content", "")
                if delta:
                    yield delta

async def _ollama_completion(messages, temperature=0.7):
    base = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
    model = os.getenv("OLLAMA_MODEL", "llama3.1:8b")
    payload = {
        "model": model,
        "messages": messages,
        "options": {"temperature": float(temperature)},
        "stream": False,
    }
    async with httpx.AsyncClient(base_url=base, timeout=120) as client:
        r = await client.post("/api/chat", json=payload)
        if r.status_code != 200:
            raise HTTPException(status_code=r.status_code, detail=r.text or "ollama error")
        data = r.json()
        return data.get("message", {}).get("content", "")

# ---------- OpenAI ----------
async def _openai_stream(messages, temperature=0.7, max_retries: int = 2):
    headers = {"Authorization": f"Bearer {settings.openai_api_key}"}
    payload = {
        "model": settings.openai_model,
        "messages": messages,
        "temperature": temperature,
        "stream": True,
    }
    async with httpx.AsyncClient(base_url=settings.openai_base_url, timeout=None) as client:
        attempt = 0
        while True:
            async with client.stream("POST", "/chat/completions", json=payload, headers=headers) as r:
                if r.status_code in (429, 408, 500, 502, 503, 504) and attempt < max_retries:
                    await asyncio.sleep(1.2 * (attempt + 1))
                    attempt += 1
                    continue
                if r.status_code != 200:
                    text = (await r.aread()).decode(errors="ignore") if hasattr(r, "aread") else ""
                    raise HTTPException(status_code=r.status_code, detail=text or "upstream error")
                async for raw in r.aiter_lines():
                    if not raw or not raw.startswith("data:"):
                        continue
                    data = raw[5:].strip()
                    if data in ("", "[DONE]"):
                        break
                    try:
                        obj = json.loads(data)
                        delta = obj["choices"][0]["delta"].get("content", "")
                        if delta:
                            yield delta
                    except Exception:
                        continue
            break

async def _openai_completion(messages, temperature=0.7):
    async with httpx.AsyncClient(base_url=settings.openai_base_url, timeout=120) as client:
        payload = {"model": settings.openai_model, "messages": messages, "temperature": temperature}
        r = await client.post("/chat/completions", json=payload,
                              headers={"Authorization": f"Bearer {settings.openai_api_key}"})
        r.raise_for_status()
        data = r.json()
        return data["choices"][0]["message"]["content"]

# ---------- Public API (router에서 사용) ----------
async def chat_stream(messages, temperature=0.7):
    if DEMO_MODE:
        demo = "🤖 데모 모드: Ollama/모델 호출 없이 UI 스트리밍만 테스트 중입니다.\n환경변수 DEMO_MODE=0 으로 끄세요."
        for ch in demo:
            await asyncio.sleep(0.008)
            yield ch
        return

    if PROVIDER == "ollama":
        async for ch in _ollama_stream(messages, temperature):
            yield ch
    else:
        async for ch in _openai_stream(messages, temperature):
            yield ch

async def chat_completion(messages, temperature=0.7):
    if DEMO_MODE:
        return "🤖 데모 모드 응답 (실제 모델 호출 없음)"
    if PROVIDER == "ollama":
        return await _ollama_completion(messages, temperature)
    else:
        return await _openai_completion(messages, temperature)
