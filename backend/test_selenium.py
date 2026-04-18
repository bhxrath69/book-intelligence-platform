from scraper.scrape import ScraperSetupError, create_webdriver


def main():
    driver = None
    try:
        driver = create_webdriver()
        driver.get("https://books.toscrape.com/")
        print("Browser launch OK")
        print(f"Page title: {driver.title}")
    except ScraperSetupError as exc:
        print(f"Scraper setup failed: {exc.message}")
        if exc.details:
            print(f"Details: {exc.details}")
        raise SystemExit(1)
    except Exception as exc:
        print(f"Unexpected Selenium test failure: {exc}")
        raise SystemExit(1)
    finally:
        if driver:
            driver.quit()


if __name__ == "__main__":
    main()
