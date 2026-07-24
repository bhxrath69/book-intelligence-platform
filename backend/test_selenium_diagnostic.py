import platform
import sys
from pathlib import Path

from scraper.scrape import (
    ScraperSetupError,
    _resolve_valid_chromedriver_path,
    build_chrome_options,
    get_selenium_components,
)


def main():
    print("Python executable:", sys.executable)
    print("Python version:", sys.version)
    print("Architecture:", platform.architecture())

    try:
        webdriver_module, _, service_class, manager_class = get_selenium_components()
        options = build_chrome_options()
        raw_driver_path = manager_class().install()
        driver_path = _resolve_valid_chromedriver_path(raw_driver_path, options.binary_location)

        print("Chrome path:", options.binary_location)
        print("webdriver-manager driver path:", raw_driver_path)
        print("Validated driver path:", driver_path)
        print("Driver exists:", Path(driver_path).exists())

        driver = webdriver_module.Chrome(
            service=service_class(executable_path=driver_path),
            options=options,
        )
        try:
            driver.get("https://books.toscrape.com/")
            print("Page title:", driver.title)
        finally:
            driver.quit()
    except ScraperSetupError as exc:
        print("Scraper setup failed:", exc.message)
        print("Details:", exc.details)
        raise SystemExit(1)
    except Exception as exc:
        print("Diagnostic failed with exception:", repr(exc))
        raise SystemExit(1)


if __name__ == "__main__":
    main()
