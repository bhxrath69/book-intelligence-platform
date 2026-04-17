import time
import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
from typing import List, Dict

def scrape_books(max_pages: int = 10) -> List[Dict]:
    options = Options()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    
    driver = None
    try:
        # Try webdriver_manager first
        try:
            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=options)
        except:
            # Fallback
            driver = webdriver.Chrome(options=options)
        
        books = []
        base_url = 'http://books.toscrape.com/'
        
        for page in range(1, max_pages + 1):
            try:
                url = f'{base_url}catalogue/page-{page}.html' if page > 1 else f'{base_url}catalogue/'
                driver.get(url)
                time.sleep(0.5)
                
                soup = BeautifulSoup(driver.page_source, 'html.parser')
                book_tiles = soup.find_all('article', class_='product_pod')
                
                for tile in book_tiles:
                    try:
                        title_elem = tile.h3.a
                        title = title_elem['title']
                        relative_url = title_elem['href']
                        book_url = base_url + relative_url.replace('../../../', '')
                        
                        # Rating
                        rating_class = tile.find('p', class_='star-rating')['class'][1]
                        rating_map = {'One': 1, 'Two': 2, 'Three': 3, 'Four': 4, 'Five': 5}
                        rating = rating_map.get(rating_class, 0)
                        
                        # Detail page
                        driver.get(book_url)
                        time.sleep(0.5)
                        detail_soup = BeautifulSoup(driver.page_source, 'html.parser')
                        
                        author = 'Unknown'
                        author_elem = detail_soup.find('h3')
                        if author_elem:
                            author = author_elem.a.text
                        
                        description = ''
                        desc_elem = detail_soup.find('div', id='product_description')
                        if desc_elem and desc_elem.find('p'):
                            description = desc_elem.find('p').text.strip()
                        
                        num_reviews_elem = detail_soup.find('table', class_='table-striped').find('tr', string='No. reviews')
                        num_reviews = 0
                        if num_reviews_elem:
                            num_reviews = int(num_reviews_elem.find('td').text)
                        
                        cover_img = detail_soup.find('img', class_='thumbnail')
                        cover_image_url = ''
                        if cover_img:
                            cover_image_url = 'http://books.toscrape.com/' + cover_img['src'].replace('../../', '')
                        
                        books.append({
                            'title': title,
                            'author': author,
                            'rating': rating,
                            'num_reviews': num_reviews,
                            'description': description,
                            'book_url': book_url,
                            'cover_image_url': cover_image_url
                        })
                        
                    except Exception as e:
                        print(f"Error scraping book tile: {e}")
                        continue
                
            except Exception as e:
                print(f"Error on page {page}: {e}")
                continue
        
        return books
    
    except Exception as e:
        print(f"Scraper error: {e}")
        return []
    
    finally:
        if driver:
            driver.quit()
