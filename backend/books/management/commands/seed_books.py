from django.core.management.base import BaseCommand

from books.models import Book


SAMPLE_BOOKS = [
    {
        "title": "Atomic Habits",
        "author": "James Clear",
        "rating": 5,
        "num_reviews": 1240,
        "description": "A practical guide to building better habits through small, repeatable changes.",
        "book_url": "https://example.com/books/atomic-habits",
        "cover_image_url": "",
        "genre": "Self-Help",
        "summary": "A concise guide to habit formation focused on tiny improvements that compound over time.",
        "sentiment": "Positive",
        "is_processed": True,
    },
    {
        "title": "The Silent Patient",
        "author": "Alex Michaelides",
        "rating": 4,
        "num_reviews": 980,
        "description": "A psychological mystery about a woman who stops speaking after a violent event.",
        "book_url": "https://example.com/books/the-silent-patient",
        "cover_image_url": "",
        "genre": "Mystery",
        "summary": "A suspense novel centered on trauma, silence, and a therapist trying to uncover the truth.",
        "sentiment": "Neutral",
        "is_processed": True,
    },
    {
        "title": "Project Hail Mary",
        "author": "Andy Weir",
        "rating": 5,
        "num_reviews": 860,
        "description": "A lone astronaut wakes up far from Earth and must solve a scientific mystery to save humanity.",
        "book_url": "https://example.com/books/project-hail-mary",
        "cover_image_url": "",
        "genre": "Science Fiction",
        "summary": "A fast-moving science fiction novel blending survival, problem solving, and humor in deep space.",
        "sentiment": "Positive",
        "is_processed": True,
    },
]


class Command(BaseCommand):
    help = "Seed a few sample books for local testing."

    def handle(self, *args, **options):
        created_count = 0

        for payload in SAMPLE_BOOKS:
            _, created = Book.objects.update_or_create(
                book_url=payload["book_url"],
                defaults=payload,
            )
            if created:
                created_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Seed complete. Created {created_count} sample books; total books now {Book.objects.count()}."
            )
        )
