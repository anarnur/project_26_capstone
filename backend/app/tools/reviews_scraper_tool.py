import httpx
from bs4 import BeautifulSoup
from langchain_core.tools import tool
from pydantic import BaseModel
import structlog

logger = structlog.get_logger()

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}


class Review(BaseModel):
    source: str
    rating: float | None
    title: str
    body: str


class ReviewsResult(BaseModel):
    company: str
    reviews: list[Review]
    average_rating: float | None
    total_found: int
    sources_checked: list[str]
    error: str | None = None


def _scrape_g2(company_slug: str) -> list[Review]:
    """Парсим отзывы с G2."""
    url = f"https://www.g2.com/products/{company_slug}/reviews"
    reviews = []
    try:
        with httpx.Client(headers=HEADERS) as client:
            response = client.get(url, timeout=10, follow_redirects=True)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "lxml")

            for card in soup.select(".review-card")[:10]:
                title_tag = card.select_one(".review-card__title")
                body_tag = card.select_one(".review-card__body, .review-card__snip")
                rating_tag = card.select_one("[data-rating]")

                title = title_tag.get_text(strip=True) if title_tag else ""
                body = body_tag.get_text(strip=True) if body_tag else ""
                rating = float(rating_tag["data-rating"]) if rating_tag else None

                if title or body:
                    reviews.append(Review(
                        source="G2",
                        rating=rating,
                        title=title,
                        body=body[:500],
                    ))
    except Exception as e:
        logger.warning("g2_scrape_failed", error=str(e))
    return reviews


def _scrape_trustpilot(company_slug: str) -> list[Review]:
    """Парсим отзывы с Trustpilot."""
    url = f"https://www.trustpilot.com/review/{company_slug}"
    reviews = []
    try:
        with httpx.Client(headers=HEADERS) as client:
            response = client.get(url, timeout=10, follow_redirects=True)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "lxml")

            for card in soup.select("[data-service-review-card-paper]")[:10]:
                title_tag = card.select_one("h2[data-service-review-title-typography]")
                body_tag = card.select_one("p[data-service-review-text-typography]")
                rating_tag = card.select_one("[data-service-review-rating]")

                title = title_tag.get_text(strip=True) if title_tag else ""
                body = body_tag.get_text(strip=True) if body_tag else ""

                rating = None
                if rating_tag:
                    stars = rating_tag.get("data-service-review-rating")
                    try:
                        rating = float(stars)
                    except (TypeError, ValueError):
                        pass

                if title or body:
                    reviews.append(Review(
                        source="Trustpilot",
                        rating=rating,
                        title=title,
                        body=body[:500],
                    ))
    except Exception as e:
        logger.warning("trustpilot_scrape_failed", error=str(e))
    return reviews


def _average_rating(reviews: list[Review]) -> float | None:
    rated = [r.rating for r in reviews if r.rating is not None]
    if not rated:
        return None
    return round(sum(rated) / len(rated), 2)


def _guess_slug(company_name: str) -> str:
    """Простая нормализация имени в slug."""
    return company_name.lower().replace(" ", "-")


@tool
def reviews_scraper_tool(company_name: str, company_slug: str = "") -> dict:
    """
    Собирает отзывы о компании с G2 и Trustpilot.
    Возвращает список отзывов, средний рейтинг и источники.

    Args:
        company_name: Название компании (например "Notion")
        company_slug: Slug компании на платформах (например "notion" или "notion.so").
                      Если не указан — угадывается автоматически.

    Returns:
        Словарь с отзывами, средним рейтингом и источниками.
    """
    slug = company_slug or _guess_slug(company_name)
    logger.info("reviews_scrape_started", company=company_name, slug=slug)

    all_reviews: list[Review] = []
    sources_checked = []

    g2_reviews = _scrape_g2(slug)
    sources_checked.append("G2")
    all_reviews.extend(g2_reviews)
    logger.info("g2_done", count=len(g2_reviews))

    tp_reviews = _scrape_trustpilot(slug)
    sources_checked.append("Trustpilot")
    all_reviews.extend(tp_reviews)
    logger.info("trustpilot_done", count=len(tp_reviews))

    avg = _average_rating(all_reviews)
    logger.info("reviews_done", total=len(all_reviews), avg_rating=avg)

    return ReviewsResult(
        company=company_name,
        reviews=[r.model_dump() for r in all_reviews],
        average_rating=avg,
        total_found=len(all_reviews),
        sources_checked=sources_checked,
    ).model_dump()