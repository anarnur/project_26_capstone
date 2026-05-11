import httpx
from langchain_core.tools import tool
from pydantic import BaseModel
import structlog
import os

logger = structlog.get_logger()

REDDIT_SEARCH_URL = "https://www.reddit.com/search.json"
HEADERS = {
    "User-Agent": "MarketIntelligenceAgent/1.0 (research tool)"
}


class RedditPost(BaseModel):
    title: str
    subreddit: str
    score: int
    body: str
    url: str
    num_comments: int


class RedditResult(BaseModel):
    company: str
    posts: list[RedditPost]
    total_found: int
    error: str | None = None


@tool
def reddit_search_tool(company_name: str, limit: int = 10) -> dict:
    """
    Ищет отзывы и обсуждения о компании на Reddit.
    Не требует API ключа — использует публичный JSON endpoint.

    Args:
        company_name: Название компании (например "Notion")
        limit: Максимальное количество постов (по умолчанию 10)

    Returns:
        Словарь со списком постов, оценками и ссылками.
    """
    logger.info("reddit_search_started", company=company_name)

    queries = [
        f"{company_name} review",
        f"{company_name} alternatives",
        f"{company_name} experience",
    ]

    all_posts: list[RedditPost] = []
    seen_urls: set[str] = set()

    with httpx.Client(headers=HEADERS) as client:
        for query in queries:
            try:
                params = {
                    "q": query,
                    "sort": "relevance",
                    "limit": limit,
                    "type": "link",
                }
                response = client.get(
                    REDDIT_SEARCH_URL,
                    params=params,
                    timeout=10,
                    follow_redirects=True,
                )
                response.raise_for_status()
                data = response.json()

                for post in data.get("data", {}).get("children", []):
                    p = post.get("data", {})
                    url = p.get("url", "")

                    if url in seen_urls:
                        continue
                    seen_urls.add(url)

                    body = p.get("selftext", "") or p.get("title", "")
                    all_posts.append(RedditPost(
                        title=p.get("title", ""),
                        subreddit=p.get("subreddit", ""),
                        score=p.get("score", 0),
                        body=body[:500],
                        url=f"https://reddit.com{p.get('permalink', '')}",
                        num_comments=p.get("num_comments", 0),
                    ))

            except Exception as e:
                logger.warning("reddit_query_failed", query=query, error=str(e))
                continue

    # Сортируем по score — самые популярные обсуждения первыми
    all_posts.sort(key=lambda x: x.score, reverse=True)
    top_posts = all_posts[:limit]

    logger.info("reddit_search_done", company=company_name, found=len(top_posts))

    return RedditResult(
        company=company_name,
        posts=[p.model_dump() for p in top_posts],
        total_found=len(top_posts),
    ).model_dump()