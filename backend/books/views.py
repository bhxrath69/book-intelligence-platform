from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from django.db.models import Count, Avg
from .models import Book
from .serializers import BookSerializer
from scraper.scrape import scrape_books
from .ai_service import generate_summary, classify_genre, analyze_sentiment
from .rag_service import index_book, rag_query
from django.db import transaction

class BookViewSet(viewsets.ModelViewSet):
    queryset = Book.objects.all()
    serializer_class = BookSerializer
    permission_classes = [AllowAny]

    @action(detail=False, methods=['post'], url_path='upload')
    def upload(self, request):
        try:
            scraped_books = scrape_books(max_pages=5)
            new_count = 0
            skipped_count = 0
            errors = []
            
            for book_data in scraped_books:
                try:
                    book, created = Book.objects.get_or_create(
                        book_url=book_data['book_url'],
                        defaults=book_data
                    )
                    
                    if not created and book.is_processed:
                        skipped_count += 1
                        continue
                    
                    book.title = book_data['title']
                    book.author = book_data['author']
                    book.rating = book_data['rating']
                    book.num_reviews = book_data['num_reviews']
                    book.description = book_data['description']
                    book.cover_image_url = book_data['cover_image_url']
                    
                    book.summary = generate_summary(book.title, book.description)
                    book.genre = classify_genre(book.title, book.description)
                    book.sentiment = analyze_sentiment(book.description)
                    book.is_processed = True
                    book.save()
                    
                    if index_book(book):
                        new_count += 1
                    else:
                        errors.append(f"Failed to index {book.title}")
                    
                except Exception as e:
                    errors.append(f"Error processing {book_data.get('title', 'unknown')}: {str(e)}")
            
            return Response({
                'new_books': new_count,
                'skipped': skipped_count,
                'total_scraped': len(scraped_books),
                'errors': errors
            })
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

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
                    author=book.author,
                    id__ne=pk
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
