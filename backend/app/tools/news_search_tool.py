import httpx
from langchain_core.tools import tool
from pydantic import BaseModel
from datetime import datetime, timedelta
import structlog
import os

logger = structlog.get_logger()

NEWS_API_URL = "https://newsapi.org/v2/everything"
SERP_API_URL = "https://serpapi.com/search"


class NewsArticle(BaseModel):
    title: str
    source: str
    published_at: str
    description: str
    url: str


class NewsResult(BaseModel):
    company: str
    articles: list[NewsArticle]
    total_found: int
    period_days: int
    error: str | None = None


def _search_newsapi(company: str, from_date: str, api_key: str) -> list[NewsArticle]:
    """Поиск через NewsAPI."""
    params = {
        "q": company,
        "from": from_date,
        "sortBy": "relevancy",
        "language": "en",
        "pageSize": 10,
        "apiKey": api_key,
    }
    with httpx.Client() as client:
        response = client.get(NEWS_API_URL, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

    articles = []
    for a in data.get("articles", []):
        articles.append(NewsArticle(
            title=a.get("title", ""),
            source=a.get("source", {}).get("name", ""),
            published_at=a.get("publishedAt", ""),
            description=a.get("description") or "",
            url=a.get("url", ""),
        ))
    return articles


def _search_serpapi(company: str, api_key: str) -> list[NewsArticle]:
    """Fallback поиск через SerpAPI если NewsAPI недоступен."""
    params = {
        "q": f"{company} news",
        "tbm": "nws",
        "api_key": api_key,
        "num": 10,
    }
    with httpx.Client() as client:
        response = client.get(SERP_API_URL, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

    articles = []
    for a in data.get("news_results", []):
        articles.append(NewsArticle(
            title=a.get("title", ""),
            source=a.get("source", ""),
            published_at=a.get("date", ""),
            description=a.get("snippet") or "",
            url=a.get("link", ""),
        ))
    return articles


@tool
def news_search_tool(company_name: str, period_days: int = 30) -> dict:
    """
    Ищет последние новости о компании-конкуренте.
    Если новостей мало — автоматически расширяет период поиска.
    Если NewsAPI недоступен — переключается на SerpAPI.

    Args:
        company_name: Название компании (например "Notion" или "Linear")
        period_days: За сколько дней искать новости (по умолчанию 30)

    Returns:
        Словарь со списком статей, количеством найденных и периодом поиска.
    """
    logger.info("news_search_started", company=company_name, period_days=period_days)

    news_api_key = os.getenv("NEWS_API_KEY")
    serp_api_key = os.getenv("SERP_API_KEY")

    if not news_api_key and not serp_api_key:
        return NewsResult(
            company=company_name,
            articles=[],
            total_found=0,
            period_days=period_days,
            error="Не задан ни NEWS_API_KEY, ни SERP_API_KEY в .env",
        ).model_dump()

    from_date = (datetime.now() - timedelta(days=period_days)).strftime("%Y-%m-%d")
    articles = []

    # Пробуем NewsAPI
    if news_api_key:
        try:
            articles = _search_newsapi(company_name, from_date, news_api_key)
            logger.info("newsapi_success", count=len(articles))
        except Exception as e:
            logger.warning("newsapi_failed", error=str(e))

    # Fallback на SerpAPI
    if not articles and serp_api_key:
        try:
            articles = _search_serpapi(company_name, serp_api_key)
            logger.info("serpapi_fallback_success", count=len(articles))
        except Exception as e:
            logger.warning("serpapi_failed", error=str(e))
            return NewsResult(
                company=company_name,
                articles=[],
                total_found=0,
                period_days=period_days,
                error=str(e),
            ).model_dump()

    # Мало новостей — агент должен перезвать с большим периодом
    if len(articles) < 3 and period_days < 90:
        logger.info("too_few_articles_extend_period", current=period_days)

    logger.info("news_search_done", company=company_name, found=len(articles))

    return NewsResult(
        company=company_name,
        articles=articles,
        total_found=len(articles),
        period_days=period_days,
    ).model_dump()