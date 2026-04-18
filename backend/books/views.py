from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from django.db.models import Count, Avg
from .models import Book
from .serializers import BookSerializer
from scraper.scrape import ScraperSetupError, run_scraper_self_check, scrape_books
from .ai_service import generate_summary, classify_genre, analyze_sentiment
from .rag_service import index_book, rag_query
from django.db import transaction

class BookViewSet(viewsets.ModelViewSet):
    queryset = Book.objects.all()
    serializer_class = BookSerializer
    permission_classes = [AllowAny]
    pagination_class = None

    @action(detail=False, methods=['post'], url_path='upload')
    def upload(self, request):
        try:
            scraped_books = scrape_books(max_pages=5)
            if not scraped_books:
                return Response({
                    'success': False,
                    'new_books': 0,
                    'skipped': 0,
                    'total_scraped': 0,
                    'errors': ['No books were scraped. Check scraper/browser configuration or seed sample data.']
                }, status=status.HTTP_503_SERVICE_UNAVAILABLE)

            new_count = 0
            skipped_count = 0
            errors = []
            indexed_count = 0
            
            for book_data in scraped_books:
                try:
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

                    if index_book(book):
                        indexed_count += 1
                    else:
                        errors.append(f"Saved {book.title}, but indexing failed.")
                    
                except Exception as e:
                    errors.append(f"Error processing {book_data.get('title', 'unknown')}: {str(e)}")
            
            return Response({
                'success': new_count > 0 or skipped_count > 0,
                'new_books': new_count,
                'indexed_books': indexed_count,
                'skipped': skipped_count,
                'total_scraped': len(scraped_books),
                'errors': errors
            }, status=status.HTTP_200_OK if new_count > 0 or skipped_count > 0 else status.HTTP_500_INTERNAL_SERVER_ERROR)
        except ScraperSetupError as e:
            return Response({
                'success': False,
                'error': e.message,
                'details': e.details,
            }, status=e.status_code)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

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
