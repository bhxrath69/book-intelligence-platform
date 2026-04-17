# Book Intelligence Platform

A full-stack Document Intelligence platform for books with scraping, AI insights, and RAG search.

## Setup Instructions

### Backend
1. Install Python 3.11+
2. `pip install -r requirements.txt`
3. Copy `.env.example` to `.env` and fill values:
   ```
   cp .env.example .env
   # Edit .env with your Anthropic API key and MySQL credentials
   ```
4. Create MySQL database:
   ```sql
   CREATE DATABASE bookdb CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
   ```
5. Run migrations:
   ```bash
   cd backend
   python manage.py makemigrations books
   python manage.py migrate
   ```
6. Start server:
   ```bash
   python manage.py runserver
   ```

### Frontend
1. Install Node.js LTS
2. ```bash
   cd frontend
   npm install
   npm start
   ```

## API Documentation

- `GET /api/books/` — List all books (paginated)
- `GET /api/books/:id/` — Book detail
- `POST /api/books/upload/` — Scrape & process 5 pages of books.toscrape.com
- `POST /api/books/ask/` — RAG Q&A: `{"question": "..."}`
- `GET /api/books/:id/recommend/` — Similar book recommendations
- `GET /api/books/stats/` — Platform statistics

## Sample Questions and Answers

**Q: "What mystery books do you have?"**  
A: "Based on the collection, we have several mystery novels including 'Sharp Objects' by Gillian Flynn..."

**Q: "Recommend a mystery novel"**  
A: "For mystery fans, I recommend 'Sharp Objects' by Gillian Flynn - a psychological thriller..."

**Q: "Highest rated books?"**  
A: "The top rated books are those with 5★ ratings from books.toscrape.com..."

## Features

✅ Selenium scraping (headless Chrome)  
✅ Claude AI summaries, genre classification, sentiment  
✅ ChromaDB RAG pipeline with sentence-transformers  
✅ Full DRF APIs  
✅ React + Tailwind frontend  
✅ Responsive design  
✅ Real-time scraping status  
✅ Book recommendations  
✅ Chat history  

## Screenshots
[Add screenshots after running the app]

Visit [localhost:3000](http://localhost:3000) after starting both services!
