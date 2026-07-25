from django.db import models
from django.urls import reverse

class Book(models.Model):
    title = models.CharField(max_length=500)
    author = models.CharField(max_length=300)
    rating = models.FloatField(null=True, blank=True)
    num_reviews = models.IntegerField(default=0)
    description = models.TextField(blank=True, default='')
    book_url = models.URLField(unique=True, max_length=255)
    cover_image_url = models.URLField(blank=True, max_length=1000)
    genre = models.CharField(max_length=100, blank=True, default='')
    summary = models.TextField(blank=True, default='')
    sentiment = models.CharField(max_length=50, blank=True, default='')

    # Gutenberg full text used for RAG indexing
    full_text = models.TextField(blank=True, default='')

    is_processed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse('book-detail', kwargs={'pk': self.pk})

class BookChunk(models.Model):
    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name='chunks')
    chunk_text = models.TextField()
    chunk_index = models.IntegerField()
    chroma_id = models.CharField(max_length=200, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['chunk_index']

    def __str__(self):
        return f"Chunk {self.chunk_index} - {self.book.title}"

class ChatSession(models.Model):
    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name='sessions')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Session {self.id} - {self.book.title}"


class Message(models.Model):
    ROLE_CHOICES = [('user', 'User'), ('assistant', 'Assistant')]
    session = models.ForeignKey(ChatSession, on_delete=models.CASCADE, related_name='messages')
    role = models.CharField(max_length=10, choices=ROLE_CHOICES)
    content = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['timestamp']

    def __str__(self):
        return f"{self.role}: {self.content[:50]}"
