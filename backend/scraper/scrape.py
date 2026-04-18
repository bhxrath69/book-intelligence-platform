import importlib
import logging
import os
import shutil
import time
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

SCRAPE_BASE_URL = "https://books.toscrape.com/"
DEFAULT_TIMEOUT_SECONDS = 15


class ScraperSetupError(Exception):
    def __init__(self, message: str, details: Optional[Dict] = None, status_code: int = 500):
        super().__init__(message)
        self.message = message
        self.details = details or {}
        self.status_code = status_code


def find_chrome_binary() -> Optional[str]:
    env_candidates = [
        os.getenv("GOOGLE_CHROME_BIN"),
        os.getenv("CHROME_BINARY"),
        os.getenv("CHROME_BIN"),
    ]
    path_candidates = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        str(Path.home() / "AppData" / "Local" / "Google" / "Chrome" / "Application" / "chrome.exe"),
    ]
    which_candidates = [
        shutil.which("chrome"),
        shutil.which("chrome.exe"),
        shutil.which("google-chrome"),
        shutil.which("msedge"),
    ]

    for candidate in env_candidates + path_candidates + which_candidates:
        if candidate and Path(candidate).exists():
            return str(candidate)
    return None


def run_scraper_self_check(base_url: str = SCRAPE_BASE_URL, verify_network: bool = True) -> Dict:
    logger.info("Scraper dependency check started")

    result = {
        "ok": True,
        "errors": [],
        "warnings": [],
        "chrome_path": None,
        "network_ok": None,
    }

    for module_name in ("selenium", "webdriver_manager.chrome"):
        try:
            importlib.import_module(module_name)
        except Exception as exc:
            result["errors"].append(f"Missing dependency: {module_name} ({exc})")

    chrome_path = find_chrome_binary()
    if chrome_path:
        result["chrome_path"] = chrome_path
    else:
        result["errors"].append(
            "Google Chrome not found. Install Chrome or set GOOGLE_CHROME_BIN to chrome.exe."
        )

    if verify_network:
        try:
            response = requests.get(base_url, timeout=DEFAULT_TIMEOUT_SECONDS)
            response.raise_for_status()
            result["network_ok"] = True
        except requests.RequestException as exc:
            result["network_ok"] = False
            result["errors"].append(f"Network access failed: {exc}")

    result["ok"] = len(result["errors"]) == 0
    logger.info("Scraper dependency check result: ok=%s", result["ok"])
    return result


def get_selenium_components():
    try:
        webdriver_module = importlib.import_module("selenium.webdriver")
        exceptions_module = importlib.import_module("selenium.common.exceptions")
        service_module = importlib.import_module("selenium.webdriver.chrome.service")
        manager_module = importlib.import_module("webdriver_manager.chrome")
    except Exception as exc:
        raise ScraperSetupError(
            f"WebDriver setup failed: {exc}",
            details={"import_error": str(exc)},
            status_code=500,
        ) from exc

    return (
        webdriver_module,
        exceptions_module.WebDriverException,
        service_module.Service,
        manager_module.ChromeDriverManager,
    )


def build_chrome_options():
    webdriver_module, _, _, _ = get_selenium_components()
    options = webdriver_module.ChromeOptions()
    options.binary_location = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    return options


def create_webdriver():
    check = run_scraper_self_check()
    if not check["ok"]:
        raise ScraperSetupError(
            "WebDriver setup failed",
            details=check,
            status_code=500,
        )

    logger.info("Launching browser")
    print("Launching Chrome via Selenium...")

    webdriver_module, _, service_class, manager_class = get_selenium_components()

    try:
        driver = webdriver_module.Chrome(
            service=service_class(manager_class().install()),
            options=build_chrome_options(),
        )
        return driver
    except Exception as exc:
        raise ScraperSetupError(
            f"Chrome could not be launched: {exc}",
            details={**check, "chrome_path": r"C:\Program Files\Google\Chrome\Application\chrome.exe"},
            status_code=500,
        ) from exc


def parse_book_tile(tile, driver, page_number: int) -> Optional[Dict]:
    title_container = tile.find("h3")
    title_elem = title_container.find("a") if title_container else None
    if not title_elem:
        logger.warning("Skipping book tile without title link on page %s", page_number)
        return None

    title = title_elem.get("title") or title_elem.get_text(strip=True)
    relative_url = title_elem.get("href")
    if not relative_url:
        logger.warning("Skipping book tile without href for title '%s' on page %s", title, page_number)
        return None

    book_url = urljoin(SCRAPE_BASE_URL + "catalogue/", relative_url)

    rating_elem = tile.find("p", class_="star-rating")
    rating_classes = rating_elem.get("class", []) if rating_elem else []
    rating_class = rating_classes[1] if len(rating_classes) > 1 else None
    rating_map = {"One": 1, "Two": 2, "Three": 3, "Four": 4, "Five": 5}
    rating = rating_map.get(rating_class, 0)

    driver.get(book_url)
    logger.debug("Page loaded: %s", book_url)
    time.sleep(0.5)
    detail_soup = BeautifulSoup(driver.page_source, "html.parser")

    author = "Unknown"
    author_elem = detail_soup.find("h3")
    if author_elem and author_elem.find("a"):
        author = author_elem.find("a").get_text(strip=True)

    description = ""
    desc_elem = detail_soup.find("div", id="product_description")
    if desc_elem:
        desc_paragraph = desc_elem.find_next_sibling("p") or desc_elem.find("p")
        if desc_paragraph:
            description = desc_paragraph.get_text(strip=True)

    num_reviews = 0
    details_table = detail_soup.find("table", class_="table-striped")
    if details_table:
        for row in details_table.find_all("tr"):
            header = row.find("th")
            value_cell = row.find("td")
            if header and value_cell and header.get_text(strip=True) == "No. reviews":
                try:
                    num_reviews = int(value_cell.get_text(strip=True))
                except ValueError:
                    logger.warning("Invalid review count for '%s': %s", title, value_cell.get_text(strip=True))
                break

    cover_img = detail_soup.find("img", class_="thumbnail")
    cover_image_url = ""
    if cover_img and cover_img.get("src"):
        cover_image_url = urljoin(SCRAPE_BASE_URL, cover_img["src"].replace("../../", ""))

    return {
        "title": title,
        "author": author,
        "rating": rating,
        "num_reviews": num_reviews,
        "description": description,
        "book_url": book_url,
        "cover_image_url": cover_image_url,
    }


def scrape_books(max_pages: int = 10) -> List[Dict]:
    logger.info("Scraper started with max_pages=%s", max_pages)
    driver = None
    books: List[Dict] = []

    try:
        driver = create_webdriver()
        _, web_driver_exception, _, _ = get_selenium_components()

        for page in range(1, max_pages + 1):
            try:
                page_path = f"catalogue/page-{page}.html" if page > 1 else "catalogue/"
                url = urljoin(SCRAPE_BASE_URL, page_path)
                driver.get(url)
                logger.info("Page loaded: %s", url)
                time.sleep(0.5)

                soup = BeautifulSoup(driver.page_source, "html.parser")
                book_tiles = soup.find_all("article", class_="product_pod")
                logger.info("Found %s tiles on page %s", len(book_tiles), page)

                for tile in book_tiles:
                    try:
                        book_data = parse_book_tile(tile, driver, page)
                        if book_data:
                            books.append(book_data)
                    except Exception as exc:
                        logger.warning("Skipping malformed book tile on page %s: %s", page, exc)
                        continue
            except requests.RequestException as exc:
                logger.error("Network access failed on page %s: %s", page, exc)
                raise ScraperSetupError(
                    f"Network access failed: {exc}",
                    details={"page": page, "url": url},
                    status_code=502,
                ) from exc
            except web_driver_exception as exc:
                logger.error("Chrome could not be launched or navigated on page %s: %s", page, exc)
                raise ScraperSetupError(
                    f"Chrome could not be launched: {exc}",
                    details={"page": page, "url": url},
                    status_code=500,
                ) from exc
            except Exception as exc:
                logger.warning("Error on page %s: %s", page, exc)
                continue

        logger.info("Scrape completed with %s books", len(books))
        return books
    except ScraperSetupError:
        logger.exception("Scraper failed with a setup/runtime error")
        raise
    except Exception as exc:
        logger.exception("Scraper failed with reason: %s", exc)
        raise ScraperSetupError(
            f"Scraper failed: {exc}",
            details={"exception_type": type(exc).__name__},
            status_code=500,
        ) from exc
    finally:
        if driver:
            driver.quit()
