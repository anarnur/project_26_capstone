# Market Intelligence Agent

> AI-ассистент для анализа конкурентов: сайт + новости + отзывы → SWOT-отчёт за 2 минуты.

## Live demo
_ссылка появится после деплоя_

## Быстрый старт
```bash
cp .env.example .env
docker-compose up
```

## Стек
- **Agent:** LangGraph
- **LLM:** Claude claude-sonnet-4-20250514
- **RAG:** Qdrant
- **Backend:** FastAPI + SSE
- **Frontend:** Next.js
- **Deploy:** Railway

## Структура проекта
```
backend/app/agents/   — логика агентов
backend/app/tools/    — кастомные инструменты
backend/app/rag/      — retrieval + chunking
frontend/app/         — Next.js страницы
docs/                 — proposal, архитектура, демо
```

## API
- `POST /chat` — запрос к агенту (SSE streaming)
- `GET /health` — статус сервиса

## Известные ограничения
- NewsAPI: 100 запросов/день на бесплатном тарифе
- Сайты с JS-рендерингом требуют Playwright
