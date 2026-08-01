from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from django.db.models import Count, Avg
from django.db import DatabaseError, IntegrityError, transaction
import logging
from .models import Book
from .serializers import BookSerializer
from scraper.scrape import ScraperSetupError, run_scraper_self_check, scrape_books
from .ai_service import generate_summary, classify_genre, analyze_sentiment
from .rag_service import index_book, rag_query

logger = logging.getLogger(__name__)

class BookViewSet(viewsets.ModelViewSet):
    queryset = Book.objects.all()
    serializer_class = BookSerializer
    permission_classes = [AllowAny]
    pagination_class = None

    def get_serializer_class(self):
        if self.action == 'list':
            from .serializers import BookListSerializer
            return BookListSerializer
        return BookSerializer

    @action(detail=False, methods=['post'], url_path='upload')
    def upload(self, request):
        logger.info("Stage upload_entered: method=%s content_type=%s", request.method, request.content_type)
        try:
            logger.info("Stage scrape_started: invoking scrape_books")
            scraped_books = scrape_books(max_pages=5)
            logger.info("Stage scrape_completed: scraped_count=%s", len(scraped_books))
            if not scraped_books:
                return Response({
                    'success': False,
                    'stage': 'scrape',
                    'new_books': 0,
                    'skipped': 0,
                    'total_scraped': 0,
                    'error': 'Scraping failed',
                    'details': 'No books were scraped. Check scraper/browser configuration or seed sample data.',
                    'errors': ['No books were scraped. Check scraper/browser configuration or seed sample data.']
                }, status=status.HTTP_503_SERVICE_UNAVAILABLE)

            new_count = 0
            skipped_count = 0
            errors = []
            indexed_count = 0
            logger.info("Stage records_prepared: preview=%s", scraped_books[:2])
            
            for book_data in scraped_books:
                try:
                    logger.info("Stage record_save_attempt: book_url=%s title=%s", book_data.get('book_url'), book_data.get('title'))
                    with transaction.atomic():
                        book, created = Book.objects.get_or_create(
                            book_url=book_data['book_url'],
                            defaults=book_data
                        )
                        
                        if not created and book.is_processed:
                            skipped_count += 1
                            continue
                        
                        book.title = book_data.get('title', book.title)
                        book.author = book_data.get('author', book.author)
                        book.rating = book_data.get('rating')
                        book.num_reviews = book_data.get('num_reviews', 0)
                        book.description = book_data.get('description', '')
                        book.cover_image_url = book_data.get('cover_image_url', '')
                        
                        book.summary = generate_summary(book.title, book.description)
                        book.genre = classify_genre(book.title, book.description)
                        book.sentiment = analyze_sentiment(book.description)
                        book.is_processed = True
                        book.save()

                    new_count += 1
                    logger.info("Stage record_saved: id=%s title=%s created=%s saved_count=%s", book.id, book.title, created, new_count)

                    if index_book(book):
                        indexed_count += 1
                    else:
                        errors.append(f"Saved {book.title}, but indexing failed.")
                        logger.warning("Stage record_index_warning: title=%s", book.title)

                except IntegrityError as e:
                    logger.exception("Stage db_integrity_error: title=%s error=%s", book_data.get('title', 'unknown'), e)
                    errors.append(f"Database integrity error for {book_data.get('title', 'unknown')}: {str(e)}")
                except DatabaseError as e:
                    logger.exception("Stage db_error: title=%s error=%s", book_data.get('title', 'unknown'), e)
                    errors.append(f"Database error for {book_data.get('title', 'unknown')}: {str(e)}")
                except Exception as e:
                    logger.exception("Stage record_processing_failed: title=%s error=%s", book_data.get('title', 'unknown'), e)
                    errors.append(f"Error processing {book_data.get('title', 'unknown')}: {str(e)}")
            
            logger.info(
                "Stage response_returned: saved=%s skipped=%s indexed=%s total_scraped=%s errors=%s",
                new_count,
                skipped_count,
                indexed_count,
                len(scraped_books),
                len(errors),
            )
            return Response({
                'success': new_count > 0 or skipped_count > 0,
                'new_books': new_count,
                'indexed_books': indexed_count,
                'skipped': skipped_count,
                'total_scraped': len(scraped_books),
                'errors': errors
            }, status=status.HTTP_200_OK if new_count > 0 or skipped_count > 0 else status.HTTP_500_INTERNAL_SERVER_ERROR)
        except ScraperSetupError as e:
            logger.exception("Stage upload_scraper_failed: details=%s", e.details)
            return Response({
                'success': False,
                'error': e.message,
                'stage': e.details.get('stage', 'scrape') if isinstance(e.details, dict) else 'scrape',
                'details': e.details,
            }, status=e.status_code)
        except Exception as e:
            logger.exception("Stage upload_failed_unexpectedly: %s", e)
            return Response({
                'success': False,
                'error': 'Scraping failed',
                'stage': 'upload',
                'details': str(e),
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'], url_path='scraper-check')
    def scraper_check(self, request):
        result = run_scraper_self_check()
        status_code = status.HTTP_200_OK if result['ok'] else status.HTTP_500_INTERNAL_SERVER_ERROR
        return Response(result, status=status_code)

    @action(detail=False, methods=['post'], url_path='ask')
    def ask(self, request):
        question = request.data.get('question', '').strip()
        if not question:
            return Response({'error': 'Question required'}, status=status.HTTP_400_BAD_REQUEST)
        
        result = rag_query(question)
        return Response(result)

    @action(detail=True, methods=['get'], url_path='recommend')
    def recommend(self, request, pk=None):
        try:
            book = Book.objects.get(pk=pk)
            recs = list(Book.objects.filter(
                genre=book.genre
            ).exclude(pk=pk).order_by('-rating')[:3])
            
            if len(recs) < 3:
                recs.extend(Book.objects.filter(
                    author=book.author
                ).exclude(
                    pk=pk
                ).exclude(
                    pk__in=[rec.pk for rec in recs]
                ).order_by('-rating')[:6-len(recs)])
            
            serializer = self.get_serializer(recs, many=True)
            return Response(serializer.data)
        except Book.DoesNotExist:
            return Response([], status=status.HTTP_404_NOT_FOUND)

    @action(detail=False, methods=['get'], url_path='stats')
    def stats(self, request):
        total_books = Book.objects.count()
        processed_books = Book.objects.filter(is_processed=True).count()
        genres = dict(Book.objects.values('genre').annotate(count=Count('genre')).order_by('-count').values_list('genre', 'count'))
        avg_rating = Book.objects.filter(rating__isnull=False).aggregate(Avg('rating'))['rating__avg'] or 0
        
        return Response({
            'total_books': total_books,
            'processed_books': processed_books,
            'genres': genres,
            'average_rating': round(float(avg_rating), 1)
        })
    @action(detail=False, methods=['get'], url_path='stats')
    def stats(self, request):
        total_books = Book.objects.count()
        processed_books = Book.objects.filter(is_processed=True).count()
        genres = dict(Book.objects.values('genre').annotate(count=Count('genre')).order_by('-count').values_list('genre', 'count'))
        avg_rating = Book.objects.filter(rating__isnull=False).aggregate(Avg('rating'))['rating__avg'] or 0

        return Response({
            'total_books': total_books,
            'processed_books': processed_books,
            'genres': genres,
            'average_rating': round(float(avg_rating), 1)
        })

    @action(detail=False, methods=['get'], url_path='search-gutenberg')
    def search_gutenberg_books(self, request):
        query = request.query_params.get('q', '').strip()
        if not query:
            return Response({'error': 'Query param "q" required'}, status=status.HTTP_400_BAD_REQUEST)

        from scraper.scrape import search_gutenberg
        results = search_gutenberg(query, max_results=5)
        return Response({"results": results})

    @action(detail=False, methods=['post'], url_path='add-from-gutenberg')
    def add_from_gutenberg(self, request):
        gutenberg_id = request.data.get('gutenberg_id')
        title = request.data.get('title')
        author = request.data.get('author')
        text_url = request.data.get('text_url')

        if not all([gutenberg_id, title, text_url]):
            return Response({'error': 'gutenberg_id, title, text_url required'}, status=status.HTTP_400_BAD_REQUEST)

        from scraper.scrape import download_book_by_search_result
        from .rag_service import index_book

        result = {
            "gutenberg_id": gutenberg_id,
            "title": title,
            "author": author or "Unknown",
            "text_url": text_url,
        }
        book_data = download_book_by_search_result(result)

        if not book_data:
            return Response({'error': 'Failed to download book'}, status=status.HTTP_502_BAD_GATEWAY)

        book, created = Book.objects.get_or_create(
            book_url=book_data['book_url'],
            defaults=book_data
        )
        if not created:
            return Response({'message': 'Book already exists', 'book_id': book.id})

        indexed = index_book(book)

        return Response({
            'message': 'Book added and indexed' if indexed else 'Book added but indexing failed',
            'book_id': book.id,
            'title': book.title,
            'indexed': indexed
        })
    @action(detail=True, methods=['post'], url_path='chat')
    def chat(self, request, pk=None):
        question = request.data.get('question', '').strip()
        session_id = request.data.get('session_id', None)

        if not question:
            return Response(
                {'error': 'Question required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        from .rag_service import hybrid_rag_query
        result = hybrid_rag_query(
            question=question,
            book_id=int(pk),
            session_id=session_id
        )

        return Response(result)
    @action(detail=True, methods=['get'], url_path='history')
    def history(self, request, pk=None):
        from .models import ChatSession

        sessions = ChatSession.objects.filter(
            book_id=pk
        ).prefetch_related('messages')

        data = []

        for session in sessions:
            data.append({
                'session_id': session.id,
                'created_at': session.created_at,
                'messages': [
                    {
                        'role': m.role,
                        'content': m.content,
                        'timestamp': m.timestamp
                    }
                    for m in session.messages.all()
                ]
            })

        return Response(data)
