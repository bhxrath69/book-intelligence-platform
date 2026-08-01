from rest_framework import serializers

from .models import Book, BookChunk


class BookChunkSerializer(serializers.ModelSerializer):
    class Meta:
        model = BookChunk
        fields = '__all__'


class BookListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for list views - excludes full_text and chunks"""
    star_display = serializers.SerializerMethodField()

    class Meta:
        model = Book
        exclude = ['full_text']

    def get_star_display(self, obj):
        if obj.rating:
            stars = int(round(obj.rating))
            return '*' * stars + '-' * (5 - stars)
        return '-----'


class BookSerializer(serializers.ModelSerializer):
    """Full serializer for detail views - includes chunks"""
    chunks = BookChunkSerializer(many=True, read_only=True)
    star_display = serializers.SerializerMethodField()

    class Meta:
        model = Book
        exclude = ['full_text']

    def get_star_display(self, obj):
        if obj.rating:
            stars = int(round(obj.rating))
            return '*' * stars + '-' * (5 - stars)
        return '-----'