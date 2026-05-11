import asyncio
import os
from pathlib import Path

import structlog
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

load_dotenv(Path(__file__).parent.parent.parent / ".env")

logger = structlog.get_logger()

# Rate limiter
limiter = Limiter(key_func=get_remote_address)

app = FastAPI(
    title="Market Intelligence Agent API",
    description="AI-ассистент для анализа конкурентов",
    version="1.0.0",
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Pydantic схемы ---

class ChatRequest(BaseModel):
    company: str = Field(..., min_length=1, max_length=200, description="Название компании или URL")
    language: str = Field(default="Russian", description="Язык отчёта")

    class Config:
        json_schema_extra = {
            "example": {
                "company": "Notion",
                "language": "Russian"
            }
        }


class HealthResponse(BaseModel):
    status: str
    version: str


# --- Эндпоинты ---

@app.get("/health", response_model=HealthResponse)
async def health():
    """Проверка статуса сервиса."""
    return HealthResponse(status="ok", version="1.0.0")


@app.post("/chat")
@limiter.limit("10/minute")
async def chat(request: Request, body: ChatRequest):
    """
    Запускает агента и стримит отчёт по конкуренту.
    Поддерживает Server-Sent Events (SSE).
    """
    logger.info("chat_request", company=body.company, language=body.language)

    async def generate():
        try:
            # Сигнал старта
            yield "data: {\"type\": \"start\", \"message\": \"Агент начинает анализ...\"}\n\n"
            await asyncio.sleep(0.1)

            yield f"data: {{\"type\": \"status\", \"message\": \"Собираю данные о {body.company}...\"}}\n\n"
            await asyncio.sleep(0.1)

            # Запускаем агента в отдельном потоке чтобы не блокировать event loop
            loop = asyncio.get_event_loop()

            from backend.app.agents.agent import run_agent
            report = await loop.run_in_executor(
                None,
                lambda: run_agent(body.company, body.language)
            )

            # Стримим отчёт по чанкам
            chunk_size = 100
            for i in range(0, len(report), chunk_size):
                chunk = report[i:i + chunk_size]
                # Экранируем для JSON
                chunk_escaped = chunk.replace('"', '\\"').replace('\n', '\\n')
                yield f"data: {{\"type\": \"chunk\", \"content\": \"{chunk_escaped}\"}}\n\n"
                await asyncio.sleep(0.01)

            yield "data: {\"type\": \"done\", \"message\": \"Анализ завершён\"}\n\n"
            logger.info("chat_completed", company=body.company)

        except Exception as e:
            logger.error("chat_error", error=str(e), company=body.company)
            error_msg = str(e).replace('"', '\\"')
            yield f"data: {{\"type\": \"error\", \"message\": \"{error_msg}\"}}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        }
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.app.main:app", host="0.0.0.0", port=8000, reload=True)