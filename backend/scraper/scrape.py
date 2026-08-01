import importlib
import logging
import os
import platform
import shutil
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import urljoin

import requests

logger = logging.getLogger(__name__)

# Gutenberg ingestion (no selenium)
GUTENBERG_BASE_URL = "https://www.gutenberg.org"
DEFAULT_TIMEOUT_SECONDS = 30

# Fixed list of Gutenberg book IDs for stable indexing.
# You can add/remove IDs later without crawling.
GUTENBERG_BOOK_IDS = [
    1342,   # Pride and Prejudice
    84,     # The Adventures of Sherlock Holmes
    11,     # Alice's Adventures in Wonderland
    64317,  # (May vary) - fallback IDs can be replaced if needed
    98,     # A Tale of Two Cities
    1400,   # The Adventures of Tom Sawyer
    2600,   # The Complete Works of William Shakespeare
    1952,   # Treasure Island
    2701,   # The Thirty-Nine Steps
    408,    # The Three Musketeers
    105,    # Crime and Punishment
    144,    # Dracula
    46,     # Narrative of the Life of Frederick Douglass
    1661,   # Twenty Thousand Leagues Under the Seas
    74,     # The Hound of the Baskervilles (may not be at 74)
]



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


def run_scraper_self_check(base_url: str = GUTENBERG_BASE_URL + "/ebooks", verify_network: bool = True) -> Dict:
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


def get_selenium_wait_components():
    try:
        ui_module = importlib.import_module("selenium.webdriver.support.ui")
        by_module = importlib.import_module("selenium.webdriver.common.by")
        exceptions_module = importlib.import_module("selenium.common.exceptions")
    except Exception as exc:
        raise ScraperSetupError(
            f"WebDriver wait setup failed: {exc}",
            details={"import_error": str(exc), "stage": "webdriver_wait_setup"},
            status_code=500,
        ) from exc

    return ui_module.WebDriverWait, by_module.By, exceptions_module.TimeoutException


def _raise_stage_error(stage: str, details: str, extra: Optional[Dict] = None, status_code: int = 500):
    payload = {"stage": stage, "details": details}
    if extra:
        payload.update(extra)
    raise ScraperSetupError("Scraping failed", details=payload, status_code=status_code)


def get_beautifulsoup_class():
    try:
        bs4_module = importlib.import_module("bs4")
        return bs4_module.BeautifulSoup
    except Exception as exc:
        raise ScraperSetupError(
            f"Scraper parsing dependency missing: {exc}",
            details={"import_error": str(exc), "missing_dependency": "beautifulsoup4"},
            status_code=500,
        ) from exc


def build_chrome_options():
    webdriver_module, _, _, _ = get_selenium_components()
    options = webdriver_module.ChromeOptions()
    options.binary_location = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
    options.add_argument("--headless=new")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    return options


def _driver_debug_info(driver_path: Optional[str], chrome_path: str) -> Dict:
    path_obj = Path(driver_path) if driver_path else None
    exists = bool(path_obj and path_obj.exists())
    size = path_obj.stat().st_size if exists else None
    info = {
        "python_executable": sys.executable,
        "python_version": sys.version,
        "architecture": platform.architecture(),
        "chrome_binary": chrome_path,
        "driver_path": driver_path,
        "driver_path_endswith_exe": bool(driver_path and driver_path.lower().endswith("chromedriver.exe")),
        "driver_path_exists": exists,
        "driver_file_size": size,
    }
    print("Python executable:", info["python_executable"])
    print("Python version:", info["python_version"])
    print("Architecture:", info["architecture"])
    print("Chrome binary:", info["chrome_binary"])
    print("Driver path from webdriver-manager:", info["driver_path"])
    print("Driver path ends with chromedriver.exe:", info["driver_path_endswith_exe"])
    print("Driver path exists:", info["driver_path_exists"])
    print("Driver file size:", info["driver_file_size"])
    logger.info("Selenium debug info: %s", info)
    return info


def _resolve_valid_chromedriver_path(raw_driver_path: str, chrome_path: str) -> str:
    debug_info = _driver_debug_info(raw_driver_path, chrome_path)

    if not raw_driver_path:
        raise ScraperSetupError(
            "WebDriver setup failed: webdriver-manager returned an empty path",
            details=debug_info,
            status_code=500,
        )

    candidate = Path(raw_driver_path)
    if candidate.exists() and candidate.name.lower() == "chromedriver.exe":
        return str(candidate)

    search_root = candidate if candidate.is_dir() else candidate.parent
    fallback = search_root / "chromedriver.exe"
    if fallback.exists():
        fallback_info = _driver_debug_info(str(fallback), chrome_path)
        logger.warning(
            "webdriver-manager returned invalid driver path '%s'; using '%s' instead",
            raw_driver_path,
            fallback,
        )
        return str(fallback)

    discovered = list(search_root.rglob("chromedriver.exe")) if search_root.exists() else []
    if discovered:
        corrected = str(discovered[0])
        _driver_debug_info(corrected, chrome_path)
        logger.warning(
            "webdriver-manager returned invalid driver path '%s'; discovered '%s' instead",
            raw_driver_path,
            corrected,
        )
        return corrected

    raise ScraperSetupError(
        f"WebDriver setup failed: webdriver-manager returned invalid driver path: {raw_driver_path}",
        details=debug_info,
        status_code=500,
    )


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
    chrome_path = r"C:\Program Files\Google\Chrome\Application\chrome.exe"

    try:
        raw_driver_path = manager_class().install()
        driver_path = _resolve_valid_chromedriver_path(raw_driver_path, chrome_path)
        driver = webdriver_module.Chrome(
            service=service_class(executable_path=driver_path),
            options=build_chrome_options(),
        )
        driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
            "source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        })
        return driver
    except Exception as exc:
        raise ScraperSetupError(
            f"Chrome could not be launched: {exc}",
            details={**check, "chrome_path": chrome_path},
            status_code=500,
        ) from exc


def parse_book_tile(tile, driver, page_number: int) -> Optional[Dict]:
    BeautifulSoup = get_beautifulsoup_class()
    logger.info("Stage parse: parsing tile on page %s", page_number)
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
    logger.info("Stage parse: requesting detail page %s", book_url)

    rating_elem = tile.find("p", class_="star-rating")
    rating_classes = rating_elem.get("class", []) if rating_elem else []
    rating_class = rating_classes[1] if len(rating_classes) > 1 else None
    rating_map = {"One": 1, "Two": 2, "Three": 3, "Four": 4, "Five": 5}
    rating = rating_map.get(rating_class, 0)

    driver.get(book_url)
    logger.debug("Page loaded: %s", book_url)
    time.sleep(0.5)
    detail_page_source = driver.page_source
    logger.info("Stage parse: detail page loaded for '%s', page_source length=%s", title, len(detail_page_source))
    detail_soup = BeautifulSoup(detail_page_source, "html.parser")

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


def _gutenberg_plain_text_url(book_id: int) -> str:
    # Gutenberg predictable plain text URL pattern
    return f"{GUTENBERG_BASE_URL}/files/{book_id}/{book_id}-0.txt"


def _clean_gutenberg_text(raw: str) -> str:
    # Basic cleanup: remove Gutenberg header/footer markers when possible.
    text = raw.replace("\r\n", "\n").strip()
    start_marker = "*** START OF THIS PROJECT GUTENBERG EBOOK"
    end_marker = "*** END OF THIS PROJECT GUTENBERG EBOOK"

    if start_marker in text:
        text = text.split(start_marker, 1)[1]
    if end_marker in text:
        text = text.split(end_marker, 1)[0]

    # Collapse excessive whitespace
    lines = [ln.strip() for ln in text.splitlines()]
    text = "\n".join([ln for ln in lines if ln])
    return text.strip()


def scrape_books(max_pages: int = 10) -> List[Dict]:
    # max_pages kept for backward compatibility with views.upload().
    # For Gutenberg fixed list we ignore max_pages.
    logger.info("Gutenberg scrape started: ids=%s", len(GUTENBERG_BOOK_IDS))
    books: List[Dict] = []

    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125 Safari/537.36"
    })

    for book_id in GUTENBERG_BOOK_IDS:
        plain_url = _gutenberg_plain_text_url(book_id)
        book_page_url = f"{GUTENBERG_BASE_URL}/ebooks/{book_id}"
        try:
            logger.info("Fetching Gutenberg text: id=%s url=%s", book_id, plain_url)
            r = session.get(plain_url, timeout=DEFAULT_TIMEOUT_SECONDS)
            r.raise_for_status()
            raw_text = r.text

            cleaned = _clean_gutenberg_text(raw_text)
            if len(cleaned) < 500:
                logger.warning("Skipping Gutenberg book %s: cleaned text too small (%s chars)", book_id, len(cleaned))
                continue

            # Title/author parsing from Gutenberg header (best-effort)
            # The first non-empty lines usually contain title/author.
            header_lines = [ln.strip() for ln in raw_text.splitlines()[:60] if ln.strip()]
            title = ""
            author = ""
            for ln in header_lines:
                if ln.lower().startswith("title:"):
                    title = ln.split(":", 1)[1].strip()
                if ln.lower().startswith("author:"):
                    author = ln.split(":", 1)[1].strip()

            if not title:
                # Fallback: first line with alphabetic characters
                for ln in header_lines:
                    if any(ch.isalpha() for ch in ln) and len(ln) > 3:
                        title = ln[:200]
                        break
            if not author:
                author = "Unknown"

            books.append({
                "title": title or f"Gutenberg Book {book_id}",
                "author": author,
                "rating": None,
                "num_reviews": 0,
                "description": "",
                "book_url": book_page_url,
                "cover_image_url": "",
                "genre": "",
                "summary": "",
                "sentiment": "",
                "full_text": cleaned,
                "is_processed": False,
            })
        except Exception as exc:
            logger.warning("Skipping Gutenberg id=%s due to error: %s", book_id, exc)
            continue

    logger.info("Gutenberg scrape completed: books=%s", len(books))
    if not books:
        raise ScraperSetupError(
            "Gutenberg scrape produced no books",
            details={"book_ids": GUTENBERG_BOOK_IDS},
            status_code=502,
        )

    return books
def search_gutenberg(query: str, max_results: int = 5) -> list:
    """Search Gutendex API for books matching a title/author query."""
    try:
        response = requests.get(
            "https://gutendex.com/books",
            params={"search": query},
            timeout=15
        )
        response.raise_for_status()
        data = response.json()
        results = []
        for book in data.get("results", [])[:max_results]:
            text_url = None
            for fmt, url in book.get("formats", {}).items():
                if "text/plain" in fmt:
                    text_url = url
                    break
            if text_url:
                results.append({
                    "gutenberg_id": book["id"],
                    "title": book["title"],
                    "author": book["authors"][0]["name"] if book.get("authors") else "Unknown",
                    "text_url": text_url,
                })
        return results
    except Exception as exc:
        logger.warning("Gutendex search failed: %s", exc)
        return []

def search_gutenberg(query: str, max_results: int = 5) -> list:
    """Search Gutendex API for books matching a title/author query across all 70,000+ Gutenberg books."""
    try:
        response = requests.get(
            "https://gutendex.com/books",
            params={"search": query},
            timeout=15
        )
        response.raise_for_status()
        data = response.json()
        results = []
        for book in data.get("results", [])[:max_results]:
            text_url = None
            for fmt, url in book.get("formats", {}).items():
                if "text/plain" in fmt:
                    text_url = url
                    break
            if text_url:
                results.append({
                    "gutenberg_id": book["id"],
                    "title": book["title"],
                    "author": book["authors"][0]["name"] if book.get("authors") else "Unknown",
                    "text_url": text_url,
                })
        return results
    except Exception as exc:
        logger.warning("Gutendex search failed: %s", exc)
        return []


def download_book_by_search_result(result: dict) -> dict:
    """Download full text for a single Gutendex search result."""
    try:
        response = requests.get(result["text_url"], timeout=30)
        response.raise_for_status()
        full_text = response.text

        return {
            "title": result["title"],
            "author": result["author"],
            "book_url": f"https://www.gutenberg.org/ebooks/{result['gutenberg_id']}",
            "description": "",
            "rating": None,
            "num_reviews": 0,
            "cover_image_url": "",
            "full_text": full_text,
        }
    except Exception as exc:
        logger.warning("Download failed for %s: %s", result["title"], exc)
        return None


def download_book_by_search_result(result: dict) -> dict:
    """Download full text for a single Gutendex search result."""
    try:
        response = requests.get(result["text_url"], timeout=30)
        response.raise_for_status()
        full_text = response.text

        return {
            "title": result["title"],
            "author": result["author"],
            "book_url": f"https://www.gutenberg.org/ebooks/{result['gutenberg_id']}",
            "description": "",
            "rating": None,
            "num_reviews": 0,
            "cover_image_url": "",
            "full_text": full_text,
        }
    except Exception as exc:
        logger.warning("Download failed for %s: %s", result["title"], exc)
        return None

