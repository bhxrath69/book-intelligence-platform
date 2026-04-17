from rest_framework import serializers
from .models import Book, BookChunk

class BookChunkSerializer(serializers.ModelSerializer):
    class Meta:
        model = BookChunk
        fields = '__all__'

class BookSerializer(serializers.ModelSerializer):
    chunks = BookChunkSerializer(many=True, read_only=True)
    star_display = serializers.SerializerMethodField()

    class Meta:
        model = Book
        fields = '__all__'

    def get_star_display(self, obj):
        if obj.rating:
            stars = int(round(obj.rating))
            return '★' * stars + '☆' * (5 - stars)
        return '☆☆☆☆☆'
