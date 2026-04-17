# Progress Tracker

**✅ Backend files complete & fixed**
- Models, serializers, views (ORM fixed), urls
- Scraper (Selenium + webdriver_manager)
- AI services (Claude summaries/genre/sentiment)
- RAG (ChromaDB + sentence-transformers, Claude fixed)
- Settings (dotenv/MySQL/CORS/DRF, scraper app removed)

**✅ Frontend complete**
- React + Tailwind + Router + Axios
- Dashboard, Q&A, BookDetail (functions hoisted)

**🔄 Setup steps remaining:**

1. pip install -r requirements.txt
2. cp .env.example .env && edit (API key/DB)
3. cd backend && python manage.py makemigrations books && migrate
4. python manage.py runserver
5. cd ../frontend && npm install && npm start

**Verification:**
- POST /api/books/upload/ → scrape/AI/index
- POST /api/books/ask/ → RAG response
- Frontend all pages functional
