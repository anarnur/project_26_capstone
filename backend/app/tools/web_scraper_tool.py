import httpx
from bs4 import BeautifulSoup
from langchain_core.tools import tool
from pydantic import BaseModel, HttpUrl
import structlog

logger = structlog.get_logger()

SCRAPE_PAGES = ["", "/about", "/pricing", "/blog", "/product"]
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}


class ScrapeResult(BaseModel):
    url: str
    title: str
    description: str
    main_text: str
    pages_scraped: list[str]
    error: str | None = None


def _clean_text(soup: BeautifulSoup) -> str:
    """Убираем скрипты, стили и лишние пробелы."""
    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()
    return " ".join(soup.get_text(separator=" ").split())[:3000]


def _scrape_page(client: httpx.Client, url: str) -> str:
    """Парсим одну страницу, возвращаем чистый текст."""
    try:
        response = client.get(url, timeout=10, follow_redirects=True)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "lxml")
        return _clean_text(soup)
    except Exception as e:
        logger.warning("scrape_page_failed", url=url, error=str(e))
        return ""


def _get_meta(soup: BeautifulSoup) -> tuple[str, str]:
    """Извлекаем title и meta description."""
    title = soup.find("title")
    title_text = title.get_text(strip=True) if title else ""

    description = ""
    for attr in [{"name": "description"}, {"property": "og:description"}]:
        tag = soup.find("meta", attr)
        if tag and tag.get("content"):
            description = tag["content"]
            break

    return title_text, description


@tool
def web_scraper_tool(company_url: str) -> dict:
    """
    Парсит сайт компании-конкурента и извлекает ключевую информацию:
    название, описание, тексты с главных страниц.

    Args:
        company_url: URL сайта компании (например https://notion.so)

    Returns:
        Словарь с title, description, main_text и списком спарсенных страниц.
    """
    base_url = company_url.rstrip("/")
    logger.info("scraping_started", url=base_url)

    all_text_parts = []
    pages_scraped = []

    try:
        with httpx.Client(headers=HEADERS) as client:
            # Главная страница отдельно — берём meta теги
            response = client.get(base_url, timeout=10, follow_redirects=True)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "lxml")
            title, description = _get_meta(soup)
            main_text = _clean_text(soup)
            all_text_parts.append(main_text)
            pages_scraped.append(base_url)

            # Дополнительные страницы
            for path in SCRAPE_PAGES[1:]:
                url = base_url + path
                text = _scrape_page(client, url)
                if text:
                    all_text_parts.append(text)
                    pages_scraped.append(url)

        combined_text = " ".join(all_text_parts)[:6000]
        logger.info("scraping_done", pages=len(pages_scraped))

        return ScrapeResult(
            url=base_url,
            title=title,
            description=description,
            main_text=combined_text,
            pages_scraped=pages_scraped,
        ).model_dump()

    except httpx.HTTPStatusError as e:
        logger.error("scrape_http_error", status=e.response.status_code)
        return ScrapeResult(
            url=base_url,
            title="",
            description="",
            main_text="",
            pages_scraped=[],
            error=f"HTTP {e.response.status_code}: сайт недоступен",
        ).model_dump()

    except Exception as e:
        logger.error("scrape_failed", error=str(e))
        return ScrapeResult(
            url=base_url,
            title="",
            description="",
            main_text="",
            pages_scraped=[],
            error=str(e),
        ).model_dump()